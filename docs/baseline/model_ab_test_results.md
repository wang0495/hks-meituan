# 多模型A/B测试结果

测试时间: 2026-05-15
测试场景: 5场景(情侣/亲子/美食/特种兵/休闲)
评分模型: deepseek-chat (统一)
及格线: overall >= 6.5

## 最终排名 (10组A/B测试)

| intent_parser | experts+coordinator | review | 通过 | overall | 说明 |
|---------------|---------------------|--------|------|---------|------|
| **DeepSeek** | **qwen3.5-flash** | **DeepSeek** | **5/5** | **7.0** | 最优方案 |
| qwen-turbo | DeepSeek | DeepSeek | **5/5** | **7.0** | 也可行 |
| DeepSeek | DeepSeek | DeepSeek | 4/5 | 6.4 | 基线 |
| qwen-turbo | qwen3.5-flash | DeepSeek | 3/5 | 6.4 | 叠加翻车 |
| qwen-turbo | qwen3.5-flash | qwen3.5-flash | 3/5 | 6.4 | 全百炼 |
| qwen3.5-flash | qwen3.5-flash | DeepSeek | 3/5 | 6.6 | intent换flash掉分 |
| qwen-turbo | qwen-turbo | DeepSeek | 2~3/5 | 6.4~6.6 | coordinator扛不住 |

### 结论
- 两个5/5方案**不能叠加**, 替换越多节点随机性越大
- review必须留DeepSeek, flash审查判断力不够(3/5→2/5)
- coordinator也必须留DeepSeek, turbo综合判断力不够

## 最优方案: qwen3.5-flash替换experts+coordinator

env vars:
```
EXPERT_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EXPERT_LLM_API_KEY=<your-api-key>
EXPERT_LLM_MODEL=qwen3.5-flash
```

LLM_BASE_URL/LLM_MODEL 保持 DeepSeek (intent_parser + review 用)

### 基线验证 (2026-05-15 复测, 4轮)

| 模型 | overall | 通过 | intent | poi | geo | diverse |
|------|---------|------|--------|-----|-----|---------|
| qwen3.5-flash | 6.8 | 4/5 | 7.6 | 6.8 | 7.2 | 5.2 |
| qwen3-flash | 6.4 | 2/5 | 7.4 | 6.4 | 7.2 | 5.4 |
| qwen-flash | 6.2 | 2/5 | 7.2 | 6.4 | 5.0 | 5.6 |

注意: 之前用了错误的API key导致基线偏低(6.4), 正确key(sk-85c5...)稳定在6.8

## 价格对比

| 组件 | DeepSeek | qwen3.5-flash | 节省 |
|------|----------|---------------|------|
| 输入 | ¥1/M token | ¥0.2/M token | 80% |
| 输出 | ¥2/M token | ¥2/M token | 0% |

experts+coordinator占pipeline token消耗60%+, 实际整体成本降约48%

## 关键发现

1. json模式 + 关thinking必须同时设置, 单独设置无效 (qwen3.5-flash: 8.8s → 0.8s)
2. qwen-turbo可以替代intent_parser (1.7s vs DeepSeek 2.1s, 质量一样)
3. coordinator和review必须留DeepSeek, 小模型判断力不够
4. 替换越多节点随机性越大, 两个5/5方案不能叠加
5. intent_parser短prompt不影响质量 (5/5满分), 还能加速

## 模型价格参考 (百炼/Bailian)

| 模型 | 输入(¥/M) | 输出(¥/M) |
|------|-----------|-----------|
| deepseek-chat (直连) | 1 | 2 |
| qwen3.5-flash | 0.2 | 2 |
| qwen-flash | 0.15 | 1.5 |
| qwen-turbo | 0.3 | 0.6 |
