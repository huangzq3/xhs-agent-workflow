# 发布与发布后策略

账号战略中的 `publishing_policy` 是发布节奏与发布后动作的唯一配置来源。运行 Agent 不内置“发布后一天不能改”“同主题隔两天”等数字。

## 发布前检查

使用 `portfolio_cli.py check-policy --action publish` 生成 `policy_check`：

- `allowed`：未发现违反当前策略的条件；仍需 G4；
- `needs_human`：阈值未配置、同主题处于冷却期，或某项状态需要证据判断；G4 必须明确处理例外；
- `blocked`：策略明确禁止该动作；G4 不得批准。

policy check 绑定 `strategy_artifact_id` 和检查时间。账号战略修订后必须重新检查。

## 发布后修改与删除

远端修改和删除不属于自动恢复动作：

1. 先用 `check-policy --action modify|delete` 查看当前策略；
2. `human_review_required` 返回 `needs_human`；
3. 账号负责人用 `record-post-publish` 明确批准或拒绝，并写明理由；
4. `prohibited` 不得记录为 approved；
5. 记录决定本身不等于已经在平台执行，实际外部动作仍要单独核验与审计。

发布结果为 unknown 时仍按发布状态机人工核对，不得把删除或重发当作自动补偿。
