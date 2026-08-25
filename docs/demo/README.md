# README 演示源

本目录保存 README 截图对应的机器源文件：

- `account-strategy.json`：Schema 2.4.0 账号策略，包含创作者方向。
- `persona.json`：Schema 2.4.0 persona，包含定位诊断、方向投射、定位生长状态和逐项假设。
- `render_demo.py`：调用当前 `workflow_cli.py` 校验并渲染中文 HTML。

所有业务内容均为虚构示例，不代表真实账号、真实经历、真实数据或运营效果。示例的用途是验证机器契约和人工界面之间的映射。

```bash
python3 docs/demo/render_demo.py --output-dir /tmp/xhs-readme-demo
```

脚本只读取本目录 JSON 和当前渲染器，输出到显式指定的目录；不会访问网络。
