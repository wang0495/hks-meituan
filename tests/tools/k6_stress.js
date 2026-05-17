// k6 压力测试脚本 - CityFlow
// 安装: https://k6.io/docs/get-started/installation/
// 用法: k6 run tests/tools/k6_stress.js
//
// k6 (30K+ stars) - 最流行的HTTP压力测试工具
// 支持SSE流式测试、自定义指标、阶梯加压

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// 自定义指标
const errorRate = new Rate('errors');
const sseDuration = new Trend('sse_duration_ms');

export const options = {
  stages: [
    // 阶梯加压: 1→10→50→10→1
    { duration: '30s', target: 10 },   // 预热
    { duration: '1m',  target: 50 },   // 加压
    { duration: '30s', target: 100 },  // 峰值
    { duration: '1m',  target: 50 },   // 降压
    { duration: '30s', target: 1 },    // 恢复
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'],   // 95%请求在5s内完成
    errors: ['rate<0.1'],                // 错误率<10%
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// 测试场景
const SCENARIOS = [
  { input: '情侣珠海一日游，喜欢拍照打卡', weight: 3 },
  { input: '亲子海洋王国一日游，预算500', weight: 2 },
  { input: '珠海美食探索，想吃海鲜', weight: 2 },
  { input: '特种兵打卡，一天10个景点', weight: 1 },
  { input: '休闲养老游，走走停停', weight: 1 },
];

function pickScenario() {
  const totalWeight = SCENARIOS.reduce((s, sc) => s + sc.weight, 0);
  let r = Math.random() * totalWeight;
  for (const sc of SCENARIOS) {
    r -= sc.weight;
    if (r <= 0) return sc;
  }
  return SCENARIOS[0];
}

export default function () {
  const scenario = pickScenario();

  // 测试1: /api/plan (SSE)
  const startTime = Date.now();
  const planResp = http.post(`${BASE_URL}/api/plan`, JSON.stringify({
    user_input: scenario.input,
    user_id: `k6_${__VU}_${__ITER}`,
  }), {
    headers: { 'Content-Type': 'application/json' },
    timeout: '60s',
  });

  const duration = Date.now() - startTime;
  sseDuration.add(duration);

  const planOk = check(planResp, {
    'plan status 200': (r) => r.status === 200,
    'plan has content': (r) => r.body && r.body.length > 0,
    'plan no error': (r) => !r.body || !r.body.includes('"error"'),
  });
  errorRate.add(!planOk);

  sleep(1);

  // 测试2: /api/health
  const healthResp = http.get(`${BASE_URL}/api/health`);
  check(healthResp, {
    'health status 200': (r) => r.status === 200,
  });

  sleep(2);
}

// SSE专用测试 (单独运行: k6 run -e TEST=sse tests/tools/k6_stress.js)
export function handleSummary(data) {
  return {
    'stdout': JSON.stringify(data, null, 2),
    'tests/results/k6_report.json': JSON.stringify(data, null, 2),
  };
}
