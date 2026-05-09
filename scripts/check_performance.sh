#!/bin/bash
# CityFlow 性能回归检测脚本
#
# 用法：bash scripts/check_performance.sh
#
# 功能：
#   1. 运行 tests/test_benchmark.py 基准测试
#   2. 将结果与 tests/baseline.json 比较
#   3. 任一指标退化超过阈值则返回非零退出码
#
# 阈值配置：修改下方 THRESHOLD 变量（百分比）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS_FILE="$PROJECT_ROOT/tests/benchmark_results.json"
BASELINE_FILE="$PROJECT_ROOT/tests/baseline.json"
THRESHOLD=20  # 允许的最大性能退化百分比

cd "$PROJECT_ROOT"

echo "=== CityFlow 性能回归检测 ==="
echo "阈值: ${THRESHOLD}%"
echo ""

# 1. 运行基准测试
echo "--- 运行基准测试 ---"
python tests/test_benchmark.py
echo ""

# 2. 比较结果
if [ ! -f "$BASELINE_FILE" ]; then
    echo "未找到基线文件，跳过比较"
    exit 0
fi

echo "--- 性能回归检测 ---"
python -c "
import json
import sys

THRESHOLD = $THRESHOLD

with open('$RESULTS_FILE', encoding='utf-8') as f:
    results = json.load(f)

with open('$BASELINE_FILE', encoding='utf-8') as f:
    baseline = json.load(f)

checks = ['health_check', 'poi_search', 'distance_matrix', 'route_planning']
failures = []

for key in checks:
    if key not in results or key not in baseline:
        continue

    current = results[key].get('avg_ms', 0)
    base = baseline[key].get('avg_ms', 0)
    if base == 0:
        continue

    change = (current - base) / base * 100

    if change > THRESHOLD:
        msg = f'  [FAIL] {key}: {current:.2f}ms (基线: {base:.2f}ms, 退化: +{change:.1f}%)'
        print(msg)
        failures.append(key)
    elif change > THRESHOLD * 0.5:
        print(f'  [WARN] {key}: {current:.2f}ms (基线: {base:.2f}ms, 变化: {change:+.1f}%)')
    else:
        print(f'  [ OK ] {key}: {current:.2f}ms (基线: {base:.2f}ms, 变化: {change:+.1f}%)')

print()
if failures:
    print(f'检测到 {len(failures)} 项性能回归: {", ".join(failures)}')
    sys.exit(1)
else:
    print('所有性能检查通过')
    sys.exit(0)
"
