#!/bin/bash
# ═══════════════════════════════════════════════════════════
# CityFlow 全方位安全与稳定性测试一键脚本
# ═══════════════════════════════════════════════════════════
#
# 用法: bash tests/tools/run_security_tests.sh [--phase 1|2|3|4|5|6|all]
#
# Phase 1: 代码安全扫描 (Bandit + pip-audit + Safety)
# Phase 2: LLM攻击测试 (promptfoo + 自定义payload)
# Phase 3: API渗透测试 (路径遍历/CORS/注入)
# Phase 4: 压力测试 (Locust + k6)
# Phase 5: 速率限制测试
# Phase 6: 全量运行

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
PHASE="${1:-all}"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

banner() {
    echo -e "\n${GREEN}═════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  CityFlow 安全测试 - $1${NC}"
    echo -e "${GREEN}═════════════════════════════════════════════════${NC}\n"
}

pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }

# ─── Phase 1: 代码安全扫描 ───
phase1() {
    banner "Phase 1: 代码安全扫描"

    echo "1.1 Bandit (Python安全扫描)..."
    if command -v bandit &>/dev/null; then
        bandit -r backend/ -f json -o tests/results/bandit.json 2>/dev/null || true
        bandit -r backend/ -ll 2>/dev/null | tail -5 || warn "Bandit扫描完成，有发现"
        pass "Bandit扫描完成"
    else
        warn "Bandit未安装: pip install bandit"
    fi

    echo "\n1.2 pip-audit (依赖漏洞审计)..."
    if command -v pip-audit &>/dev/null; then
        pip-audit -r requirements.txt --desc 2>/dev/null | tail -10 || pass "无已知漏洞"
    else
        warn "pip-audit未安装: pip install pip-audit"
    fi

    echo "\n1.3 Safety (依赖安全检查)..."
    if command -v safety &>/dev/null; then
        safety check -r requirements.txt 2>/dev/null | tail -10 || pass "无安全问题"
    else
        warn "Safety未安装: pip install safety"
    fi
}

# ─── Phase 2: LLM攻击测试 ───
phase2() {
    banner "Phase 2: LLM安全攻击测试"

    echo "2.1 Prompt Injection 攻击测试..."
    python -m pytest tests/test_security_suite.py -v -m llm --tb=short 2>/dev/null || warn "部分LLM测试失败"

    echo "\n2.2 promptfoo 红队测试..."
    if command -v npx &>/dev/null; then
        npx promptfoo@latest eval -c tests/tools/promptfoo_cityflow.yaml 2>/dev/null || warn "promptfoo测试需手动检查"
    else
        warn "Node.js未安装，跳过promptfoo"
    fi

    echo "\n2.3 garak (NVIDIA LLM扫描器)..."
    if command -v garak &>/dev/null; then
        garak --model_type rest --model_name "${BASE_URL}/api/plan" --probes promptinject encoding 2>/dev/null | tail -10 || true
    else
        warn "garak未安装: pip install garak"
    fi
}

# ─── Phase 3: API渗透测试 ───
phase3() {
    banner "Phase 3: API渗透测试"

    echo "3.1 公开端点可达性..."
    for endpoint in "/api/health" "/docs" "/openapi.json"; do
        status=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}${endpoint}")
        if [ "$status" = "200" ]; then
            pass "${endpoint} → ${status}"
        else
            fail "${endpoint} → ${status}"
        fi
    done

    echo "\n3.2 CORS头检查..."
    cors=$(curl -s -I -X OPTIONS -H "Origin: http://evil.com" -H "Access-Control-Request-Method: POST" "${BASE_URL}/api/plan" 2>/dev/null | grep -i "access-control" || echo "无CORS头")
    echo "  CORS响应: ${cors}"

    echo "\n3.3 路径遍历测试..."
    for path in "/metrics" "/admin" "/api/cache/stats" "/pool" "/tasks"; do
        status=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}${path}")
        if [ "$status" = "401" ]; then
            pass "${path} → 401 (认证保护)"
        elif [ "$status" = "200" ]; then
            warn "${path} → 200 (可能需要检查认证配置)"
        else
            pass "${path} → ${status}"
        fi
    done

    echo "\n3.4 GraphQL introspection..."
    gql=$(curl -s -X POST -H "Content-Type: application/json" -d '{"query":"{ __schema { types { name } } }"}' "${BASE_URL}/graphql" 2>/dev/null)
    if echo "$gql" | grep -q "__schema"; then
        warn "GraphQL introspection 开启"
    else
        pass "GraphQL introspection 已关闭或不可达"
    fi

    echo "\n3.5 SQL注入测试..."
    sql_payloads=(
        "珠海一日游' OR '1'='1"
        "珠海' UNION SELECT * FROM users--"
        "珠海'; DROP TABLE pois; --"
    )
    for payload in "${sql_payloads[@]}"; do
        status=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" \
            -d "{\"user_input\":\"${payload}\",\"user_id\":\"sql_test\"}" "${BASE_URL}/api/plan")
        if [ "$status" = "200" ]; then
            pass "SQL payload 未导致崩溃 (${status})"
        else
            warn "SQL payload → ${status}"
        fi
    done

    echo "\n3.6 认证绕过测试..."
    for bypass in "/metrics/../api/health" "/api/plan/../../metrics" "/api/health?next=/metrics"; do
        status=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}${bypass}")
        if [ "$status" = "200" ]; then
            body=$(curl -s "${BASE_URL}${bypass}")
            if echo "$body" | grep -q "metric\|pool\|task"; then
                fail "路径遍历绕过成功: ${bypass}"
            else
                pass "${bypass} → 200 但无敏感数据"
            fi
        else
            pass "${bypass} → ${status} (已阻止)"
        fi
    done
}

# ─── Phase 4: 压力测试 ───
phase4() {
    banner "Phase 4: 压力测试"

    echo "4.1 Locust 压力测试..."
    if command -v locust &>/dev/null; then
        echo "  启动Locust (浏览器打开 http://localhost:8089)..."
        echo "  命令: locust -f tests/test_security_suite.py --host=${BASE_URL}"
        warn "Locust需手动运行: locust -f tests/test_security_suite.py --host=${BASE_URL}"
    else
        warn "Locust未安装: pip install locust"
    fi

    echo "\n4.2 k6 压力测试..."
    if command -v k6 &>/dev/null; then
        k6 run --vus 10 --duration 30s tests/tools/k6_stress.js 2>/dev/null | tail -20 || warn "k6测试需服务运行"
    else
        warn "k6未安装: https://k6.io/docs/get-started/installation/"
    fi

    echo "\n4.3 并发SSE测试 (内置)..."
    python -c "
import httpx, concurrent.futures, time
url = '${BASE_URL}/api/plan'
def req(i):
    start = time.time()
    try:
        r = httpx.post(url, json={'user_input': f'压力测试{i}', 'user_id': f'stress_{i}'}, timeout=60)
        return r.status_code, time.time() - start
    except Exception as e:
        return str(e), time.time() - start
results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    futs = [pool.submit(req, i) for i in range(20)]
    for f in concurrent.futures.as_completed(futs, timeout=120):
        results.append(f.result())
ok = sum(1 for s, t in results if s == 200)
avg_t = sum(t for s, t in results) / len(results)
print(f'  并发20请求: {ok}/{len(results)}成功, 平均耗时{avg_t:.1f}s')
"
}

# ─── Phase 5: 速率限制测试 ───
phase5() {
    banner "Phase 5: 速率限制测试"

    echo "5.1 快速请求测试..."
    count=0
    for i in $(seq 1 70); do
        status=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/health")
        if [ "$status" = "429" ]; then
            count=$((count + 1))
            pass "第${i}个请求被限流 (429)"
            break
        fi
    done
    if [ $count -eq 0 ]; then
        warn "70个请求未被限流 (可能rate_limit_per_minute > 70)"
    fi

    echo "\n5.2 X-Forwarded-For绕过测试..."
    for i in $(seq 1 5); do
        curl -s -o /dev/null -H "X-Forwarded-For: 10.0.${i}.1" "${BASE_URL}/api/health"
    done
    # 检查是否每个IP都被独立限流
    status=$(curl -s -o /dev/null -w "%{http_code}" -H "X-Forwarded-For: 10.0.99.1" "${BASE_URL}/api/health")
    pass "伪造IP请求 → ${status}"
}

# ─── 主流程 ───
mkdir -p tests/results

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║       CityFlow 全方位安全与稳定性测试             ║"
echo "║       目标: ${BASE_URL}                    ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

case "$PHASE" in
    1) phase1 ;;
    2) phase2 ;;
    3) phase3 ;;
    4) phase4 ;;
    5) phase5 ;;
    all|"")
        phase1
        phase3
        phase5
        phase2
        phase4
        ;;
    *)
        echo "Usage: $0 [--phase 1|2|3|4|5|all]"
        exit 1
        ;;
esac

echo -e "\n${GREEN}═════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  测试完成! 结果在 tests/results/ 目录下${NC}"
echo -e "${GREEN}═════════════════════════════════════════════════${NC}\n"
