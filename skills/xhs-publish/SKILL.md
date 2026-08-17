---
name: xhs-publish
description: 对 ready 或 scheduled 的小红书库存项执行账号战略检查和发布预览，在人工 G4 后辅助一次发布尝试，并记录远端结果及发布后人工修改/删除决定。处理发布检查、定时发布、发布节奏、上传笔记、失败恢复、远端修改删除和结果核对时使用。
---

# 小红书发布

发布是外部状态变更。只接受明确路径和明确账号，不使用“今天最新”“上一个目录”等推断。

## 前置条件

1. 要求明确的 run manifest、account_strategy、ready/scheduled inventory_item、content JSON 和目标 `account_id`。
2. 校验库存引用、content 的有效 G3、素材权利和账号战略 G1；不得跳过库存层直接查找“最新 content”。
3. 读取 `authenticated_platform_control` 能力快照。只调用已展示且已授权的能力；不可用时改为账号负责人手动发布。
4. 核对当前实际发布界面的登录账号与 `target_account_id`。不一致时停止。
5. 登录、验证码、实名验证和账号切换始终由账号负责人完成。

## 工作流

1. 按 [references/publish-checklist.md](references/publish-checklist.md) 检查内容、素材、事实、平台限制和账号。
2. 按 [references/publishing-policy.md](references/publishing-policy.md) 运行策略检查并把 `policy_check` 同步到库存项和 publication。blocked 不得进入 G4；needs_human 必须在 G4 明确处理。
3. 创建 `publication` JSON，绑定战略、库存项和内容，状态从 `draft` 转为 `review_required`。
4. 生成最终预览，展示标题、正文、标签、素材顺序、可见范围、发布时间、目标账号、策略结果和内容 hash。
5. 请账号负责人完成 G4。批准必须绑定当前 publication payload；沉默不视为批准。
6. 使用核心状态契约从 `approved` 转为 `publishing`，每次 G4 只执行一次提交；记录自动能力 `capability_id` 或 `manual_by_account_owner`。
7. 平台明确返回远端 ID 或可验证 URL 时写入 `published`。
8. 平台明确拒绝且未创建内容时写入 `failed`。
9. 超时、页面崩溃、返回模糊或无法判断是否已创建时写入 `unknown`，停止自动重试。
10. 由账号负责人检查创作中心后，把 `unknown` 人工解决为 `published` 或 `failed`；随后推进库存项并生成配置化长尾计划。

## 禁止事项

- 未获 G4 不点击最终发布。
- 不绕过登录、验证码、风控或平台限制。
- 不自动修改或删除远端内容；发布后动作必须有单独的人工决定记录。
- 不在失败后直接重试；先检查是否重复发布并重新批准。
- 不把本地预览成功当作平台发布成功。
- 不通过裁剪水印宣称版权合规。

发布成功后登记 publication artifact 并推进 inventory_item；后续复盘必须引用其远端 ID，而不是从文本中提取 URL。
