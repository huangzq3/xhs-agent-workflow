---
name: xhs-persona
description: 在已批准账号战略下创建或修订可审计的小红书 persona JSON，区分试运营假设与已验证定位，定义受众、内容支柱、差异化、表达边界和验证计划。处理账号定位、人设定位、赛道选择、受众定义、试运营假设或定位修订时使用。
---

# 小红书账号定位

为一个明确的 `account_id` 生成 persona artifact。遵守 [xhs-workflow 数据契约](../xhs-workflow/references/data-contracts.md)，不得写入全局共享 persona 或覆盖其他账号。

## 前置条件

1. 要求明确的 `workspace_root`、`account_id`、`run_id`、run manifest 和已获 G1 的 account_strategy 路径。
2. 校验 manifest 与战略，并确认同账号 G0；persona 必须写入 `strategy_artifact_id`。
3. 修订定位时要求旧 persona 的明确路径；不得用“最新 persona”猜测。
4. 缺少会实质改变定位的信息时，请内容负责人确认；不得填入示例身份或推测个人经历。

## 工作流

1. 收集身份依据、目标、赛道、目标人群、差异化证据、明确不做事项、可用内容形式和隐私边界。
2. 把陈述分成已确认事实、偏好、假设和待验证项。试运营按 [references/trial-positioning.md](references/trial-positioning.md) 使用 `mode=assumed`、可证伪 hypotheses 与 validation_plan。
3. 如获授权，按 [references/competitor-research.md](references/competitor-research.md) 研究公开竞品；工具不可用时标注缺口，不生成虚假账号或指标。
4. 按 [references/persona-schema.md](references/persona-schema.md) 形成定位。每个内容支柱说明服务对象、价值和边界，不强制数量。
5. 写入 `persona` JSON，状态设为 `review_required`；路径使用：
   `artifacts/<account_id>/persona/<artifact_id>.json`。
6. 运行核心 CLI 校验并生成 Markdown 审阅视图。
7. 展示与上一修订版的差异、证据和未决问题，请内容负责人执行 persona 自身的 G1；该批准不代表画像已经验证。
8. G1 通过后登记到 run manifest。旧版本保留并标记 `superseded`，不得静默覆盖。

## 质量规则

- 定位陈述必须能指出受众、价值和差异，不使用空泛标签。
- `credentials`、案例和成就必须有用户输入或可核对来源。
- 竞品信息只用于观察空位和表达模式，不复制文案、视觉或身份。
- persona 只提供创作约束，不替代本轮明确输入。
- 从 assumed 改为 validated 必须由 review 证据支持，并建立新 revision、重新 G1。
- 不采集与定位无关的个人敏感信息。

## 输出

- 权威层：通过 V2 校验的 persona JSON。
- 审阅层：由同一 JSON 渲染的 Markdown；可选 HTML。
- 审计层：G1 决定、payload hash、修订关系和 artifact 登记事件。
