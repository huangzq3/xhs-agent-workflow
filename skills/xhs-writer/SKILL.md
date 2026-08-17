---
name: xhs-writer
description: 基于已确认的小红书账号运营策略、账号定位和选题创作图文、视频或纯文本，管理内容目标、事实、个人经历、素材权利、版本差异和当前 Agent 的原生生图交接。处理写小红书、制作卡片、视频分镜、改稿、配文和素材编排时使用。
---

# 小红书内容创作

把创作结果写入内部版本化记录，不得从展示页或“最新目录”反向猜测输入。面向内容负责人的提问、改稿说明和定稿交付遵守 [人工交互与审阅规范](../xhs-workflow/references/human-interface.md)，只生成中文 HTML 审阅页。

## 前置条件

1. 内部要求明确的工作区、本轮任务、已确认的账号运营策略、账号定位、选题报告和已选选题。
2. 校验所有记录属于同一账号并保持明确版本引用，不以模糊“最新版”查找。
3. 如内容负责人要求偏离 persona 或 topic，记录为本轮明确 override；重大定位变化转回 persona 修订。
4. 读取 run manifest 中的运行时能力快照。生图、处理边界、引用图处理和本地导出能力未确认时不得猜测。

## 工作流

1. 读取选题核心、受众需求、证据、风险、账号定位边界以及运营策略中的内容目标组合。
2. 为本篇明确一个业务目标：“吸引新受众”“建立信任”或“强化账号标签”；试运营内容在内部记录序号，不要求内容负责人理解内部枚举。
3. 选择图文、视频或纯文字，并按 [references/output-spec.md](references/output-spec.md) 生成对应结构。
4. 按 [references/humanizer-zh.md](references/humanizer-zh.md) 调整表达，但不得新增事实、数字、引语或亲身经历。
5. 建立 `claims`：标记事实、观点或假设，并关联来源。
6. 建立 `personal_experiences`：只有内容负责人提供且明确确认的经历才能使用。
7. 按 [references/image-sourcing.md](references/image-sourcing.md) 建立素材权利台账。权利尚未核对的素材不得进入内容定稿确认。
8. 需要生图时按 [references/image-generation.md](references/image-generation.md) 创建 `image_job` JSON，再调用当前 Agent 已展示的原生生图能力。不内置生图接口，不根据 Agent 品牌猜测工具名。
9. 使用参考图前核对启动时确认的外部处理范围、当前能力是否支持参考图，以及该素材是否已获外部处理许可。
10. 写入 `content` JSON，记录修订号和 `change_summary`，运行核心契约与素材校验。
11. 生成中文 HTML 预览和卡片图，用业务语言展示相对上一版的修改内容。
12. 请内容负责人完成“内容定稿确认”。任何改文、换图或调整顺序都会使旧确认失效；确认后由核心工作流建立或推进内容库存。

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
