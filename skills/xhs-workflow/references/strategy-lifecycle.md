# 账号战略与生命周期

`account_strategy` 是账号级、版本化的控制面；`run_manifest` 是一次执行的运行面。账号资料 `account.json` 只保存稳定身份，不承载会变化的运营判断。

## 生命周期

| 阶段 | 主要问题 | 常见证据方向 |
|---|---|---|
| trial | 哪类受众、价值与形式值得继续验证 | 多样化样本、画像假设、早期信任信号 |
| scale | 哪些已验证模式可以稳定扩大 | 同类内容重复性、产能、转化与负反馈 |
| stabilize | 如何降低波动并提高可持续性 | 基线分位数、库存覆盖、流程瓶颈 |
| flywheel | 如何让内容、搜索、社群与转化相互增强 | 长尾贡献、复访、系列化与资产复用 |

阶段不是由粉丝数或单篇爆款自动决定。每次新建或修订账号战略都要记录 `stage_evidence`、置信度、替代解释和局限。阶段变化写入新 revision，设置 `supersedes_artifact_id`，并由账号负责人重新完成 G1。

## 两级编排

1. `full_cycle` 或 `strategy_review` run 先产生账号战略。
2. persona 必须显式引用已批准战略。
3. 内容类 run 使用 `--strategy` 与 `--persona` 引用账号级版本，不复制或隐式寻找“最新版”。
4. run 的 `run_type` 决定 G0 后的入口阶段；运行 Agent 不根据品牌或文件时间猜测。
5. review 只能提出生命周期修订，`requires_human_confirmation` 必须为 true；不得直接改写账号战略。

## 内容目标

每个内容项明确一个目标：`acquisition`、`trust` 或 `tag_strengthening`。`target_share` 是账号负责人配置的组合意图；全部填写时合计必须为 1。没有账号数据支持时可留 null，并把阈值依据写为 `unset`，不得用跨账号固定比例伪装基线。
