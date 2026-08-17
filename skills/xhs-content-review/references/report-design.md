# 复盘报告视图

报告必须由 review JSON 渲染，不得在展示层新增结论。

建议结构：

1. 账号、内容、观察窗口和数据完整性
2. 与适用基线的对比
3. 可直接支持的 observations
4. hypotheses 与 alternative explanations
5. 信任与长尾 observations
6. 需人工确认的 lifecycle_assessment 与 persona_validation
7. 按 topic、creative、distribution、positioning、strategy 分类的 interventions
8. 局限与下一次需要补采的数据
9. 待批准的 experiment 候选

视觉规则：

- 明确区分绝对值、增量和比例。
- 图表标注样本数、窗口、分母和缺失值。
- 不用红绿颜色单独表达好坏。
- 不把低置信度推断放进“确定结论”。
- HTML 必须对平台文本、评论和 URL 转义。
