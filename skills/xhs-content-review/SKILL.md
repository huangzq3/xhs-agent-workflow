---
name: xhs-content-review
description: 采集小红书内容的短期与长尾指标快照，分离流量、信任和人工定性指标，以账号基线生成 review JSON，并提出需人工确认的生命周期或画像修订。处理笔记复盘、长尾复盘、信任指标、内容数据分析、阶段判断、诊断和观察窗口比较时使用。
---

# 小红书内容复盘

把原始快照、派生指标和解释分层保存。飞书与 HTML 是可选展示或同步目标，JSON 才是事实源。

## 前置条件

1. 要求明确的 run manifest、已发布 publication JSON 和 content JSON。
2. 核对 `account_id`、`content_artifact_id` 和远端 ID。
3. 在采集前请账号负责人完成 G5，明确短期窗口、信任指标、长尾检查点、人工量表、个人数据和同步目标。详见 [references/measurement-and-long-tail.md](references/measurement-and-long-tail.md)。
4. 读取 `metrics_collection` 能力快照，只使用已展示的能力。不可用时接受结构化 JSON/CSV 手工导入；不得编造缺失值。

## 采集

1. 按观察窗口创建不可变 `metrics_snapshot`，区分 `initial` 和 `long_tail`，不覆盖历史快照。
2. 分开保存存量指标、期间增量和派生指标。
3. 图文、视频和文本使用不同指标集合，见 [references/data-analysis.md](references/data-analysis.md)。
4. 分母为零或字段不可用时写 `null` 并登记 `missing_fields`。
5. 信任指标单独写入 `trust_metrics`；需要语义判断的评论质量写入 human-assessed `qualitative_metrics`。
6. 不采集 G5 未批准的受众画像或个人信息。

## 分析

1. 首选同账号、同内容形式、相近生命周期的历史分位数作为基线。
2. 样本不足时明确标为 exploratory，不使用固定阈值伪装确定结论。
3. 把输出拆成：
   - observation：数据直接显示的现象；
   - hypothesis：可能原因；
   - alternative_explanations：其他解释；
   - diagnosis：基于证据的暂定判断；
   - intervention：可验证行动。
4. 不把相关性写成因果关系。
5. 生成 `review` JSON，记录快照、基线、信任与长尾观察，并分别填写 `lifecycle_assessment` 和 `persona_validation`。
6. 阶段/画像变化只作为需要人工确认的修订建议，不能直接改写 account_strategy 或 persona。
7. 从 review JSON 渲染报告；需要飞书时按 [references/feishu-base-schema.md](references/feishu-base-schema.md) 同步，且不得对每日存量快照求和。

## 输出

- 一个或多个 `metrics_snapshot` JSON。
- 一个 `review` JSON。
- 可选 Markdown、HTML、飞书视图。

展示规范见 [references/report-design.md](references/report-design.md)。展示失败不得阻断 JSON 产出。
