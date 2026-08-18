# V2 数据契约

## 事实源原则

- JSON 是唯一机器事实源。
- 中文 HTML 是可删除、可再生成的人工审阅视图；不得把原始机器数据直接作为人工报告。
- 图片、视频等二进制资产通过 URI、SHA-256、权利信息引用，不嵌入 artifact。
- 任何在线表格、数据库和仪表盘都是可选同步目标，不是事实源。

## 工作区布局

```text
<workspace>/
├── workspace.json
├── accounts/<account_id>/account.json
├── runs/<run_id>/run.json
├── artifacts/<account_id>/<artifact_type>/<artifact_id>.json
├── assets/<account_id>/<content_id>/...
├── renders/<account_id>/<artifact_id>.html
└── audit/events.ndjson
```

禁止使用仅含日期的文件名。所有实体使用稳定 ID，并在 JSON 内重复声明 `account_id` 与 `run_id`。

## 通用信封

每个 artifact 必须包含：

```json
{
  "schema_version": "2.2.0",
  "artifact_type": "persona",
  "artifact_id": "persona_...",
  "account_id": "account_slug",
  "run_id": "run_...",
  "created_at": "2026-08-17T10:00:00+08:00",
  "updated_at": "2026-08-17T10:00:00+08:00",
  "status": "review_required",
  "provenance": [],
  "approvals": [],
  "payload": {}
}
```

`provenance` 记录用户输入、平台数据、网页证据、派生过程或生成过程。原文引语只有在保存可核对来源且 `quote_verified=true` 时才能以引号展示；否则改写成“观察”或“假设”。

`approvals` 保存门禁、人工身份、决定、时间、备注与该门禁负责字段的 SHA-256。G0 绑定运行能力与数据范围，G5 绑定测量计划；领域 artifact 绑定去除状态型字段后的业务 payload。受保护字段变化会使对应批准失效。

`run_manifest.payload.runtime_capabilities` 保存当前 Agent 运行时的已发现能力，而不保存假定的产品配置。`data_scope.external_processing` 使用实际 `capability_id` 声明会离开本地工作区的数据处理。能力快照或外部处理范围变更时，G0 必须重新批准。

## Artifact 职责

| artifact_type | 生产者 | 主要消费者 | 核心内容 |
|---|---|---|---|
| run_manifest | xhs-workflow | 全部 | 本轮目标、运行时能力、数据范围、阶段、门禁、artifact 路径 |
| account_strategy | xhs-workflow | 全部 | 生命周期、内容目标、库存、发布与测量策略 |
| persona | xhs-persona | topic-report、writer、review | 已确认定位事实或试运营假设、验证计划、边界 |
| topic_report | xhs-topic-report | writer | 候选选题、证据、评分、局限 |
| content | xhs-writer | publish、review | 文案、卡片/分镜、事实与权利台账 |
| inventory_item | xhs-workflow | publish、review | 创作/排期/发布状态、精确引用、长尾检查点 |
| publication | xhs-publish | review | 目标账号、立即或定时安排、尝试、远端结果、实际上线时间及依据 |
| metrics_snapshot | xhs-content-review | review | 某一采集时点的原始指标快照、实际上线时间锚点和真实观察时长 |
| review | xhs-content-review | iterate | 基线、观察、假设、诊断和建议 |
| experiment | xhs-iterate | topic-report、writer、review | 单变量实验、窗口、指标和停止条件 |

完整约束由 [schemas/artifact.schema.json](schemas/artifact.schema.json) 定义，并由 `workflow_cli.py validate` 执行额外的跨字段检查。

定时发布记录可以保存 `scheduled_at`、`schedule_expires_at`、`schedule_method` 与平台或运行工具返回的排期凭据。`published_at` 专指平台确认的实际上线时间；计划时间、排期提交时间和发布尝试开始时间不得写入该字段。内容库存中的复盘周期使用 `anchor_published_at` 固定该起点，数据快照用 `published_at_anchor` 证明使用了同一时间轴。

## 输入优先级

1. 本轮内容负责人明确输入。
2. 本轮已批准 artifact。
3. 同账号明确引用且仍有效的已批准 account_strategy 与 persona。
4. 同账号历史 review/experiment，仅作为建议并标注日期与适用范围。
5. 外部趋势和竞品证据。

低优先级信息不得覆盖高优先级信息。冲突必须显式呈现并请求决定。
