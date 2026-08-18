---
name: xhs-workflow
description: 编排小红书账号策略、试运营定位、选题、创作、库存、立即或定时发布、从实际上线时间起算的短期与长尾复盘和迭代实验；管理账号隔离、机器数据契约、人工确认和审计。处理启动或继续运营流程、账号阶段判断、库存节奏、审批、发布恢复、复盘待办、人工审阅页和工作区校验时使用。
---

# 小红书工作流编排

内部使用结构化数据作为唯一机器事实源，面向内容负责人只使用其当前语言和中文可视化 HTML。不得把内部字段、阶段号、状态码、JSON 或命令输出直接交给内容负责人。完整规则见 [人工交互与审阅规范](references/human-interface.md)。

## 不变量

1. 启动前按 [运行时能力契约](references/runtime-capabilities.md) 核对当前运行工具实际提供且已授权的能力，不根据 Agent 品牌、安装路径或工具名称猜测。
2. 在任何读写前明确工作区、账号和本轮任务。存在多个候选时，用账号名称、任务目标和时间向内容负责人提问，不要求其选择内部编号。
3. 内部只消费符合 [数据契约](references/data-contracts.md) 的机器文件；人工审阅页不得成为下游机器输入。
4. 保留内容负责人本轮明确输入及来源；历史建议不能覆盖当前明确要求。
5. 高影响操作前必须获得对应的人工确认。自动生成内容不代表人工同意。
6. 每次确认、退回、状态变化和异常都追加到内部审计记录；不得把原始审计数据直接展示给内容负责人。
7. 无法确定是否发布成功时，向内容负责人说明“发布结果待核对”，停止自动重试。
8. 不得编造评论、指标、亲身经历、授权或测试结果。
9. 账号运营策略与单篇内容运行分层并保留版本，不静默使用所谓“最新版”。
10. 所有节奏、库存和长尾数字来自账号自己的策略或本轮人工配置，不写死跨账号阈值。

## 标准流程

1. 建立账号隔离工作区并创建本轮运营任务。
2. 核对当前工具能力、目标账号、允许的数据来源和外部处理范围，生成 HTML 后请求“启动与授权确认”。
3. 完整运营流程先形成账号运营策略，再形成试运营或已验证的账号定位。
4. 依次完成选题研究、内容制作、内容库存、发布、数据复盘和迭代实验。
5. 每个阶段先校验内部机器文件，再生成 HTML 审阅页；最终回复只提供业务摘要和 HTML 路径。
6. 内容负责人明确确认后才进入下一阶段；退回修改时保留原因并重新生成审阅页。
7. 发布支持立即发布和定时发布。定时方式必须来自当前环境可证明的能力，并同时设置明确时区和最晚允许执行时间；错过时间后不自动补发。
8. 只有核对平台实际已经上线并记录实际上线时间后，才按账号配置从该时间起生成短期和长尾复盘安排。
9. 需要查看整轮操作记录时生成中文 HTML 人工审计报告，不输出原始 JSON 或 NDJSON。

## 人工看到的流程

| 阶段 | 内容负责人审阅什么 | 确认后的动作 |
|---|---|---|
| 启动与授权 | 目标账号、工具能力、数据来源、登录状态、外部处理范围 | 启动本轮运营 |
| 账号运营策略 | 账号阶段、内容目标、发布节奏、库存与复盘规则 | 制定或修订账号定位 |
| 账号定位 | 身份、受众、差异化、边界和试运营验证计划 | 开始选题研究 |
| 选题确认 | 候选选题、证据、局限和风险 | 选择选题进入创作 |
| 内容定稿 | 标题、正文、图片或视频、事实与素材权利 | 加入可发布库存 |
| 发布前确认 | 目标账号、最终预览、立即或定时发布方式、明确时区、最晚执行时间和规则例外 | 只执行一次发布或排期尝试 |
| 数据采集范围 | 从实际上线时间起算的观察窗口、信任指标、长尾时间点和隐私范围 | 按真实内容生命周期采集并复盘数据 |
| 迭代实验 | 唯一调整项、指标、观察时间和停止条件 | 投入下一轮验证 |

内部阶段、状态与回退规则见 [流程与职责](references/workflow-v2.md) 和 [人工确认机制](references/hitl-gates.md)。内容库存规则见 [内容库存](references/inventory-and-cadence.md)。

## 执行器命令

以下命令只供运行助手使用，不得原样要求内容负责人填写参数：

```bash
python3 scripts/workflow_cli.py init --root <workspace> --account-id <id> --display-name <name>
python3 scripts/workflow_cli.py new-run --root <workspace> --account-id <id> --objective <goal> --actor <human>
python3 scripts/workflow_cli.py validate <artifact.json>
python3 scripts/workflow_cli.py approve <artifact.json> --gate G1 --actor <human> --decision approved
python3 scripts/workflow_cli.py render <artifact.json> --output <review.html>
python3 scripts/workflow_cli.py audit-report --root <workspace> --output <audit.html>
python3 scripts/workflow_cli.py validate-workspace --root <workspace>
python3 scripts/portfolio_cli.py new-strategy --run <run.json> --lifecycle-stage trial --stage-confidence low --persona-mode assumed --play-mode undecided --actor <human>
python3 scripts/portfolio_cli.py new-inventory --run <run.json> --strategy <strategy.json> --persona <persona.json> --objective trust --format text --working-title <title> --actor <agent>
python3 scripts/portfolio_cli.py check-policy --strategy <strategy.json> --inventory <inventory.json> --action publish --actor <agent>
python3 scripts/portfolio_cli.py long-tail-due --root <workspace>
```

当运行工具不能执行 Python 时，仍应遵守同一内部数据契约、状态变化和确认失效规则；无法安全执行时，向内容负责人说明“当前只能生成方案，不能声称已完成自动化闭环”。不得直接手改人工决定、发布状态或审计日志。

## 失败处理

- 输入缺失：保持当前步骤，用业务语言提出一个具体问题，不展示缺失字段名。
- 外部工具不可用：说明受影响的业务动作和可选人工方案；没有安全替代时停止。
- 发布结果不明确：说明“发布结果待核对”，请求内容负责人检查创作中心，不自动重试。
- 定时任务错过允许执行时间：说明“已错过允许执行时间”，停止自动补发，请账号负责人重新安排并确认。
- 已确认内容发生变化：说明改了什么、原确认为何失效，并重新生成 HTML 审阅页。
- 定位或账号阶段变化：建立新版本，先展示差异，再请求新的账号定位或运营策略确认。
