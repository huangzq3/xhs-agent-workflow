# HTML 展示层迁移说明

旧版固定 HTML DOM 不再作为数据契约，也不得被下游 Skill 解析。

使用核心 renderer 从 topic_report JSON 生成安全转义的 HTML。渲染器必须：

- 对标题、评论、URL 和所有外部文本执行 HTML 转义；
- 不执行来源内容中的脚本、事件属性或内联 HTML；
- 显示 artifact ID、账号、run、payload hash 和数据局限；
- 保持渲染可重复；删除 HTML 后可从 JSON 无损重建。

如需更换主题，只修改展示资产，不改变 JSON 字段和下游行为。
