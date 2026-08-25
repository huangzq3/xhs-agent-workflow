# 开发与验证

## 目录

```text
xhs-workflow-pack/
├── skills/                  八个 Skill 及其脚本、契约、参考资料和测试
├── docs/demo/               README 演示所用的有效虚构 artifact 与渲染脚本
├── docs/images/             README 当前版本截图
├── install.sh               显式目标目录安装器
├── VERSION                  发行包版本
└── README.md                面向使用者的项目入口
```

`audit-evidence/` 是开发过程中的本地审计材料，不属于发行包，也不能替代当前版本演示或自动化测试。

## 常用命令

```bash
CORE=/absolute/path/to/skills/xhs-workflow
WORKSPACE=/absolute/path/to/xhs-data

python3 "$CORE/scripts/workflow_cli.py" init \
  --root "$WORKSPACE" --account-id account_slug \
  --display-name "账号显示名" --actor content-owner

python3 "$CORE/scripts/workflow_cli.py" new-run \
  --root "$WORKSPACE" --account-id account_slug \
  --objective "本轮明确目标" --run-type full_cycle --actor content-owner

python3 "$CORE/scripts/workflow_cli.py" validate /path/to/artifact.json
python3 "$CORE/scripts/workflow_cli.py" validate-workspace --root "$WORKSPACE"
python3 "$CORE/scripts/workflow_cli.py" render /path/to/artifact.json --output /path/to/review.html
python3 "$CORE/scripts/workflow_cli.py" audit-report --root "$WORKSPACE" --output /path/to/audit-report.html

python3 "$CORE/scripts/workflow_cli.py" approve /path/to/artifact.json \
  --gate G0 --actor content-owner --decision approved
```

文章审计与绑定：

```bash
python3 skills/article-audit/scripts/article_audit_cli.py validate \
  /path/to/article-audit.json --content /path/to/content.json

python3 "$CORE/scripts/workflow_cli.py" link-article-audit \
  --content /path/to/content.json --audit /path/to/article-audit.json \
  --actor orchestrator-agent
```

定时发布与实际上线时间：

```bash
python3 "$CORE/scripts/workflow_cli.py" set-schedule /path/to/publication.json \
  --scheduled-at 2026-08-26T20:00:00+08:00 \
  --expires-at 2026-08-26T20:30:00+08:00 \
  --method agent_wakeup --actor operator

python3 "$CORE/scripts/workflow_cli.py" scheduled-due --root "$WORKSPACE"

python3 "$CORE/scripts/portfolio_cli.py" record-actual-publish-time \
  --publication /path/to/publication.json \
  --inventory /path/to/inventory.json \
  --published-at 2026-08-26T20:03:00+08:00 \
  --source platform_metadata --evidence "创作中心记录" --actor operator
```

内部命令参数、阶段代码和英文枚举不得原样变成人工提问。运行助手应先翻译为业务语言。

## 自动化验证

```bash
python3 -m unittest discover -s skills/xhs-workflow/tests -v
python3 -m unittest discover -s skills/xhs-writer/tests -v
python3 -m unittest discover -s skills/article-audit/tests -v
PYTHONPYCACHEPREFIX=/tmp/xhs-workflow-pycache python3 -m compileall -q skills docs/demo
bash -n install.sh
```

自动化测试覆盖机器契约、定位证据引用、选题—稿件定位追踪、复盘逐项假设结果、G6 复盘—实验引用、复盘—实验—Persona 修订谱系、跨内容稳定化门禁、写审身份/上下文/只读分离、提示注入边界、高风险模型多样性、稿件与审计指纹失效、定稿与发布阻断、方向/策略/定位分层、发布防重、定时发布到点复核、防止过期补发、实际上线时间锚定的复盘、内容库存、HTML 转义、中文术语映射、原生生图交接、素材权利和去水印阻断。

## 重新生成 README 演示

演示源文件是通过当前机器校验的虚构 artifact，不得替换成未经校验的手写界面：

```bash
python3 docs/demo/render_demo.py --output-dir /tmp/xhs-readme-demo

"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1440,1400 \
  --screenshot=docs/images/v2.6-account-strategy.png \
  file:///tmp/xhs-readme-demo/account-strategy.html

"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1440,1400 \
  --screenshot=docs/images/v2.6-persona.png \
  file:///tmp/xhs-readme-demo/persona.html
```

截图后应人工核对：版本、中文术语、示例声明、首屏关键信息、桌面宽度与链接路径。Chrome 命令只是当前 macOS 开发环境的复现方式，不构成运行依赖。
