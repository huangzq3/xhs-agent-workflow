---
name: xhs-workflow
description: 以 Agent 无关的运行时能力契约编排小红书账号战略、试运营定位、选题、创作、库存、发布、短期与长尾复盘和实验迭代；管理账号隔离、JSON 数据契约、Human-in-the-loop 门禁和审计。处理启动或继续运营流程、账号阶段判断、库存节奏、审批、发布恢复、长尾待办和工作区校验时使用。
---

# 小红书工作流编排

把 JSON artifact 作为唯一机器事实源。只把 Markdown 和 HTML 当作由 JSON 再生成的审阅视图；不得从展示文件反向提取数据驱动下一步。

## 不变量

1. 在 G0 前按 [references/runtime-capabilities.md](references/runtime-capabilities.md) 发现当前 Agent 的实际能力并写入 run manifest。不假定 Agent 品牌、Skill 安装路径或工具名称。
2. 在任何读写前明确 `workspace_root`、`account_id` 和 `run_id`。存在多个候选时停止并请内容负责人选择，不得猜测或使用跨账号“最新文件”。
3. 只消费符合机器 Schema 和跨字段约束的 JSON artifact。当 Python 3.9+ 可用时优先使用 `scripts/workflow_cli.py validate`。
4. 保留内容负责人明确输入及来源；不得让历史迭代建议覆盖当前明确要求。
5. 在高影响操作前验证对应人工门禁。自动生成内容不能代表人工批准。
6. 每次批准、拒绝、状态变化和异常都追加到 `audit/events.ndjson`。
7. 发布结果不明确时进入 `unknown`；未经人工判定不得自动重试。
8. 不得编造评论、指标、亲身经历、授权或测试结果。
9. 账号战略与内容运行分层：账号级 `account_strategy` 版本控制生命周期、内容目标、发布和测量策略；每个 run 只引用明确版本。
10. 所有节奏、库存和长尾数字来自账号战略或本轮人工配置；不得写死跨账号阈值。

## 标准流程

1. 建立账号隔离工作区；当 Python 辅助脚本可用时运行 `init`，否则按同一 JSON 契约建立。
2. 创建带 `run_type` 的本轮 manifest，完成能力发现和数据范围申明，再由内容负责人完成 G0。
3. `full_cycle` 先创建账号战略；内容类 run 必须显式引用已批准的战略和 persona。规则见 [references/strategy-lifecycle.md](references/strategy-lifecycle.md)。
4. 按 manifest 的 `current_stage` 调用对应执行 Skill。
5. 验证执行 Skill 产出的 JSON，将路径登记到 manifest；创作完成后进入 [内容库存](references/inventory-and-cadence.md)。
6. 用 `render` 生成 Markdown 或 HTML 供人工审阅。
7. 记录人工决定；只有批准后才能进入下一阶段。
8. 完成发布后按配置生成短期和长尾测量，再生成 review 和 experiment。

## 阶段与门禁

| 阶段 | 执行 Skill | 权威 artifact | 进入下一阶段所需门禁 |
|---|---|---|---|
| 账号与范围 | xhs-workflow | run_manifest | G0 运行时能力、账号、数据范围与外部处理授权 |
| 账号战略 | xhs-workflow | account_strategy | G1 阶段、目标、发布/库存/测量策略批准 |
| 定位 | xhs-persona | persona | G1 定位事实、试运营假设边界与验证计划批准 |
| 选题 | xhs-topic-report | topic_report | G2 选题与证据批准 |
| 创作 | xhs-writer | content | G3 内容、事实、素材权利批准 |
| 内容库存 | xhs-workflow | inventory_item | 达到 ready 需要有效 G3；发布例外并入 G4 |
| 发布 | xhs-publish | publication | G4 策略结果、发布预览与目标账号批准 |
| 采集与复盘 | xhs-content-review | metrics_snapshot、review | G5 短期、信任、长尾和隐私范围批准 |
| 实验与迭代 | xhs-iterate | experiment | G6 实验或定位/战略变更批准 |

详细职责、状态和回退规则见 [references/workflow-v2.md](references/workflow-v2.md) 与 [references/hitl-gates.md](references/hitl-gates.md)。运行时适配见 [references/runtime-capabilities.md](references/runtime-capabilities.md)；字段契约见 [references/data-contracts.md](references/data-contracts.md)；机器 Schema 见 [references/schemas/artifact.schema.json](references/schemas/artifact.schema.json)。

## 确定性命令

```bash
python3 scripts/workflow_cli.py init --root <workspace> --account-id <id> --display-name <name>
python3 scripts/workflow_cli.py new-run --root <workspace> --account-id <id> --objective <goal> --actor <human>
python3 scripts/workflow_cli.py validate <artifact.json>
python3 scripts/workflow_cli.py approve <artifact.json> --gate G1 --actor <human> --decision approved
python3 scripts/workflow_cli.py transition <publication.json> --to review_required --actor <agent> --reason <reason>
python3 scripts/workflow_cli.py render <artifact.json> --format markdown --output <artifact.md>
python3 scripts/workflow_cli.py validate-workspace --root <workspace>
python3 scripts/portfolio_cli.py new-strategy --run <run.json> --lifecycle-stage trial --stage-confidence low --persona-mode assumed --play-mode undecided --actor <human>
python3 scripts/portfolio_cli.py new-inventory --run <run.json> --strategy <strategy.json> --persona <persona.json> --objective trust --format text --working-title <title> --actor <agent>
python3 scripts/portfolio_cli.py check-policy --strategy <strategy.json> --inventory <inventory.json> --action publish --actor <agent>
python3 scripts/portfolio_cli.py long-tail-due --root <workspace>
```

命令是可选的确定性辅助器，不是对某个 Agent 的依赖。当运行时不能执行 Python 时，使用它已展示的 JSON/文件能力实现同一 Schema、状态机和 payload hash 规则；无法做到时降级为 `document_only`。不直接手改 `approvals`、发布状态或审计日志。

## 失败处理

- 输入缺失或不合法：保持当前阶段，记录错误，不生成伪造补全。
- 外部工具不可用：声明降级路径；没有安全降级时停止。
- 发布返回超时、页面状态不确定或远端 ID 缺失：写入 `unknown`。
- artifact 内容在批准后发生变化：原批准自动失效，重新渲染并请求批准。
- 定位或生命周期变更：分别新建 persona 或 account_strategy 修订版；review 只能提出建议，旧版不得静默覆盖。
