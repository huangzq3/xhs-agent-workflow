# 从选题进入创作

只接受已获 G1 的 account_strategy/persona、已获 G2 的 topic_report JSON 和明确 topic_id。

## 读取

1. 校验 topic_report。
2. 确认 topic_id 位于 selected_topic_ids。
3. 读取对应 candidate 的 premise、audience_need、evidence_refs、risks 和 content_angles。
4. 通过 evidence_refs 读取证据；不得解析 Markdown 或 HTML。

## 写入 content

- topic_report_artifact_id
- topic_id
- strategy_artifact_id
- persona_artifact_id
- content_objective
- content_sequence_no（试运营序列使用，否则 null）
- 继承使用的 provenance
- 新增 claims、personal_experiences、assets

若内容负责人要求更换主题，新建或修订 topic_report 并重新执行 G2，不直接改写已批准选题。
