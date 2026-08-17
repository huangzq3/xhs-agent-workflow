# 选题研究流程

## 1. 固定范围

确认账号、run、account_strategy、persona、`research_mode`、目标、观察时间范围和允许的数据来源。内容负责人本轮明确输入始终优先。

## 2. 建立证据表

每条 evidence 至少包含：

~~~json
{
  "evidence_id": "evidence_...",
  "kind": "platform_post|platform_comment|search_trend|user_input|experiment_result",
  "source_ref": "source_...",
  "captured_at": "ISO-8601",
  "observation": "可由数据直接支持的描述",
  "quote": null,
  "quote_verified": false,
  "metrics": {},
  "limitations": []
}
~~~

原文引语必须能回到来源；不可核对内容只能写 observation 或 hypothesis。

## 3. 生成候选

- 保留内容负责人给出的全部候选。
- 可以从 persona 支柱、已完成 experiment 和公开趋势补充。
- 不强制候选数量。
- 不把 creative/distribution 问题转成与账号赛道无关的“运营教学”主题。
- `trial_diversification` 按 persona.validation_plan 的差异维度生成候选，用于提高试运营信息增益；不是为了机械凑数。

## 4. 评分

默认评分仅用于同一报告内部排序，可按目标调整权重：

| 维度 | 默认权重 | 证据 |
|---|---:|---|
| 人设与受众相关性 | 30 | persona 与本轮目标 |
| 需求强度 | 25 | 评论、搜索、用户输入 |
| 证据强度 | 20 | 来源质量、数量与新鲜度 |
| 差异化 | 15 | 竞品空位与账号能力 |
| 可执行性 | 10 | 素材、时间和能力约束 |

权重是报告内部建议值；账号战略或本轮目标需要时可调整，但必须记录理由，不把它当作通用阈值。

记录每项原始分、理由和 evidence refs。不得为了视觉平衡强制制造分档。

## 5. 决策

为每个候选记录置信度、风险、反证和可执行角度。由内容负责人选择 topic_id 并执行 G2。
