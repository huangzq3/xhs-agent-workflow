# 支持范围与真实边界

本文件区分设计目标、已经验证的本地能力和仍未验证的外部能力。Skill 名称、产品名称或文档声明本身不构成支持证据。

## 当前验证矩阵

截至 2026-08-25：

| 范围 | 状态 | 证据与边界 |
|---|---|---|
| macOS + Bash 安装器 | verified | `bash -n install.sh`、显式目标目录、dry-run 与升级备份路径由自动化测试覆盖 |
| Python 3.9.6 本地辅助器 | verified | 61 项单元测试全部执行通过；其中核心工作流40项、写作辅助器8项、独立审计13项。CLI 帮助与字节码编译通过；jsonschema 不是确定性跨字段校验的前提 |
| Python 3.14.6 本地辅助器 | verified | 同一组61项单元测试全部执行通过，无图片依赖跳过项；CLI 帮助与字节码编译通过 |
| jsonschema 4.25.1 | verified optional | 通过临时隔离依赖路径重跑核心40项与独立审计13项测试，并验证 `image_job` 1.1.0 标准 Schema，全部通过；未把该包变成运行必需依赖，CLI 仍保留内建跨字段校验 |
| Codex Skill 目录结构 | verified | 八个 Skill 通过官方 `quick_validate.py`；校验器所需 PyYAML 仅在临时目录中加载，未增加项目运行依赖。这不等同于已验证小红书平台自动化 |
| 定位生长闭环 | verified locally | G2/G3 锁定选题—稿件定位追踪，复盘逐项回应假设，G6 只接受复盘已评估假设，非首版 Persona G1 反查战略/复盘/实验修订谱系，稳定化 G1 再反查跨内容证据链；只证明本地契约与门禁 |
| Claude Code、TRAE、WorkBuddy、豆包及其他宿主 | unverified end-to-end | 文档与安装器不绑定产品，但每个宿主仍需在启动阶段核对真实工具能力和 Skill 目录 |
| Linux 安装与运行 | unverified | 安装脚本采用 Bash 与常见 Unix 工具，但当前发行验证未在 Linux 执行 |
| Windows 安装与运行 | unverified | 当前安装器不是 PowerShell 安装器 |
| 小红书登录态操作与发布 | runtime-dependent | 只有当前环境明确提供登录态控制、内容负责人授权且发布门禁有效时才能执行 |
| 定时唤醒 | runtime-dependent | 平台原生排期、宿主到点唤醒和人工交接是三种不同能力，不互相冒充 |
| AI Agent 原生生图与网页研究 | runtime-dependent | 生图仅使用当前 AI Agent 已经展示并授权的原生能力；缺失时交付 prompt、布局规格、未执行任务或人工素材任务，不启用本地栅格后备路径 |

## Python 与可选依赖

- Python 3.9+ 用于确定性 JSON 校验、状态操作、HTML 渲染、审计报告、素材清单和 Agent 生图结果登记。
- 没有 Python 时，Skill 仍可被运行助手读取，但机器契约需要由宿主文件能力维护；该路径不能宣称已经执行 Python 校验。
- jsonschema 增加标准 JSON Schema 校验；核心 CLI 仍保留不依赖该包的关键跨字段检查。

## 运行模式

启动阶段根据实际能力选择：

- **完整模式**：本地记录、人工确认、独立审计、研究、平台操作和数据采集均可用。
- **辅助模式**：保留策略、内容和审计，缺失动作以明确的人工交接完成。
- **文档模式**：只生成方向、定位、计划、稿件或检查清单，不宣称操作平台。

## 停止条件

出现以下情况时，高影响动作必须停止：

- 目标账号、稿件、素材顺序、排期或数据范围与已确认版本不一致；
- 登录态、发布结果或实际上线时间无法确认；
- 定时发布超过最晚允许执行时间；
- 独立文章审计缺失、失效或存在未解决的阻断项；
- 当前工具能力与启动阶段记录不一致；
- 证据不足以支持方向、定位或效果判断。

## 故障定位

- 安装问题先运行 `bash install.sh --target <绝对目录> --dry-run`。
- Python 辅助器问题先运行三个 CLI 的 `--help`。
- artifact 问题运行 `workflow_cli.py validate <artifact.json>`。
- 整个工作区问题运行 `workflow_cli.py validate-workspace --root <workspace>`。
- 平台结果不明确时停止重试，由内容负责人核对创作中心或平台记录。
