# 图片与素材权利

每个发布素材都必须进入 rights ledger。

## 可接受的权利依据

- owned：账号负责人自行拍摄或制作。
- licensed：许可证明确覆盖当前发布用途。
- permission：权利人以可保存方式授权。
- public_domain：有可靠依据确认进入公有领域。
- generated：由生成工具创建，且输入素材和服务条款允许当前用途。

“网上找到”“带水印”“已经裁剪”“用于学习”都不是授权依据。

## 必填字段

~~~json
{
  "asset_id": "asset_...",
  "uri": "本地或受控存储路径",
  "sha256": "64位哈希",
  "media_type": "image/png",
  "rights_basis": "owned",
  "rights_status": "verified",
  "license_or_permission_ref": null,
  "contains_personal_data": false,
  "external_processing_approved": false,
  "generation_job_id": null,
  "generator_capability_id": null
}
~~~

## 处理规则

- 权利不明时换成自有、已许可或新生成素材。
- 不移除、裁剪、遮挡或重绘第三方水印来规避授权。
- 生成式素材也要记录 `generation_job_id`、实际 `generator_capability_id`、日期、输入来源和限制。
- 含人脸、聊天记录、后台截图或个人数据时，单独核对公开与外部处理许可。
- rights_status 不是 verified 时禁止进入 G3。
