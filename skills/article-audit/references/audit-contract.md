# 审计数据契约

权威机器约束见 [article-audit.schema.json](article-audit.schema.json)，确定性校验见 `../scripts/article_audit_cli.py`。

通用独立审计使用顶层 `schema_version=article-audit/1.0.0`，`account_id` 和 `run_id` 可为 null。接入 xhs-workflow 时使用其 artifact 信封：`schema_version=2.2.0`，并填写实际账号和任务标识。两种信封共用 `payload.contract_version=1.0.0` 和完全相同的审计语义。

## 目标绑定

每次审计必须记录：

- `content_artifact_id` 和 `content_revision`；
- `target_uri`；
- `content_sha256` 与 `hash_mode`；
- 作者与审计者的身份快照；
- 规则集、覆盖表面和证据范围。

小红书 content artifact 的目标指纹是由 `payload` 和 `provenance` 组成的规范化 JSON SHA-256，但计算前移除 `article_audit_ref`。这样编排器可以在审计完成后写入审计引用，同时不改变被审文章与来源的指纹；修改来源记录也会使旧审计失效。其他所有冻结目标，包括 Markdown、纯文本和非 xhs JSON，均使用原始字节 SHA-256。

## 独立性

作者和审计者必须满足：

- `actor_id` 不同；
- 作者为 Agent 时，`context_id` 均存在且不同；
- 审计者为 Agent，并声明全新上下文；
- `read_only=true`；
- `prompt_injection_treated_as_data=true`。

这些字段让工作流能够拒绝明显的自审，但真实的权限隔离仍由运行环境负责。无法证明只读边界时不能声称已经完成独立审计。

## 独立主张清单

`claim_inventory.method` 固定为 `independent_full_text_review`。清单由审计者从最终稿重新提取，不得复制作者的 `claims` 后直接宣称完成。

每项主张记录：

- 文本与最终呈现位置；
- 类型，事实、观点、假设或个人经历；
- 是否属于会影响读者判断的关键主张；
- 来源引用；
- 核实状态。

`source_refs` 必须指向审计 artifact 或被审 content 的 `provenance.source_id`。事实主张标为“已核实”或“与证据冲突”时必须有已登记来源；“有来源字符串”不等于来源已经登记和核对。

关键事实处于 `unverified` 或 `contradicted` 时，必须存在对应的开放 P0。

## 结论

| 结论 | 条件 |
|---|---|
| `passed` | 没有开放 P0/P1；可以保留 P2 |
| `audit_failed` | 存在开放 P0，或存在必须先修订的 P1 |
| `human_decision_required` | 没有开放 P0，但存在需要人工决定的 P1，或高风险复核缺少模型多样性等重要局限 |

审计 Agent 不能作出人工豁免。小红书接入中，`human_decision_required` 只有在内容负责人于 G3 明确记录理由后才能继续。

## 失效条件

- 稿件指纹变化；
- 审计 artifact payload 被改动；
- 规则集版本变化；
- 覆盖表面变化；
- 作者身份记录变化。

任一条件发生后必须重新审计，不能只更新旧审计的结论字段。
