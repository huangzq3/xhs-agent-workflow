---
name: xhs-writer
description: 基于已批准的小红书账号战略、persona 和选题 JSON 创作图文、视频或纯文本，标记内容目标与试运营序号，管理事实、经历、素材权利、版本差异和 Agent 原生生图交接，产出 content JSON。处理写小红书、制作卡片、视频分镜、改稿、配文和素材编排时使用。
---

# 小红书内容创作

把创作结果写入 `content` artifact。不得从 topic HTML、persona Markdown 或“最新目录”反向猜测输入。

## 前置条件

1. 要求明确的 `workspace_root`、run manifest、已获 G1 的 account_strategy 与 persona、已获 G2 的 topic_report 和选中的 `topic_id`。
2. 校验相同 `account_id`、显式战略/画像引用和本轮 topic_report；账号级 artifact 可跨 run 复用，不以模糊“最新版”查找。
3. 如内容负责人要求偏离 persona 或 topic，记录为本轮明确 override；重大定位变化转回 persona 修订。
4. 读取 run manifest 中的运行时能力快照。生图、处理边界、引用图处理和本地导出能力未确认时不得猜测。

## 工作流

1. 读取选题 premise、受众需求、证据、风险、persona 边界以及战略中的内容目标组合。
2. 为本篇明确 `content_objective=acquisition|trust|tag_strengthening`；试运营内容同时记录 `content_sequence_no`，不把顺序写在标题或文件名里充当机器数据。
3. 选择 `image`、`video` 或 `text`，并按 [references/output-spec.md](references/output-spec.md) 生成对应结构。
4. 按 [references/humanizer-zh.md](references/humanizer-zh.md) 调整表达，但不得新增事实、数字、引语或亲身经历。
5. 建立 `claims`：标记事实、观点或假设，并关联来源。
6. 建立 `personal_experiences`：只有内容负责人提供且明确确认的经历才能使用。
7. 按 [references/image-sourcing.md](references/image-sourcing.md) 建立素材权利台账。权利状态不是 `verified` 的素材不得进入 G3。
8. 需要生图时按 [references/image-generation.md](references/image-generation.md) 创建 `image_job` JSON，再调用当前 Agent 已展示的原生生图能力。不内置生图接口，不根据 Agent 品牌猜测工具名。
9. 使用引用图前核对 G0 `external_processing` 范围、能力是否支持引用图，以及素材级 `external_processing_approved`。
10. 写入 `content` JSON，记录修订号和 `change_summary`，运行核心契约与素材校验。
11. 从 JSON 生成 Markdown/HTML 预览和卡片图；展示相对上一版的 diff。
12. 请内容负责人完成 G3。任何改文、换图、调整顺序都会使旧 G3 失效；批准后由 xhs-workflow 建立或推进 inventory_item。

## 内容形式

- 图文：`cards` 记录页面角色、文本、资产引用和顺序。
- 视频：`shots` 记录时长、画面、口播、字幕和资产引用。
- 纯文本：不伪造卡片资产；明确记录平台可接受性由发布前检查确认。

## 安全与真实性

- 不声称“亲测”“用了几天”“涨粉多少”，除非来源中有内容负责人确认。
- 不对浏览量、点赞量或爆款概率作无依据承诺。
- 不去除第三方水印，不把裁剪、模糊或重绘视为取得授权。
- 生成素材仍要记录 `image_job`、实际 `capability_id`、输入来源和潜在权利限制。
- 医疗、金融、法律等高风险主张必须提示额外事实核查。

素材分析按 [references/material-intake.md](references/material-intake.md) 执行；生成图片按 [references/image-generation.md](references/image-generation.md) 执行，机器契约见 [references/image-job.schema.json](references/image-job.schema.json)。
