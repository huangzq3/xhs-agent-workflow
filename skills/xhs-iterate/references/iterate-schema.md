# Experiment payload 说明

V2 不再输出自动覆盖选题池的 iterate.json。迭代使用 experiment artifact。

~~~json
{
  "review_artifact_id": "review_...",
  "hypothesis": "如果改变一个变量，目标指标将按预期变化",
  "intervention_type": "creative",
  "independent_variable": "封面价值表达",
  "control": "保持主题、正文、发布时间和标签不变",
  "target_metric": {
    "name": "click_rate",
    "direction": "increase",
    "minimum_effect": 0.1,
    "baseline_ref": "review_..."
  },
  "guardrails": [
    {"name": "negative_feedback_rate", "condition": "not_increase"}
  ],
  "observation_window": "由本轮测量计划明确的窗口",
  "sample_size_plan": "至少 4 个匹配内容对；不足时标为探索性",
  "stop_rule": "达到计划样本或出现护栏恶化时停止",
  "state": "proposed",
  "result": null,
  "persona_change_proposal": null,
  "strategy_change_proposal": null
}
~~~

规则：

- 一份 experiment 只设置一个主要独立变量。
- topic 实验可以产生候选 topic seed，但不覆盖本轮明确输入。
- positioning 实验必须包含 persona_change_proposal，并在后续重新执行 G1。
- strategy 实验必须包含 strategy_change_proposal，并在后续创建 account_strategy 新 revision、重新执行 G1。
- 无足够样本时允许探索性结果，但状态应为 inconclusive，而不是“验证成功”。
