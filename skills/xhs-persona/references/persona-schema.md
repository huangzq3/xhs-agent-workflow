# Persona payload 说明

权威约束位于 xhs-workflow/references/schemas/artifact.schema.json。本文件只解释 persona 的领域含义。

~~~json
{
  "revision": 1,
  "supersedes_artifact_id": null,
  "strategy_artifact_id": "account_strategy_...",
  "mode": "assumed",
  "positioning_diagnosis": {
    "diagnosis_type": "initial_definition",
    "rationale": "首次建立该账号的可验证定位",
    "evidence_refs": ["source_..."],
    "alternative_explanations": ["受众需求可能比当前设想更细分"],
    "recommended_action": "create"
  },
  "direction_alignment": {
    "account_role": "本账号在创作者长期方向中的职责",
    "account_current_value": "本账号当下交付的价值",
    "account_future_value": "本账号帮助受众通往的长期价值",
    "relationship_expression": "创作者关系姿态在本账号的表达",
    "trust_expression": "本账号可重复展示的信任证据",
    "content_engine_expression": "本账号持续产生内容的循环",
    "memory_asset_expression": "主记忆资产在标题、内容和系列中的稳定表达",
    "business_connection": "本账号与创作者商业去向的连接，不等于每篇都要销售",
    "tensions": ["平台表达与长期方向之间需要解决的张力"],
    "evidence_refs": ["source_..."]
  },
  "positioning_state": {
    "phase": "exploration",
    "scope": "小红书目标受众与当前试运营周期",
    "stable_core": ["真实能力、价值或边界"],
    "open_questions": ["仍需通过内容回答的问题"],
    "anti_audience": ["不主动吸引的人群"],
    "anti_positioning": ["不希望形成的账号认知"],
    "review_by": null
  },
  "validation_evidence": {
    "review_artifact_refs": [],
    "experiment_artifact_refs": [],
    "content_artifact_refs": [],
    "snapshot_artifact_refs": [],
    "evidence_streams_covered": [],
    "counter_evidence_reviewed": false,
    "reviewed_at": null,
    "limitations": ["尚无正式复盘证据"]
  },
  "hypotheses": [
    {
      "hypothesis_id": "persona_h1",
      "component": "value",
      "statement": "目标人群需要某项可验证价值",
      "observable_implication": "成立时应出现的可观察现象",
      "falsification_signal": "能够推翻该假设的现象",
      "status": "testing",
      "confidence": "low",
      "scope": "本轮试运营范围",
      "evidence_refs": [],
      "counter_evidence_refs": [],
      "review_by": null
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
    "positioning_statement": "当前暂定为哪类人提供什么可验证价值",
    "credentials": ["有来源支持的背景或能力"]
  },
  "niche": {
    "primary": "本轮优先探索的问题空间，不是永久赛道结论",
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
      "audience_segment_refs": ["audience_1"],
      "audience_job": "该受众希望完成的任务",
      "value_delivered": "该支柱当下交付的具体价值",
      "proof_role": "该支柱如何为信任引擎提供证据",
      "memory_asset": "该支柱稳定强化的记忆资产",
      "business_connection": "该支柱如何服务商业去向",
      "hypothesis_refs": ["persona_h1"],
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
- `identity.positioning_statement` 与 `niche.primary` 是开始行动所需的最小工作表达，不是已验证事实；不确定部分必须同步进入定位假设或开放问题。
- credentials 和 proof 必须有 provenance。
- `positioning_diagnosis` 先判断是初次建立、基础不清、兑现不稳定、受众错配还是证据不足。兑现不稳定或证据不足时不得直接建议改定位。
- `direction_alignment` 只是将已确认的 `creator_direction` 投射到本账号，不能静默改写策略层。
- `positioning_state` 区分探索、收敛、当前范围内稳定和重新检验；`scope` 与 `review_by` 防止把阶段性结论写成永久真相。
- `validation_evidence` 在首次探索时可以为空，但字段本身必须存在。非首版定位必须回指已确认上一版：同一策略下的修订至少引用一份真实复盘；如果引用实验，该实验必须已通过 G6 且所属复盘同时在证据列表中。稳定化时还必须引用至少两篇不同内容、数据快照、证据流、反证复核和时间。
- 每个定位假设必须可观察、可反驳，并独立记录成熟度、正反证据、适用范围和复核时间。
- 每个内容支柱至少关联一个存在的受众分组；`hypothesis_refs` 如果非空，必须引用存在的定位假设。
- `memory_asset` 进入内容支柱，后续选题和稿件必须原样继承其定位追踪。
- topic_seeds 不是强制队列，不得覆盖本轮明确选题。
- 定位变化使用连续的新 revision 与 `supersedes_artifact_id`，保留旧版。修订依据只能是已确认的创作者方向/账号策略变化，或能追溯到上一版定位的复盘与实验；不得只因运营者有了新想法就覆盖。
- `mode` 是兼容摘要。assumed persona 的 G1 批准搜索空间，不代表定位已验证；转为 validated 必须建立新 revision，并通过 [定位生长闭环](../../xhs-workflow/references/positioning-loop.md) 的真实证据门禁。
