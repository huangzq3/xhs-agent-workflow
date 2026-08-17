---
name: xhs-content-review
description: 采集小红书内容的短期与长尾数据，分离流量、信任和人工评价指标，以账号自身基线生成复盘，并提出需要人工确认的账号阶段或定位修订。处理笔记复盘、长尾复盘、信任指标、内容数据分析、阶段判断、诊断和观察窗口比较时使用。
---

# 小红书内容复盘

把原始快照、计算指标和解释分层保存在内部机器文件中。内容负责人只接收中文可视化 HTML；不得在对话中输出原始 JSON。遵守 [人工交互与审阅规范](../xhs-workflow/references/human-interface.md)。

## 前置条件

1. 内部要求明确的本轮任务、已发布记录和已定稿内容。
2. 核对账号、内容与平台内容记录一致。
3. 在采集前请账号负责人完成“数据采集范围确认”，明确短期窗口、信任指标、长尾时间点、人工评价标准、个人数据和同步目标。详见 [references/measurement-and-long-tail.md](references/measurement-and-long-tail.md)。
4. 读取 `metrics_collection` 能力快照，只使用已展示的能力。不可用时接受结构化 JSON/CSV 手工导入；不得编造缺失值。

## 采集

1. 按观察窗口创建不可变 `metrics_snapshot`，区分 `initial` 和 `long_tail`，不覆盖历史快照。
2. 分开保存存量指标、期间增量和派生指标。
3. 图文、视频和文本使用不同指标集合，见 [references/data-analysis.md](references/data-analysis.md)。
4. 分母为零或字段不可用时写 `null` 并登记 `missing_fields`。
5. 信任指标单独写入 `trust_metrics`；需要语义判断的评论质量写入 human-assessed `qualitative_metrics`。
6. 不采集未经“数据采集范围确认”允许的受众画像或个人信息。

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
7. 从内部复盘记录生成中文 HTML 报告；需要飞书时按 [references/feishu-base-schema.md](references/feishu-base-schema.md) 同步，且不得对每日累计数据求和。

## 输出

- 机器层：一个或多个数据快照和一份复盘记录，不直接交付给内容负责人。
- 人工层：中文 HTML 复盘报告，突出结论依据、其他可能解释、风险、局限和下一步决定。
- 可选同步层：飞书视图；不得把同步层当作机器事实源。

展示规范见 [references/report-design.md](references/report-design.md)。HTML 生成失败时应明确报告交付失败，不得用原始 JSON 顶替人工报告。
