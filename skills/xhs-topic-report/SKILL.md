---
name: xhs-topic-report
description: 为指定小红书账号研究、比较和选择选题，生成带证据来源、置信度、局限和人设适配度的 topic_report JSON，并渲染 Markdown/HTML 审阅报告。处理选题分析、竞品爆款拆解、趋势验证、评论洞察和发布优先级请求时使用。
---

# 小红书选题研究

把选题结论建立在可追溯证据上。JSON 是权威输出；Markdown/HTML 只用于审阅。

## 前置条件

1. 要求明确的 run manifest、已获 G1 的 account_strategy 与 persona JSON。
2. 校验同一 `account_id`、战略引用和批准哈希；账号级战略/persona 可来自其他 run，不以 `run_id` 相同替代显式引用。
3. 把内容负责人本轮明确给出的选题放在最高优先级。历史 experiment、persona 种子和外部趋势只能补充，不能覆盖。
4. 需要登录态、评论抓取或画像数据时，先确认 G0 数据范围；没有授权则只使用公开或用户提供的数据。
5. 核对 `web_research` 和 `authenticated_platform_control` 能力快照。不可用时只使用内容负责人提供的材料或公开可核对输入，并记录证据缺口。

## 工作流

1. 保存原始选题清单，不强制补到固定数量；写入 `strategy_artifact_id` 和 `research_mode`。
2. 试运营 persona 使用 `trial_diversification`，让候选覆盖验证计划中的差异维度，避免所有早期内容同质化。
3. 按 [references/workflow.md](references/workflow.md) 收集需求、趋势、竞品和评论证据。
4. 为每条证据保存 `evidence_id`、来源、采集时间、局限和可核对 URL/引用。
5. 只有可核对原文才能保存为 quote；否则写成“观察”或“假设”。
6. 按相关性、受众需求、证据强度、差异化和可执行性评分。不得强行制造高、中、低分布。
7. 对每个候选给出置信度、反证、风险和可执行角度；证据不足时降低置信度。
8. 写入 `topic_report` JSON，状态设为 `review_required`，运行核心 CLI 校验。
9. 由 JSON 渲染报告，按 [references/quality-checklist.md](references/quality-checklist.md) 自检。
10. 请内容负责人明确选择 `topic_id` 并执行 G2；未选择不得进入创作。

## 禁止事项

- 不生成虚假评论、虚假互动量或不存在的来源。
- 不把平台搜索结果排名直接解释成内容需求。
- 不把竞品爆款相关性写成因果关系。
- 不使用示例数据填充正式报告；无数据就明确写缺口。
- 不把固定情绪词、固定数量或固定标题公式当作跨赛道真理。

## 输出

- `artifacts/<account_id>/topic_report/<artifact_id>.json`
- `renders/<account_id>/<artifact_id>.md`
- 可选安全转义的 HTML 审阅视图

标题表达参考 [references/title-formulas.md](references/title-formulas.md)，仅作为候选生成工具，不作为效果承诺。
