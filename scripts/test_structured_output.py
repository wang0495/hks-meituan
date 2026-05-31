"""测试讯飞模型不同结构化输出方式：tools / response_format / 纯prompt"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

# 加载 .env
_project_root = Path(__file__).resolve().parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.getenv("LLM_API_KEY", "")
BASE_URL = os.getenv("LLM_BASE_URL", "")
MODEL = os.getenv("LLM_MODEL", "")

LONG_SYS = "你是珠海出行路线规划专家。选择POI组成路线。"
LONG_USER = "珠海特种兵一日游，6点出发打卡10个景点，预算200"

TOOLS_DEF = [{
    "type": "function",
    "function": {
        "name": "plan_route",
        "description": "规划出行路线",
        "parameters": {
            "type": "object",
            "properties": {
                "route": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "景点/餐厅名"},
                            "reason": {"type": "string", "description": "选择理由"},
                        },
                        "required": ["name", "reason"],
                    },
                },
                "total_budget": {"type": "number", "description": "预估总花费"},
            },
            "required": ["route"],
        },
    },
}]


async def test(label: str, body_fn, n: int = 20) -> int:
    ok = 0
    parse_ok = 0
    errors: dict[str, int] = {}
    for i in range(n):
        body = body_fn()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=90.0) as c:
                r = await c.post(
                    f"{BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json=body,
                )
                if r.status_code != 200:
                    msg = r.text[:80]
                    if "NotEnoughCv" in msg:
                        errors["NotEnoughCv"] = errors.get("NotEnoughCv", 0) + 1
                    else:
                        errors[f"HTTP{r.status_code}"] = errors.get(f"HTTP{r.status_code}", 0) + 1
                    continue
                data = r.json()
                if "error" in data:
                    errors["api_err"] = errors.get("api_err", 0) + 1
                    continue
                ok += 1
                msg = data["choices"][0]["message"]
                if "tool_calls" in msg and msg["tool_calls"]:
                    args_str = msg["tool_calls"][0]["function"]["arguments"]
                    try:
                        args = json.loads(args_str)
                        if isinstance(args, dict):
                            parse_ok += 1
                    except Exception:
                        pass
                else:
                    content = msg.get("content", "")
                    m = re.search(r"\{[\s\S]*\}", content)
                    if m:
                        try:
                            j = json.loads(m.group())
                            if isinstance(j, dict):
                                parse_ok += 1
                        except Exception:
                            pass
        except Exception as e:
            errors["exc"] = errors.get("exc", 0) + 1
    err_str = ", ".join(f"{k}:{v}" for k, v in errors.items()) if errors else "无"
    print(f"  {label:55s} → 成功{ok}/{n} | 解析{parse_ok}/{n} | 错误: {err_str}")
    return ok


def _tools_forced():
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": LONG_SYS},
            {"role": "user", "content": LONG_USER},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "tools": TOOLS_DEF,
        "tool_choice": {"type": "function", "function": {"name": "plan_route"}},
    }


def _tools_auto():
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": LONG_SYS},
            {"role": "user", "content": LONG_USER},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "tools": TOOLS_DEF,
        "tool_choice": "auto",
    }


def _tools_required():
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": LONG_SYS},
            {"role": "user", "content": LONG_USER},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "tools": TOOLS_DEF,
        "tool_choice": "required",
    }


def _response_format():
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": LONG_SYS + '\n输出JSON: {"route": [{"name": "...", "reason": "..."}]}'},
            {"role": "user", "content": LONG_USER},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
        "extra_body": {"enable_thinking": False},
    }


def _plain_prompt():
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": LONG_SYS + '\n只输出JSON: {"route": [{"name": "...", "reason": "..."}]}'},
            {"role": "user", "content": LONG_USER},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
    }


async def main():
    print(f"Model: {MODEL}")
    print()
    print("=== 20次串行 × 不同结构化输出方式 ===")
    print()

    await test("A: tools + tool_choice=forced (指定函数)", _tools_forced)
    await test("B: tools + tool_choice=auto", _tools_auto)
    await test("C: tools + tool_choice=required", _tools_required)
    await test("D: response_format + enable_thinking=False (当前)", _response_format)
    await test("E: 纯prompt (无约束)", _plain_prompt)

    print()
    print("=== 50并发 × 最佳候选方案 ===")
    print()

    # 并发测试
    for label, body_fn in [
        ("tools forced 50并发", _tools_forced),
        ("纯prompt 50并发", _plain_prompt),
    ]:
        import httpx
        tasks = []
        async with httpx.AsyncClient(timeout=90.0) as c:
            for i in range(50):
                body = body_fn()
                tasks.append(c.post(
                    f"{BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json=body,
                ))
            results = await asyncio.gather(*tasks, return_exceptions=True)
        ok = 0
        errs: dict[str, int] = {}
        for r in results:
            if isinstance(r, Exception):
                errs["exc"] = errs.get("exc", 0) + 1
                continue
            if r.status_code != 200:
                msg = r.text[:60]
                if "NotEnoughCv" in msg:
                    errs["NotEnoughCv"] = errs.get("NotEnoughCv", 0) + 1
                else:
                    errs[f"HTTP{r.status_code}"] = errs.get(f"HTTP{r.status_code}", 0) + 1
            else:
                d = r.json()
                if "error" in d:
                    errs["api_err"] = errs.get("api_err", 0) + 1
                else:
                    ok += 1
        err_str = ", ".join(f"{k}:{v}" for k, v in errs.items()) if errs else "无"
        print(f"  {label:55s} → {ok}/50 | 错误: {err_str}")


if __name__ == "__main__":
    asyncio.run(main())
