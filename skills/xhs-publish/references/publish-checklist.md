# 发布前检查

## 身份与契约

- [ ] account_id、strategy_artifact_id、inventory_item_artifact_id、content_artifact_id 明确且一致。
- [ ] 当前实际发布界面的账号与 target_account_id 一致。
- [ ] 发布路径已明确记录为已授权的 capability_id 或账号负责人手动操作。
- [ ] content JSON 通过 V2 校验。
- [ ] G3 对应当前 content payload hash。
- [ ] 库存状态为 ready 或 scheduled，且精确引用该 content。

## 内容

- [ ] 标题、正文、标签和素材顺序与预览一致。
- [ ] 事实、数字、引语和个人经历已核对。
- [ ] 没有未解决的高风险主张或隐私信息。
- [ ] 内容负责人已查看相对上一版的 diff。

## 素材

- [ ] 每个文件存在且 SHA-256 一致。
- [ ] rights_status 全部为 verified。
- [ ] 没有通过移除、裁剪或遮挡水印规避授权。
- [ ] 人脸、聊天记录、后台截图等已获公开许可。

## 发布意图

- [ ] 可见范围、发布时间和目标账号明确。
- [ ] publication 预览 hash 已生成。
- [ ] 已按当前 account_strategy 生成 policy_check；blocked 已停止，needs_human 已展示原因。
- [ ] G4 由账号负责人明确批准。
- [ ] 本次 G4 尚未消费为发布尝试。

## 结果

- [ ] 只有获得远端 ID 或可验证 URL 才标记 published。
- [ ] 明确失败标记 failed。
- [ ] 无法判断是否发布时标记 unknown 并停止重试。
- [ ] 发布成功后推进库存并按账号配置创建长尾检查点。
- [ ] 修改或删除远端内容时另行记录账号负责人的决定。
