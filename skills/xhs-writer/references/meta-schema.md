# Content artifact 迁移

旧版 meta.json 不再作为跨 Skill 契约。V2 使用 xhs-workflow 的 content artifact Schema。

关键差异：

- 加入 account_id、run_id、artifact_id 和 revision。
- topic 来源使用 topic_report_artifact_id + topic_id，不解析 HTML。
- 加入 strategy_artifact_id、content_objective 和可选 content_sequence_no。
- format 明确区分 image、video、text。
- cards 与 shots 根据 format 使用。
- claims 区分事实、观点和假设。
- personal_experiences 必须有人类确认来源。
- assets 包含 SHA-256、权利依据、个人数据、外部处理授权和原生生图溯源。
- approvals 绑定 payload hash。
- 排期与长尾状态保存在 inventory_item，发布结果独立保存在 publication，不回写 content。

旧 meta.json 只能通过显式迁移程序导入，不能与 V2 artifact 混用。
