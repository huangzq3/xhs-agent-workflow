# Experiment payload 说明

V2 不再输出自动覆盖选题池的 iterate.json。迭代使用 experiment artifact。

~~~json
{
  "review_artifact_id": "review_...",
  "hypothesis": "目标受众是否会把可复现步骤视为核心价值",
  "hypothesis_refs": ["persona_h1"],
  "experiment_mode": "exploration_probe",
  "probe_question": "目标受众更需要完整复现步骤，还是问题诊断框架",
  "diversity_dimensions": ["价值表达"],
  "evidence_plan": {
    "required_evidence_streams": [
      "audience_resonance",
      "delivery_fidelity",
      "platform_distribution",
      "creator_fit"
    ],
    "qualified_exposure_rule": "由账号基线定义本轮可判断的合格曝光",
    "delivery_fidelity_rule": "人工确认每篇完整兑现预设受众任务与价值"
  },
  "intervention_type": "positioning",
  "independent_variable": null,
  "control": null,
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
  "persona_change_proposal": {
    "target_hypothesis_ids": ["persona_h1"],
    "action": "keep",
    "rationale": "本轮只建立待确认建议，不直接覆盖定位",
    "evidence_refs": ["review_..."],
    "counter_evidence_refs": [],
    "requires_new_persona_revision": true,
    "migration_actions": []
  },
  "strategy_change_proposal": null
}
~~~

规则：

- `exploration_probe` 围绕一个问题覆盖不同差异维度，不伪装成严格单变量因果实验；`independent_variable` 与 `control` 可以为 null。
- `controlled_optimization` 只设置一个主要独立变量，并明确保持不变部分。
- 两种模式都必须关联定位假设并写明证据流、有效曝光规则和内容兑现规则。
- topic 实验可以产生候选 topic seed，但不覆盖本轮明确输入。
- positioning 实验必须包含结构化 `persona_change_proposal`，只作用于本实验关联且已被复盘评估的假设，并在后续新建 persona revision、重新执行 G1。
- strategy 实验必须包含 strategy_change_proposal，并在后续创建 account_strategy 新 revision、重新执行 G1。
- 无足够样本时允许探索性结果，但状态应为 inconclusive，而不是“验证成功”。
