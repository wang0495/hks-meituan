"""探测讯飞API最大并发数 — 逐步加压直到错误率飙升。

用法: python scripts/benchmarks/test_xunfei_concurrency
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

import httpx


async def _probe(concurrency: int, api_key: str, base_url: str, model: str) -> dict:
    """用指定并发发一批简单请求，统计成功率和延迟。"""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "max_tokens": 20,
        "messages": [{"role": "user", "content": f"说一个字，第{concurrency}批"}],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    t0 = time.perf_counter()
    ok, fail, errors = 0, 0, {}

    async def _one(i: int):
        nonlocal ok, fail
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.post(url, headers=headers, json={**payload, "messages": [{"role": "user", "content": f"说OK，编号{i}"}]})
                if r.status_code == 200:
                    ok += 1
                else:
                    fail += 1
                    err_msg = r.json().get("error", {}).get("message", "")[:60]
                    errors[err_msg] = errors.get(err_msg, 0) + 1
        except Exception as e:
            fail += 1
            err_msg = str(e)[:60]
            errors[err_msg] = errors.get(err_msg, 0) + 1

    tasks = [_one(i) for i in range(concurrency)]
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0

    return {
        "concurrency": concurrency,
        "ok": ok,
        "fail": fail,
        "total": concurrency,
        "elapsed": round(elapsed, 1),
        "qps": round(concurrency / elapsed, 1),
        "error_rate": round(fail / concurrency * 100, 1),
        "errors": errors,
    }


async def main():
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "")

    if not api_key or not base_url:
        print("需要 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")
        sys.exit(1)

    print("=" * 60)
    print("  讯飞API并发探测")
    print("=" * 60)
    print(f"  API: {base_url}")
    print(f"  Model: {model}")
    print(f"  逐步加压: 5 → 10 → 20 → 30 → 50 → 80 → 100")
    print()

    levels = [100, 200, 300, 500, 800, 1000]
    print(f"  {'并发':>4s} │ {'成功':>4s} │ {'失败':>4s} │ {'错误率':>6s} │ {'耗时':>5s} │ {'QPS':>5s} │ 错误类型")
    print(f"  {'─'*4}─┼─{'─'*4}─┼─{'─'*4}─┼─{'─'*6}─┼─{'─'*5}─┼─{'─'*5}─┼─{'─'*30}")

    for c in levels:
        r = await _probe(c, api_key, base_url, model)
        err_str = "无" if not r["errors"] else "; ".join(f"{k[:20]}×{v}" for k, v in r["errors"].items())
        print(f"  {r['concurrency']:4d} │ {r['ok']:4d} │ {r['fail']:4d} │ {r['error_rate']:5.1f}% │ {r['elapsed']:4.1f}s │ {r['qps']:5.1f} │ {err_str}")
        # 错误率超过30%就停
        if r["error_rate"] > 30:
            print(f"\n  ⚠ 并发 {c} 错误率 {r['error_rate']}%，超过阈值，停止加压")
            break
        await asyncio.sleep(2)  # 批次间喘口气

    print(f"\n  结论: 根据上表选择并发数（错误率 <10% 为安全区）")


if __name__ == "__main__":
    asyncio.run(main())
