# 原生生图交接

图片生成由当前 Agent 已展示的原生生图能力执行。本 Skill 只管理 JSON 任务、人工授权、本地产物验证和溯源，不配置密钥、端点、SDK 或网络请求。

## 路由规则

1. 读取 run manifest 的 `runtime_capabilities.capabilities.native_image_generation`。
2. 只在 `status=available` 且有实际 `capability_id` 时执行生图。
3. 确认 `processing_boundary`。边界是 `unknown` 时停止并请内容负责人核对；不把“Agent 原生”当作“本地私有”。
4. Codex 运行时若显式提供 `imagegen` 或等价原生能力，按该能力的 Skill/工具规则调用；其他 Agent 调用各自已展示的原生生图能力。
5. 不能仅根据 Agent 名称猜测工具是否存在。
6. 原生生图不可用时，使用本地文字卡、交付 prompt 与布局规格，或保留未执行任务。

## 标准流程

### 1. 创建 JSON 任务

```bash
python3 scripts/image_job.py create \
  --job /absolute/path/to/image_job.json \
  --output /absolute/path/to/card-01.png \
  --prompt "已通过内容与隐私检查的生图指令" \
  --aspect-ratio 3:4 \
  --processing-boundary local
```

使用外部处理的原生能力时，把最后一项改为以下两项；只在 G0 已列出该 `capability_id`、用途和数据类别后才能标记批准：

```bash
--processing-boundary external --external-processing-approved
```

需要引用图时再添加：

```bash
--reference /absolute/path/to/reference.png
```

本地处理引用图时不使用 `--external-processing-approved`，但仍要核对素材权利和个人数据。

### 2. 执行原生生图

运行 Agent 读取 `image_job.json.request`，把 prompt、比例和已批准引用图交给快照中记录的 `capability_id`。不使用本 Skill 之外的隐式接口备用路径。

如工具只返回会话附件或不透明结果引用，先记录：

```bash
python3 scripts/image_job.py mark-generated \
  --job /absolute/path/to/image_job.json \
  --capability-id <advertised-capability-id> \
  --runtime-name <confirmed-runtime-name> \
  --result-reference <attachment-or-result-reference>
```

此时状态是 `generated_pending_export`，还不是可发布素材。

### 3. 导出并完成

将图片保存到 `requested_output_path`，再执行：

```bash
python3 scripts/image_job.py finalize \
  --job /absolute/path/to/image_job.json \
  --capability-id <advertised-capability-id> \
  --runtime-name <confirmed-runtime-name>
```

`finalize` 只做本地图片完整性、媒体类型、尺寸、比例和 SHA-256 验证，不会呼叫生图服务，也不会静默裁剪。

### 4. 写入素材台账

只有 `status=completed` 的任务可用于构建 content asset：

- `uri`、`sha256` 和 `media_type` 来自 `image_job.output`；
- `rights_basis=generated`；
- `generation_job_id=image_job.job_id`；
- `generator_capability_id=image_job.execution.capability_id`；
- `rights_status` 先为 `pending`，由内容负责人在 G3 前核对为 `verified`。

机器契约见 [image-job.schema.json](image-job.schema.json)。
