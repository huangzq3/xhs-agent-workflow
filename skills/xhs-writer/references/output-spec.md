# 内容输出规格

## 图文

content.format 设为 image，并填写 cards。每张卡片至少包含：

- card_id
- role：cover、body 或 ending
- order
- text
- asset_refs
- accessibility_text

页面数量和字数根据内容复杂度决定，不强制固定数量。首要标准是移动端可读、信息层级清晰和正文一致。

## 视频

content.format 设为 video，并填写 shots。每个分镜至少包含：

- shot_id
- start_seconds、end_seconds
- visual
- narration
- on_screen_text
- asset_refs

时长应由内容目标和素材决定，不承诺完播率。

## 纯文本

content.format 设为 text。只保存 title、caption、hashtags 和 claims，不伪造 cards 或图片路径。

## 共通要求

- strategy_artifact_id、persona_artifact_id、topic_report_artifact_id 使用精确引用。
- 每篇设置一个 `content_objective`；试运营设置正整数 `content_sequence_no`，非序列内容可为 null。
- title、caption、hashtags 与选题交付一致。
- 所有事实主张关联来源或明确标为待确认。
- 所有素材存在、哈希一致、权利已验证。
- change_summary 能让内容负责人理解相对上一版的实质变化。
- `authorship` 记录写作者的角色类型、稳定身份、写作上下文和模型记录；机器作者的上下文不得为空。
- 作者交付的新修订将 `article_audit_ref` 设为 null；该引用只由 xhs-workflow 在独立审计契约通过后写入。
