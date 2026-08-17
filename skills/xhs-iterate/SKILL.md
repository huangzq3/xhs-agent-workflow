---
name: xhs-iterate
description: 把小红书 review JSON 转换为下一轮可验证实验，区分选题、创意、分发、定位和账号战略干预，定义单变量、基线、窗口、指标与停止条件。处理复盘后行动、下轮实验、迭代优化、定位或生命周期修订建议时使用。
---

# 小红书实验迭代

迭代产物是实验计划，不是自动塞回选题池的泛化建议。

## 前置条件

1. 要求明确的 review JSON、run manifest 和账号。
2. 校验 review 引用的 metrics snapshots 与 content 均属于同一 `account_id`。
3. review 证据不足时可以提出探索性实验，但必须降低置信度，不把假设写成结论。

## 工作流

1. 读取 observation、hypothesis、alternative explanations 和 recommended interventions。
2. 按 [references/diagnosis-topic-mapping.md](references/diagnosis-topic-mapping.md) 将干预归为：
   - `topic`：受众需求或主题选择；
   - `creative`：标题、开头、结构、视觉、口播；
   - `distribution`：SEO、发布时间、标签、发布方式；
   - `positioning`：受众、价值主张或内容支柱；
   - `strategy`：生命周期、内容目标组合、库存、发布或测量策略。
3. 每个 experiment 只设置一个主要独立变量；写明对照、目标指标、护栏指标、观察窗口、样本计划和停止条件。
4. `creative` 或 `distribution` 问题不得改造成“教创作者提高留存/SEO”的账号选题。
5. `topic` 实验可以提出下一轮 topic seed，但其优先级低于内容负责人本轮明确输入。
6. `positioning` 实验只生成 `persona_change_proposal`；`strategy` 实验只生成 `strategy_change_proposal`。不得直接修改 persona 或 account_strategy；接受结果后建立新修订并重新 G1。
7. 写入 `experiment` JSON，状态设为 `review_required`，运行核心 CLI 校验。
8. 展示实验成本、预期信息增益和风险，请内容负责人完成 G6。
9. G6 通过后登记到下一轮 manifest；实验完成前不得宣称改动有效。

## 输出

- `artifacts/<account_id>/experiment/<artifact_id>.json`
- 由 JSON 渲染的实验卡 Markdown/HTML
- G6 审批和后续结果审计记录

字段说明见 [references/iterate-schema.md](references/iterate-schema.md)。
