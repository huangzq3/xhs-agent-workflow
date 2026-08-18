# 飞书 Base 可选同步

飞书 Base 是 review JSON 的可选视图，不是事实源。同步失败时保留本地 JSON 并报告失败。

## 建议表

### Accounts

account_id、display_name、current_strategy_id、current_lifecycle_stage、current_persona_id、updated_at。这里的 current 只能由明确同步任务指定，不得按时间猜测。

### Content

inventory_item_artifact_id、content_artifact_id、account_id、strategy_artifact_id、content_objective、content_sequence_no、state、planned_publish_at、published_at、published_at_source、remote_url。

### MetricSnapshots

snapshot_artifact_id、content_artifact_id、captured_at、window、measurement_kind、checkpoint_days、published_at_anchor、window_started_at、window_ended_at、elapsed_hours、stock_metrics_json、flow_metrics_json、derived_metrics_json、trust_metrics_json、qualitative_metrics_json、missing_fields。

### Reviews

review_artifact_id、content_artifact_id、strategy_artifact_id、baseline_json、observations_json、hypotheses_json、lifecycle_assessment_json、persona_validation_json、trust_observations_json、long_tail_observations_json、limitations。

### Experiments

experiment_artifact_id、intervention_type、hypothesis、independent_variable、target_metric、window、state、result。

## 聚合规则

- stock_metrics 只取所选窗口的最新值，不求和。
- flow_metrics 只有在窗口不重叠时才能求和。
- 比率优先用总分子/总分母重新计算，不平均各行百分比。
- 所有看板必须按 account_id 和 format 过滤。
- 缺失值保留为空，不写成 0。

不得使用 AI、PPT 等固定主题枚举；赛道和内容支柱来自 persona。
