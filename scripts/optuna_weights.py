"""Optuna权重搜索 — 贝叶斯优化路线规划评分权重。

搜索空间：7个权重因子，每个范围[0.05, 0.40]
目标：最大化golden test cases通过率

用法:
    # 安装optuna: pip install optuna
    python scripts/optuna_weights.py --trials 200
    python scripts/optuna_weights.py --trials 100 --limit 30  # 快速调试
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 项目根目录

import optuna

from backend.services.solver import (
    _ALPHA, _BETA, _GAMMA, _DELTA, _REACTION_WEIGHT, _SENSORY_WEIGHT,
)
# 使用scripts/目录下的eval_framework，避免与根目录的旧文件冲突
import importlib.util
_eval_path = Path(__file__).resolve().parent / "eval_framework.py"
_spec = importlib.util.spec_from_file_location("eval_framework", _eval_path)
_eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eval_mod)
load_golden_cases = _eval_mod.load_golden_cases
load_poi_db = _eval_mod.load_poi_db
run_evaluation = _eval_mod.run_evaluation

# 搜索空间定义
WEIGHT_SPACE = {
    "alpha":   (0.05, 0.50, _ALPHA),    # travel time
    "beta":    (0.05, 0.50, _BETA),     # phase score
    "gamma":   (0.02, 0.30, _GAMMA),    # fatigue
    "delta":   (0.10, 0.60, _DELTA),    # same type penalty
    "reaction":(0.00, 0.30, _REACTION_WEIGHT),  # chemical reaction
    "sensory": (0.00, 0.20, _SENSORY_WEIGHT),   # sensory alternation
    "area":    (0.00, 0.30, 1.0),       # area penalty
}

# 结果缓存
_results_cache: dict[str, float] = {}


def weights_to_key(weights: dict) -> str:
    """权重转缓存key"""
    return json.dumps(sorted(weights.items()))


def objective(trial: optuna.Trial, poi_db: list, golden: list) -> float:
    """Optuna目标函数"""
    weights = {}
    for name, (lo, hi, default) in WEIGHT_SPACE.items():
        weights[name] = trial.suggest_float(name, lo, hi, step=0.01)

    # 缓存检查
    key = weights_to_key(weights)
    if key in _results_cache:
        return _results_cache[key]

    # 运行评估
    summary = run_evaluation(poi_db, golden, weights=weights, verbose=False)
    pass_rate = summary["total_pass_rate"]

    # 额外奖励：各画像通过率的方差越小越好（均匀提升）
    profile_rates = [v["pass_rate"] for v in summary["by_profile"].values()]
    if profile_rates:
        mean_rate = sum(profile_rates) / len(profile_rates)
        variance = sum((r - mean_rate) ** 2 for r in profile_rates) / len(profile_rates)
        # 目标 = 通过率 - 0.1 * 方差（鼓励均匀提升）
        score = pass_rate - 0.1 * variance
    else:
        score = pass_rate

    _results_cache[key] = score

    # 打印进度
    print(f"  Trial {trial.number:3d}: pass={pass_rate:.3f} score={score:.3f} "
          f"weights={ {k: f'{v:.2f}' for k, v in weights.items()} }")

    return score


def run_optimization(
    poi_db: list,
    golden: list,
    n_trials: int = 200,
    timeout: int = 3600,
) -> dict:
    """运行Optuna优化。

    Returns:
        {"best_weights": dict, "best_score": float, "study_stats": dict}
    """
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(),
    )

    print(f"\n开始Optuna搜索: {n_trials} trials, timeout={timeout}s")
    print(f"搜索空间: { {k: f'[{lo:.2f}, {hi:.2f}]' for k, (lo, hi, _) in WEIGHT_SPACE.items()} }")
    print(f"默认权重: { {k: f'{d:.2f}' for k, (_, _, d) in WEIGHT_SPACE.items()} }")

    start = time.time()
    study.optimize(
        lambda trial: objective(trial, poi_db, golden),
        n_trials=n_trials,
        timeout=timeout,
        show_progress_bar=True,
    )
    elapsed = time.time() - start

    best = study.best_trial
    best_weights = best.params

    # 用最优权重跑一次完整评估（verbose打印失败case）
    print(f"\n最优权重完整评估:")
    best_summary = run_evaluation(poi_db, golden, weights=best_weights, verbose=True)

    result = {
        "best_weights": best_weights,
        "best_score": best.value,
        "best_pass_rate": best_summary["total_pass_rate"],
        "by_profile": best_summary["by_profile"],
        "n_trials": len(study.trials),
        "elapsed_seconds": round(elapsed, 1),
        "default_weights": {k: d for k, (_, _, d) in WEIGHT_SPACE.items()},
    }

    # 保存结果
    output_path = Path("tests/optuna_result.json")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存至: {output_path}")

    return result


def print_result(result: dict):
    """打印优化结果"""
    print(f"\n{'='*60}")
    print(f"  Optuna优化结果")
    print(f"{'='*60}")
    print(f"  最优通过率: {result['best_pass_rate']*100:.1f}%")
    print(f"  试验次数: {result['n_trials']}")
    print(f"  耗时: {result['elapsed_seconds']:.1f}s")

    print(f"\n  权重对比:")
    print(f"  {'因子':12s} {'默认':>8s} {'最优':>8s} {'变化':>8s}")
    print(f"  {'-'*40}")
    for key in WEIGHT_SPACE:
        default = result["default_weights"].get(key, 0)
        best = result["best_weights"].get(key, 0)
        delta = best - default
        arrow = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "→")
        print(f"  {key:12s} {default:8.2f} {best:8.2f} {arrow} {delta:+.2f}")

    print(f"\n  各画像通过率:")
    for profile, stats in sorted(result["by_profile"].items()):
        bar = "█" * int(stats["pass_rate"] * 20) + "░" * (20 - int(stats["pass_rate"] * 20))
        print(f"    {profile:8s} {bar} {stats['pass_rate']*100:5.1f}% "
              f"({stats['passed']}/{stats['total']})")


def main():
    parser = argparse.ArgumentParser(description="Optuna权重搜索")
    parser.add_argument("--trials", type=int, default=200, help="搜索次数")
    parser.add_argument("--timeout", type=int, default=3600, help="超时秒数")
    parser.add_argument("--limit", type=int, default=0, help="限制golden cases数量（调试）")
    args = parser.parse_args()

    print("加载数据...")
    golden = load_golden_cases()
    poi_db = load_poi_db()

    if args.limit > 0:
        golden = golden[:args.limit]
        print(f"  限制为前 {args.limit} 个cases")

    result = run_optimization(poi_db, golden, n_trials=args.trials, timeout=args.timeout)
    print_result(result)


if __name__ == "__main__":
    main()
