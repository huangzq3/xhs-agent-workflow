# Persona payload 说明

权威约束位于 xhs-workflow/references/schemas/artifact.schema.json。本文件只解释 persona 的领域含义。

~~~json
{
  "revision": 1,
  "supersedes_artifact_id": null,
  "strategy_artifact_id": "account_strategy_...",
  "mode": "assumed",
  "hypotheses": [
    {
      "hypothesis_id": "persona_h1",
      "statement": "目标人群需要某项可验证价值",
      "status": "pending",
      "evidence_refs": []
    }
  ],
  "validation_plan": {
    "sample_target": null,
    "diversity_dimensions": [],
    "success_signals": ["由账号负责人定义的信号"],
    "stop_conditions": ["核心假设被连续证据反驳"]
  },
  "identity": {
    "display_name": "账号展示名称",
    "positioning_statement": "为哪类人提供什么可验证价值",
    "credentials": ["有来源支持的背景或能力"]
  },
  "niche": {
    "primary": "主赛道",
    "subtopics": ["细分方向"],
    "formats": ["image", "video"]
  },
  "audience": [
    {
      "segment_id": "audience_1",
      "name": "细分人群",
      "jobs": ["希望完成的任务"],
      "pains": ["真实问题"],
      "desired_outcomes": ["期望结果"],
      "evidence_refs": ["source_..."]
    }
  ],
  "differentiation": {
    "value_proposition": "差异化价值",
    "proof": ["支持差异化的证据"],
    "non_goals": ["明确不做"]
  },
  "content_pillars": [
    {
      "pillar_id": "pillar_1",
      "name": "内容支柱",
      "purpose": "服务哪类需求",
      "boundaries": ["不延伸到什么"],
      "topic_seeds": ["仅作建议的种子"]
    }
  ],
  "voice": {
    "traits": ["清晰", "克制"],
    "do": ["使用可核对例子"],
    "dont": ["编造亲测经历"]
  },
  "visual": {
    "principles": ["可读性优先"],
    "constraints": []
  },
  "boundaries": ["隐私、伦理、商业或内容边界"]
}
~~~

规则：

- 不设置具体城市、职业、赛道等默认个人信息。
- credentials 和 proof 必须有 provenance。
- topic_seeds 不是强制队列，不得覆盖本轮明确选题。
- 定位变化使用新 revision 与 supersedes_artifact_id，保留旧版。
- assumed persona 的 G1 批准测试边界，不代表定位已验证；转为 validated 必须建立新 revision。
