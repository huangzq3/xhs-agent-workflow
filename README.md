# 小红书运营工作流 V2.2.2

这是一套不绑定具体 Agent 产品的小红书运营工作流，覆盖账号运营策略、试运营定位、选题分析、内容创作、内容库存、发布、数据复盘和迭代实验。

V2.2.2 在中文人工体验基础上补齐发布和复盘时间闭环：

- 所有提问跟随内容负责人当前使用的语言，默认使用简体中文；
- 不再要求内容负责人理解阶段号、英文状态值或机器字段；
- 人工审阅与审计统一交付中文可视化 HTML；
- 不在对话或人工报告中输出原始 JSON；
- 内部机器数据契约保持不变，自动化交接不会因展示层调整而失效。
- 支持平台原生定时、运行工具到点唤醒和人工到点交接三种定时发布方式；
- 定时发布必须声明时区和最晚允许执行时间，错过后不自动补发；
- 短期与长尾复盘统一从平台确认的实际上线时间开始计算，不使用计划发布时间代替。

## 内容负责人看到的流程

| 阶段 | 主要产物 | 需要作出的决定 |
|---|---|---|
| 启动与授权 | 账号、当前工具能力、数据来源与外部处理范围 | 是否同意启动本轮运营 |
| 账号运营策略 | 账号阶段、内容目标、发布节奏、库存和复盘规则 | 是否按该策略运营 |
| 账号定位 | 身份、受众、差异化、边界和试运营验证计划 | 是否按该定位开展试运营 |
| 选题分析 | 候选选题、证据、判断把握度、风险与局限 | 选择哪个选题进入创作 |
| 内容创作 | 标题、正文、图片或视频、事实与素材权利 | 是否定稿 |
| 发布 | 目标账号、最终预览、立即或定时方式、时区、最晚执行时间和规则例外 | 是否授权一次发布或排期尝试 |
| 数据复盘 | 实际上线时间、观察周期、流量、信任、长尾表现和其他可能解释 | 是否接受复盘与下一步建议 |
| 迭代实验 | 唯一调整项、指标、观察时间和停止条件 | 是否投入下一轮验证 |

任何阶段被退回修改后，运行助手都应说明改动内容并重新生成 HTML。沉默不视为确认。

## 两层架构

工作流明确分离两类产物：

1. **机器层**：结构化数据、状态与追加式审计记录，用于 Skill 之间可靠交接。
2. **人工层**：安全转义的中文 HTML，用于阅读、判断、确认和审计。

HTML 不参与下游自动化解析。机器层也不得直接粘贴给内容负责人。这样既保留自动化稳定性，也避免人工界面被技术术语淹没。

## 七个 Skill

| Skill | 业务职责 |
|---|---|
| xhs-workflow | 启动流程、账号运营策略、内容库存、人工确认、审计和 HTML 渲染 |
| xhs-persona | 试运营定位、已验证定位与版本修订 |
| xhs-topic-report | 证据化选题研究、竞品拆解和候选比较 |
| xhs-writer | 图文、视频或纯文字创作，素材权利与原生生图交接 |
| xhs-publish | 发布规则检查、立即或定时发布、最终预览、一次尝试与实际上线结果核对 |
| xhs-content-review | 从实际上线时间起算的短期、信任与长尾数据复盘 |
| xhs-iterate | 单一调整项实验和账号定位或运营策略修订建议 |

## Agent 无关

工作流不预设运行工具是 TRAE、WorkBuddy、豆包、Codex、Claude Code 或其他 Agent。每轮开始时只核对当前环境实际展示并已经授权的能力：

- 本地保存工作数据；
- 追加审计记录；
- 接收人工确认；
- 网页资料研究；
- 使用已登录的平台页面；
- 使用当前工具的原生生图能力；
- 采集运营数据。

图片生成不接入固定图片 API，不包含 SDK、密钥或服务端点。Codex 在当前确实提供 imagegen 时使用 imagegen；其他 Agent 使用各自实际提供的原生生图能力。能力缺失时可生成本地文字卡，或交付待人工处理的图片任务。

## 安装或直接读取

不同 Agent 的 Skill 目录没有统一标准，因此安装器要求显式提供目标目录：

~~~bash
bash install.sh --target /absolute/path/to/active-agent/skills

# 只预览
bash install.sh --target /absolute/path/to/active-agent/skills --dry-run

# 升级前自动创建可恢复备份
bash install.sh --target /absolute/path/to/active-agent/skills --upgrade
~~~

如当前 Agent 支持直接读取目录，可直接提供本包路径，并要求从 `skills/xhs-workflow/SKILL.md` 开始。

推荐启动表达：

> 请为指定的小红书账号启动一轮完整运营流程。所有问题使用中文，每次只询问当前必须决定的事项；人工审阅和审计只输出可视化 HTML，不展示 JSON 或内部状态码。

## 人工审阅与审计

单项审阅页包含：

- 当前状态和账号；
- 当前需要决定的事项；
- 与决定有关的业务内容；
- 证据、风险和局限；
- 信息来源；
- 历史人工决定；
- 默认折叠的追溯信息。

人工审计报告按时间展示操作、决定与异常状态，并提供事件数量、人工决定数量和需要关注的状态。报告不包含机器原始数据。

## 人工参与与确认

本工作流中的人工确认具备以下约束：

- 可以确认通过、退回修改或暂不处理；
- 内容、图片、发布账号或数据范围变化后，旧确认自动失效；
- 发布前确认只授权一次发布尝试；
- 定时发布改变时间或执行方式后需要重新确认，错过最晚允许时间后不自动补发；
- 发布结果不明确时必须停止自动重试，并请内容负责人核对创作中心；
- 已排期不等于已上线；复盘周期只能从核对后的实际上线时间开始；
- 发布后的修改或删除需要新的人工决定；
- 账号阶段或定位变化只先形成建议，不能静默覆盖旧版本。

详细规范见 [人工交互与审阅规范](skills/xhs-workflow/references/human-interface.md) 和 [人工确认机制](skills/xhs-workflow/references/hitl-gates.md)。

<details>
<summary>运行助手与开发者说明</summary>

内部机器事实源仍为 JSON，Schema 版本仍是 2.2.0。V2.2.2 以向后兼容方式增加可选的定时发布、实际上线时间依据和复盘时间锚点字段。

常用内部命令：

~~~bash
CORE=/absolute/path/to/skills/xhs-workflow
WORKSPACE=/absolute/path/to/xhs-data

python3 "$CORE/scripts/workflow_cli.py" init --root "$WORKSPACE" --account-id account_slug --display-name "账号显示名" --actor content-owner

python3 "$CORE/scripts/workflow_cli.py" new-run --root "$WORKSPACE" --account-id account_slug --objective "本轮明确目标" --run-type full_cycle --actor content-owner

python3 "$CORE/scripts/workflow_cli.py" validate /path/to/artifact.json

python3 "$CORE/scripts/workflow_cli.py" render /path/to/artifact.json --output /path/to/review.html

python3 "$CORE/scripts/workflow_cli.py" audit-report --root "$WORKSPACE" --output /path/to/audit-report.html

python3 "$CORE/scripts/workflow_cli.py" set-schedule /path/to/publication.json --scheduled-at 2026-08-20T20:00:00+08:00 --expires-at 2026-08-20T20:30:00+08:00 --method agent_wakeup --actor operator

python3 "$CORE/scripts/workflow_cli.py" scheduled-due --root "$WORKSPACE"

python3 "$CORE/scripts/portfolio_cli.py" record-actual-publish-time --publication /path/to/publication.json --inventory /path/to/inventory.json --published-at 2026-08-20T20:03:00+08:00 --source platform_metadata --evidence "创作中心记录" --actor operator

python3 "$CORE/scripts/workflow_cli.py" approve /path/to/artifact.json --gate G0 --actor content-owner --decision approved
~~~

内部命令参数、阶段代码和英文枚举不得原样变成人工提问。运行助手必须先翻译为业务语言。

完整机器约束见 [artifact.schema.json](skills/xhs-workflow/references/schemas/artifact.schema.json)。

</details>

## 验证

~~~bash
python3 -m unittest discover -s skills/xhs-workflow/tests -v
python3 -m unittest discover -s skills/xhs-writer/tests -v

PYTHONPYCACHEPREFIX=/tmp/xhs-workflow-pycache python3 -m compileall -q skills

bash -n install.sh
~~~

测试覆盖机器契约、账号策略与定位分层、人工确认失效、发布防重、定时发布到点复核与防止过期补发、实际上线时间锚定的短期和长尾复盘、内容库存、HTML 安全转义、中文术语映射、人工审计 HTML、原生生图交接、素材权利和去水印阻断。
