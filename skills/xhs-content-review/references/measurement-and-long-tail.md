# 信任指标与长尾复盘

复盘同时覆盖短期流量、信任形成和长尾贡献。三者不得互相替代。

## 测量计划

“数据采集范围确认”前在内部任务记录中明确：

- `snapshot_windows`：本轮短期采集窗口；
- `trust_metrics`：账号当前真正可采集且有业务含义的信任指标；
- `long_tail_checkpoints_days`：账号负责人配置的长尾检查点；
- `qualitative_rubric_refs`：需要人工判断的评论质量、需求匹配等量表。

短期观察窗口或信任指标为空时不能完成数据采集范围确认。平台没有某字段时记录缺失，不用代理指标冒充。

## 快照

- `measurement_kind=initial`：常规窗口快照，`checkpoint_days` 可为 null。
- `measurement_kind=long_tail`：必须记录正整数 checkpoint 和前一快照 ID。
- `trust_metrics` 保存数值或 null；不把点赞率自动命名为信任。
- 人工评价指标必须引用评价标准和证据，并由内容负责人评估。

库存项发布后，系统按账号战略生成待办。`long-tail-due` 只列出到期项；`complete-long-tail` 必须用 ready 的 long-tail metrics snapshot 完成，不得仅因时间到期自动标记完成。

## 账号与画像修订

复盘中的账号阶段和定位验证结论只是证据化建议。阶段或定位修改必须由账号负责人建立新版本，并重新进行相应人工确认。
