# 内容库存与节奏

`inventory_item` 把选题、内容、排期、发布和长尾测量串成可追踪的单元。它不取代 content 或 publication，只保存精确引用和运营状态。

```text
idea -> draft -> review_ready -> ready -> scheduled -> published -> archived
             ↘ held ↗
```

允许的回退由 `portfolio_cli.py transition-inventory` 校验：

- `review_ready` 必须绑定本地 content JSON；
- `ready` 与 `scheduled` 必须有当前 payload 对应的有效 G3；
- `scheduled` 必须有包含时区的明确 ISO 8601 发布时间，并与发布记录的定时时间一致；
- `held` 必须记录原因；
- `published` 必须引用已经确认成功、且绑定同一库存项的 publication；
- 实际上线时间及其依据核对完成后，按本轮“数据采集范围确认”中的短期窗口和长尾配置生成复盘周期；账号战略只提供可修订的默认值，不内置第 7 天、第 30 天等固定值。

计划发布时间只用于排期，不能作为复盘起点。库存进入 `published` 后，复盘周期统一使用关联发布记录的实际上线时间；数据采集范围确认尚未完成时先保留空计划，确认后使用 `schedule-measurements` 生成。

库存目标 `target_coverage_days` 与 `target_ready_items` 都是策略参数。未建立账号基线时允许为 null；运行 Agent 不得自行补默认天数或数量。

同主题节奏使用 `same_topic_key` 和 `same_topic_cooldown_hours` 检查。检查结果为 `allowed`、`needs_human` 或 `blocked`，并写回库存项；任何例外都必须由账号负责人在 G4 或发布后动作记录中明确决定。
