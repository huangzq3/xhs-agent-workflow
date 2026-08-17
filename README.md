# 小红书运营工作流 V2.2

这是一套 Agent 无关的小红书运营工作流：不预设内容负责人使用 TRAE、WorkBuddy、豆包、Codex、Claude Code 或其他某个 Agent。工作流只依赖当前运行时实际展示并经授权的能力。

核心原则：JSON 是唯一机器事实源；Markdown、HTML、在线表格和图表都是可再生成的展示或同步层。

## 架构

```text
账号级控制面：account_strategy.json ── G1 ──→ persona.json ── G1
                    │                         assumed / validated
                    └────────────────────┬────────────────────────┘
                                         ↓ 精确版本引用
内容运行面：run_manifest → topic_report ── G2 ──→ content ── G3
                                                          ↓
                                                  inventory_item
                                                          ↓ policy_check
                                      publication ── G4 ──→ 一次发布尝试
                                                          ↓
                                    短期/信任/长尾 snapshot → review
                                                                    ↓
                                                        experiment ── G6
```

下游 Skill 不解析 Markdown/HTML 获取机器输入。

## 七个 Skill

| Skill | 职责 | 权威输出 |
|---|---|---|
| xhs-workflow | 能力发现、账号战略、run、库存、审批、长尾待办、审计和渲染 | run_manifest、account_strategy、inventory_item |
| xhs-persona | 试运营假设、已验证定位与修订 | persona |
| xhs-topic-report | 证据化选题研究 | topic_report |
| xhs-writer | 图文/视频/文本创作、原生生图交接与素材权利 | content |
| xhs-publish | 策略检查、预览、一次发布尝试与发布后人工决定 | publication |
| xhs-content-review | 短期/信任/长尾快照、基线、阶段与画像诊断 | metrics_snapshot、review |
| xhs-iterate | 单变量实验和定位/战略变更建议 | experiment |

## 运行时能力契约

每个 run 都必须在 G0 前记录七项能力：

- 本地 JSON 读写；
- 追加式审计日志；
- 人工批准交互；
- 网页研究；
- 登录态平台操作；
- 原生生图；
- 指标采集。

每项使用 `available | unavailable | unknown` 表示，并保存实际 `capability_id`。不从 Agent 品牌推断工具是否存在。执行模式分为：

| 模式 | 含义 |
|---|---|
| full | JSON、追加审计和人工批准都可用 |
| assisted | JSON 和人工批准可用，部分自动化改用人工交接 |
| document_only | 只输出方案/交接包，不声称工作流已执行闭环 |

详细规则见 [运行时能力契约](skills/xhs-workflow/references/runtime-capabilities.md)。

## 安装或直接读取

不同 Agent 的 Skill 目录没有通用标准，因此安装器不猜测全局或项目路径。先从当前 Agent 的实际配置或文档确认 Skills 目录，再传入绝对路径：

```bash
bash install.sh --target /absolute/path/to/active-agent/skills

# 只预览操作
bash install.sh --target /absolute/path/to/active-agent/skills --dry-run

# 升级时先把已有 Skill 移到带时间戳的可恢复备份
bash install.sh --target /absolute/path/to/active-agent/skills --upgrade
```

如当前 Agent 支持直接读取本地目录，可不安装，直接交给 Agent 此包路径并从 `skills/xhs-workflow/SKILL.md` 开始。

## 辅助脚本

核心契约不绑定 Python；但是当前运行时能执行 Python 3.9+ 时，`workflow_cli.py` 可以确定性处理状态、门禁 hash、审批、审计和渲染，`portfolio_cli.py` 可以处理账号战略、库存、策略检查和长尾待办。

可选依赖：

- Pillow：本地文字卡、图片排版和生成结果验证；
- jsonschema：用标准 Draft 2020-12 校验器再校验一次。

```bash
python3 -m pip install -r requirements-optional.txt
```

工作流包不包含生图接口 SDK、密钥配置、端点或 HTTP 请求。

## 启动一轮工作流

以可选 Python 辅助器为例：

```bash
CORE=/absolute/path/to/skills/xhs-workflow
WORKSPACE=/absolute/path/to/xhs-data

python3 "$CORE/scripts/workflow_cli.py" init \
  --root "$WORKSPACE" \
  --account-id account_slug \
  --display-name "账号显示名" \
  --actor content-owner

python3 "$CORE/scripts/workflow_cli.py" new-run \
  --root "$WORKSPACE" \
  --account-id account_slug \
  --objective "本轮明确目标" \
  --run-type full_cycle \
  --actor content-owner
```

`new-run` 不猜测运行时，因此初始快照为 `unknown/undetermined`。运行 Agent 必须根据已展示的能力填写 `payload.runtime_capabilities`，由内容负责人补齐 `payload.data_scope`，渲染审阅后再批准 G0。

```bash
python3 "$CORE/scripts/workflow_cli.py" render /path/to/run.json \
  --format markdown --output /path/to/run.md

python3 "$CORE/scripts/workflow_cli.py" approve /path/to/run.json \
  --gate G0 --actor content-owner --decision approved \
  --notes "运行时能力、数据来源和外部处理范围已确认"
```

`full_cycle` 在 G0 后先进入 `strategy`。内容负责人填充账号战略中的阶段证据、目标和策略，再执行战略 G1；随后 xhs-persona 在该战略下建立定位。

后续单篇或批量内容 run 必须显式引用已经批准的账号战略与 persona：

```bash
python3 "$CORE/scripts/workflow_cli.py" new-run \
  --root "$WORKSPACE" --account-id account_slug \
  --objective "试运营第 1 篇" --run-type trial_content \
  --strategy artifacts/account_slug/account_strategy/account_strategy_x.json \
  --persona artifacts/account_slug/persona/persona_x.json \
  --content-sequence-no 1 --actor content-owner
```

每个执行 Skill 生成 JSON、校验、渲染，再等待对应门禁。不存在“按日期找最新版”的隐式交接。

## 原生生图

标准路径是：

1. xhs-writer 创建 `image_job.json`；
2. 运行 Agent 根据能力快照确认实际 `capability_id` 和 `processing_boundary=local|external`，边界未知时停止；
3. Codex 仅在当前确实有 `imagegen` 或等价能力时使用，其他 Agent 使用各自已展示的原生能力；
4. 结果导出到本地路径，校验尺寸、比例、媒体类型和 SHA-256；
5. 内容负责人在 G3 前审阅图片与权利台账。

原生生图能力缺失时，使用本地 `render_text_card.py` 或交付未执行的图片任务，不声称已生成。详见 [原生生图交接](skills/xhs-writer/references/image-generation.md)。

## Human-in-the-loop

| Gate | 人工决定 |
|---|---|
| G0 | 运行时能力、执行模式、账号、登录态、数据范围和外部处理 |
| G1（战略） | 生命周期、内容目标、库存/发布/测量策略 |
| G1（persona） | 定位事实、边界；试运营假设和验证计划 |
| G2 | 选题、证据和局限 |
| G3 | 内容事实、个人经历、生成结果、素材权利和版本 diff |
| G4 | 目标账号、最终预览、策略检查、例外和一次发布尝试 |
| G5 | 短期窗口、信任指标、长尾检查点、人工量表、隐私和同步目标 |
| G6 | 实验变量、指标、窗口、停止条件和定位/战略影响 |

批准记录绑定 payload SHA-256。重新生成、改文、换图、改数据范围或更换能力都会使相关批准失效。

## 发布状态机

```text
draft -> review_required -> approved -> publishing
publishing -> published | failed | unknown
unknown -> published | failed   # 仅人工核对后
failed -> review_required       # 重新审阅和批准
```

`unknown` 不得自动重试，避免重复发布。

内容库存状态机为 `idea → draft → review_ready → ready → scheduled → published → archived`，并允许带原因进入 `held`。ready/scheduled 需要有效 G3；发布后修改和删除必须另有人工决定。

## 工作区

```text
<workspace>/
├── workspace.json
├── accounts/<account_id>/account.json
├── runs/<run_id>/run.json
├── artifacts/<account_id>/<artifact_type>/<artifact_id>.json
├── assets/<account_id>/<content_id>/...
├── renders/<account_id>/<artifact_id>.md|html
└── audit/events.ndjson
```

账号战略与 persona 可被多个 run 精确引用；运行 artifact 仍绑定 `account_id` 和 `run_id`。禁止跨账号或按时间猜测“最新文件”。

完整机器 Schema：[artifact.schema.json](skills/xhs-workflow/references/schemas/artifact.schema.json)。

## 验证

```bash
python3 -m unittest discover -s skills/xhs-workflow/tests -v
python3 -m unittest discover -s skills/xhs-writer/tests -v

PYTHONPYCACHEPREFIX=/tmp/xhs-workflow-pycache \
  python3 -m compileall -q skills

bash -n install.sh
```

测试覆盖双层编排、试运营画像、revision superseded、十类 artifact、门禁 hash、库存 G3、配置化发布策略、G4 阻断、发布 `unknown` 人工恢复、长尾到期/完成、HTML 转义、目录递归素材扫描、原生生图 JSON 交接、本地图片验证、素材哈希和去水印阻断。

## V2.1 迁移到 V2.2

V2.2 对 run manifest 和所有领域 artifact 有破坏性变更：

- artifact `schema_version` 从 `2.1.0` 升级为 `2.2.0`；
- 新增 `account_strategy` 和 `inventory_item`，run 新增 `run_type` 与战略/画像精确引用；
- persona 区分 assumed/validated，并新增 hypotheses 与 validation_plan；
- topic/content/publication 显式引用战略，content 标记内容目标和可选序号；
- publication 增加策略检查与发布后人工动作；
- metrics/review 增加信任、长尾、生命周期和画像验证字段；
- 图片仍使用各 Agent 已展示的原生生图能力，不接入任何固定图片 API。

由于账号阶段、定位假设、阈值来源和历史内容目标不能安全推断，旧 artifact 不自动升级。由账号负责人建立首版 V2.2 账号战略和 persona，重新确认 G0/G1，再按需要把仍在运营的内容登记为库存项。
