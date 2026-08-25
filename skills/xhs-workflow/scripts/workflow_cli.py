#!/usr/bin/env python3
"""Deterministic state, validation, approval, audit, and rendering for XHS Workflow V2.4."""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "2.4.0"
SCHEMA_V23 = "2.3.0"
SUPPORTED_SCHEMA_VERSIONS = {"2.2.0", SCHEMA_V23, SCHEMA_VERSION}
DIRECTION_SCHEMA_VERSIONS = {SCHEMA_V23, SCHEMA_VERSION}
ARTIFACT_TYPES = {
    "run_manifest",
    "account_strategy",
    "persona",
    "topic_report",
    "content",
    "article_audit",
    "inventory_item",
    "publication",
    "metrics_snapshot",
    "review",
    "experiment",
}
STATUSES = {
    "draft",
    "review_required",
    "approved",
    "rejected",
    "superseded",
    "collecting",
    "idea",
    "review_ready",
    "ready",
    "scheduled",
    "held",
    "publishing",
    "published",
    "failed",
    "unknown",
    "archived",
}
GATES = {f"G{i}" for i in range(7)}
GATE_BY_TYPE = {
    "run_manifest": {"G0", "G5"},
    "account_strategy": {"G1"},
    "persona": {"G1"},
    "topic_report": {"G2"},
    "content": {"G3"},
    "publication": {"G4"},
    "experiment": {"G6"},
}
REGISTER_RULES = {
    "account_strategy": ("account_strategy", "G1", "persona"),
    "persona": ("persona", "G1", "topics"),
    "topic_report": ("topic_report", "G2", "content"),
    "content": ("content", "G3", "inventory"),
    "inventory_item": ("inventory_item", None, "publication"),
    "publication": ("publication", "G4", "measurement"),
    "metrics_snapshot": ("metrics_snapshot", None, "measurement"),
    "review": ("review", None, "iteration"),
    "experiment": ("experiment", "G6", "complete"),
}
PAYLOAD_REQUIRED = {
    "run_manifest": {"objective", "run_type", "strategy_artifact_id", "persona_artifact_id", "content_sequence_no", "current_stage", "runtime_capabilities", "data_scope", "measurement_plan", "artifact_paths", "gate_status", "errors"},
    "account_strategy": {"revision", "supersedes_artifact_id", "lifecycle_stage", "stage_confidence", "persona_mode", "play_mode", "transition", "stage_evidence", "content_objectives", "publishing_policy", "inventory_policy", "measurement_policy", "experience_seed_refs", "limitations"},
    "persona": {"revision", "supersedes_artifact_id", "strategy_artifact_id", "mode", "hypotheses", "validation_plan", "identity", "niche", "audience", "differentiation", "content_pillars", "voice", "boundaries"},
    "topic_report": {"objective", "strategy_artifact_id", "persona_artifact_id", "research_mode", "requested_topics", "evidence", "candidates", "selected_topic_ids", "limitations"},
    "content": {"revision", "strategy_artifact_id", "persona_artifact_id", "topic_report_artifact_id", "topic_id", "content_objective", "content_sequence_no", "format", "title", "caption", "hashtags", "claims", "personal_experiences", "assets", "change_summary"},
    "article_audit": {"contract_version", "content_artifact_id", "content_revision", "target_uri", "content_sha256", "hash_mode", "author", "reviewer", "independence", "ruleset", "scope", "risk", "claim_inventory", "findings", "summary"},
    "inventory_item": {"revision", "strategy_artifact_id", "persona_artifact_id", "topic_report_artifact_id", "topic_id", "content_artifact_id", "content_artifact_path", "publication_artifact_id", "publication_artifact_path", "content_sequence_no", "content_objective", "format", "working_title", "same_topic_key", "state", "planned_publish_at", "hold_reason", "policy_check", "measurement_schedule", "history"},
    "publication": {"strategy_artifact_id", "inventory_item_artifact_id", "content_artifact_id", "target_account_id", "platform", "state", "visibility", "asset_order", "policy_check", "post_publish_actions", "attempts"},
    "metrics_snapshot": {"content_artifact_id", "publication_artifact_id", "format", "captured_at", "window", "measurement_kind", "checkpoint_days", "prior_snapshot_artifact_id", "stock_metrics", "flow_metrics", "derived_metrics", "trust_metrics", "qualitative_metrics", "missing_fields", "source"},
    "review": {"strategy_artifact_id", "content_artifact_id", "snapshot_artifact_ids", "baseline", "observations", "hypotheses", "diagnoses", "recommended_interventions", "lifecycle_assessment", "persona_validation", "trust_observations", "long_tail_observations", "limitations"},
    "experiment": {"review_artifact_id", "hypothesis", "intervention_type", "independent_variable", "control", "target_metric", "guardrails", "observation_window", "sample_size_plan", "stop_rule", "state", "strategy_change_proposal"},
}
PAYLOAD_REQUIRED_V23 = {
    "account_strategy": {"creator_direction"},
    "persona": {"positioning_diagnosis", "direction_alignment"},
}
PAYLOAD_REQUIRED_V24 = {
    "persona": {"positioning_state", "validation_evidence"},
    "content": {"positioning_trace"},
    "review": {"persona_artifact_id", "positioning_evidence_streams", "market_mirror"},
    "experiment": {
        "experiment_mode",
        "hypothesis_refs",
        "probe_question",
        "diversity_dimensions",
        "evidence_plan",
    },
}
REQUIRED_CAPABILITY_KEYS = {
    "local_json_storage",
    "append_audit_log",
    "human_approval",
    "web_research",
    "authenticated_platform_control",
    "native_image_generation",
    "metrics_collection",
}
OPTIONAL_CAPABILITY_KEYS = {"independent_agent_review", "scheduled_execution"}
CAPABILITY_KEYS = REQUIRED_CAPABILITY_KEYS | OPTIONAL_CAPABILITY_KEYS
CAPABILITY_STATUSES = {"available", "unavailable", "unknown"}
EXECUTION_MODES = {"undetermined", "full", "assisted", "document_only"}
RUN_TYPES = {
    "full_cycle",
    "strategy_review",
    "trial_content",
    "content_production",
    "batch_creation",
    "publication",
    "measurement",
    "long_tail_review",
}
LIFECYCLE_STAGES = {"trial", "scale", "stabilize", "flywheel"}
CONTENT_OBJECTIVES = {"acquisition", "trust", "tag_strengthening"}
THRESHOLD_BASES = {"account_baseline", "experience_seed", "manual", "unset"}
POSITIONING_PHASES = {"exploration", "consolidation", "stable_within_scope", "reopening"}
POSITIONING_HYPOTHESIS_COMPONENTS = {
    "audience",
    "problem",
    "value",
    "relationship",
    "trust",
    "proof",
    "memory",
    "content_engine",
    "business_fit",
    "creator_fit",
}
POSITIONING_HYPOTHESIS_STATUSES = {
    "proposed",
    "testing",
    "emerging",
    "provisionally_established",
    "under_review",
    "refuted",
}
POSITIONING_EVIDENCE_STREAMS = {
    "audience_resonance",
    "delivery_fidelity",
    "platform_distribution",
    "creator_fit",
    "business_fit",
}
REQUIRED_STABLE_EVIDENCE_STREAMS = {
    "audience_resonance",
    "delivery_fidelity",
    "platform_distribution",
    "creator_fit",
}
POSITIONING_RESULT_VERDICTS = {"supported", "refuted", "inconclusive", "not_tested"}
SCHEDULE_METHODS = {"platform_native", "agent_wakeup", "manual_handoff"}
PUBLISHED_AT_SOURCES = {"platform_metadata", "remote_page_verified", "human_confirmed"}
INVENTORY_STATES = {"idea", "draft", "review_ready", "ready", "scheduled", "held", "published", "archived"}
INVENTORY_TRANSITIONS = {
    "idea": {"draft", "archived"},
    "draft": {"review_ready", "held", "archived"},
    "review_ready": {"ready", "held", "draft"},
    "ready": {"scheduled", "held", "draft"},
    "scheduled": {"ready", "held", "published"},
    "held": {"draft", "review_ready", "ready", "archived"},
    "published": {"archived"},
    "archived": set(),
}
PUBLICATION_TRANSITIONS = {
    "draft": {"review_required"},
    "review_required": set(),
    "approved": {"publishing"},
    "publishing": {"published", "failed", "unknown"},
    "published": set(),
    "failed": {"review_required"},
    "unknown": {"published", "failed"},
}
APPROVAL_VOLATILE_FIELDS = {
    "state",
    "attempts",
    "remote_id",
    "remote_url",
    "published_at",
    "published_at_source",
    "schedule_reference",
    "execution_checks",
    "last_error",
    "post_publish_actions",
    "current_stage",
    "artifact_paths",
    "gate_status",
    "errors",
}
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{5,127}$")
ACCOUNT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
WINDOW_RE = re.compile(r"^(?:发布后)?\s*(\d+(?:\.\d+)?)\s*(h|d|小时|天)$", re.IGNORECASE)
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "schemas" / "artifact.schema.json"
ARTICLE_AUDIT_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "article-audit"
    / "scripts"
    / "article_audit_cli.py"
)
_ARTICLE_AUDIT_MODULE: Any | None = None

# Internal codes stay stable for machine handoffs. Everything below is the human
# presentation dictionary and must be used before showing a value to a person.
ARTIFACT_LABELS = {
    "run_manifest": "本轮运营任务",
    "account_strategy": "账号运营策略",
    "persona": "账号定位",
    "topic_report": "选题分析",
    "content": "内容稿件",
    "article_audit": "独立文章审计",
    "inventory_item": "内容库存项",
    "publication": "发布记录",
    "metrics_snapshot": "数据快照",
    "review": "内容复盘",
    "experiment": "迭代实验",
}
STATUS_LABELS = {
    "draft": "草稿",
    "review_required": "待人工确认",
    "approved": "已确认",
    "rejected": "已退回修改",
    "superseded": "已被新版本替代",
    "collecting": "采集中",
    "idea": "待构思",
    "review_ready": "待定稿",
    "ready": "可以发布",
    "scheduled": "已排期",
    "held": "已暂停",
    "publishing": "发布中",
    "published": "已发布",
    "failed": "发布失败",
    "unknown": "发布结果待核对",
    "archived": "已归档",
    "pending": "等待处理",
    "completed": "已完成",
    "active": "使用中",
}
GATE_LABELS = {
    "G0": "启动与授权确认",
    "G1": "账号方案确认",
    "G2": "选题确认",
    "G3": "内容定稿确认",
    "G4": "发布前确认",
    "G5": "数据采集范围确认",
    "G6": "迭代实验确认",
}
CONTEXTUAL_GATE_LABELS = {
    ("account_strategy", "G1"): "账号运营策略确认",
    ("persona", "G1"): "账号定位确认",
}
DECISION_LABELS = {
    "approved": "确认通过",
    "rejected": "退回修改",
    "revoked": "撤销此前确认",
    "allowed": "符合当前规则",
    "blocked": "当前规则不允许",
    "needs_human": "需要人工判断",
    "selected": "已选择",
    "candidate": "待选择",
    "prohibited": "禁止",
    "human_review_required": "必须人工确认",
}
VALUE_LABELS = {
    **STATUS_LABELS,
    **DECISION_LABELS,
    "assumed": "定位探索中（待验证）",
    "validated": "当前范围内已稳定",
    "exploration": "探索定位空间",
    "consolidation": "阶段性收敛",
    "stable_within_scope": "当前范围内稳定",
    "reopening": "重新检验定位",
    "proposed": "待开始验证",
    "testing": "验证中",
    "emerging": "正在形成",
    "provisionally_established": "阶段性成立",
    "under_review": "重新审视中",
    "refuted": "已被反向证据推翻",
    "explore": "探索未知",
    "confirm": "确认已有信号",
    "challenge": "主动寻找反证",
    "supported": "得到支持",
    "inconclusive": "暂不能判断",
    "not_tested": "未获得有效检验",
    "sufficient": "有效曝光充分",
    "insufficient": "有效曝光不足",
    "met": "内容已兑现承诺",
    "not_met": "内容未兑现承诺",
    "supportive": "形成支持",
    "concerning": "出现风险",
    "neutral": "暂无方向性",
    "audience_resonance": "受众共鸣",
    "delivery_fidelity": "内容兑现",
    "platform_distribution": "平台分发",
    "creator_fit": "创作者可持续性",
    "business_fit": "业务适配",
    "audience": "目标受众",
    "problem": "受众问题",
    "value": "核心价值",
    "relationship": "关系角色",
    "proof": "信任证据",
    "memory": "受众记忆",
    "content_engine": "内容引擎",
    "recall": "受众记忆",
    "follow_reason": "关注理由",
    "qualified_demand": "合格需求",
    "wrong_expectation": "错误期待",
    "nonresponse": "没有出现预期反应",
    "exploration_probe": "探索性探针",
    "controlled_optimization": "受控优化",
    "trial": "试运营期",
    "scale": "增长期",
    "stabilize": "稳定期",
    "flywheel": "复利运营期",
    "low": "较低",
    "medium": "中等",
    "high": "较高",
    "full": "完整执行",
    "assisted": "人机协作执行",
    "document_only": "仅生成方案",
    "undetermined": "尚未确定",
    "available": "可使用",
    "unavailable": "不可使用",
    "runtime_advertised": "由当前运行环境提供",
    "human_declared": "由内容负责人说明",
    "mixed": "综合确认",
    "complete": "已核对完成",
    "partial": "部分完成",
    "full_cycle": "完整运营流程",
    "strategy_review": "账号策略复核",
    "trial_content": "试运营内容",
    "content_production": "单篇内容制作",
    "batch_creation": "批量内容制作",
    "publication": "发布",
    "measurement": "数据采集",
    "long_tail_review": "长尾复盘",
    "trial_diversification": "试运营差异化验证",
    "focused": "专题聚焦研究",
    "trend_window": "趋势窗口研究",
    "scope": "确认账号与授权范围",
    "strategy": "制定账号策略",
    "persona": "确认账号定位",
    "topics": "研究并选择选题",
    "content": "制作内容",
    "inventory": "安排内容库存",
    "iteration": "制定迭代实验",
    "acquisition": "吸引新受众",
    "trust": "建立信任",
    "tag_strengthening": "强化账号标签",
    "trend": "趋势驱动",
    "ip": "个人品牌驱动",
    "hybrid": "组合运营",
    "undecided": "尚未决定",
    "image": "图文",
    "video": "视频",
    "text": "纯文字",
    "public": "公开",
    "private": "仅自己可见",
    "local": "仅在本地处理",
    "external": "会发送到外部服务处理",
    "initial": "首次数据采集",
    "long_tail": "长尾数据采集",
    "topic": "选题方向",
    "creative": "内容表达",
    "distribution": "发布与分发",
    "positioning": "账号定位",
    "manual": "由内容负责人设定",
    "account_baseline": "依据账号历史基线",
    "experience_seed": "依据已有经验样本",
    "unset": "尚未设置依据",
    "deferred": "暂缓处理",
    "owned": "自有素材",
    "licensed": "已获得许可",
    "permission": "已获得明确授权",
    "public_domain": "公共领域素材",
    "uploaded_asset": "内容负责人上传的素材",
    "fact": "事实陈述",
    "opinion": "观点",
    "hypothesis": "待验证假设",
    "human": "内容负责人",
    "agent": "运行助手",
    "passed": "审计通过",
    "audit_failed": "审计未通过",
    "human_decision_required": "需要内容负责人决定",
    "P0": "必须先解决",
    "P1": "定稿前应解决",
    "P2": "优化建议",
    "independent_full_text_review": "独立通读并重新提取主张",
    "canonical_json": "规范化内容指纹",
    "raw_bytes": "原始文件指纹",
    "article-audit-core": "通用文章审计核心规则",
    "payload.title": "标题",
    "payload.caption": "正文",
    "payload.hashtags": "话题标签",
    "payload.cards": "图文卡片",
    "payload.shots": "视频分镜",
    "fact_and_source": "事实与来源",
    "quote_and_attribution": "引语与归属",
    "logic_and_consistency": "逻辑与一致性",
    "structure_and_redundancy": "结构与重复",
    "language_and_terminology": "语言与术语",
    "cross_surface_consistency": "跨表面一致性",
    "uncertainty_and_decisions": "不确定信息与待决定事项",
    "custom_profile": "显式定制规则",
    "material": "关键主张",
    "non_material": "非关键主张",
    "verified": "已核实",
    "unverified": "无法核实",
    "contradicted": "与证据冲突",
    "not_applicable": "无需核实",
    "open": "尚未解决",
    "resolved": "已经解决",
    "platform_native": "使用平台原生定时发布",
    "agent_wakeup": "由当前运行工具到点唤醒执行",
    "manual_handoff": "由账号负责人到点手动发布",
    "platform_metadata": "平台记录的上线时间",
    "remote_page_verified": "通过已上线页面核对",
    "human_confirmed": "由账号负责人核对确认",
    "due": "已到执行时间",
    "missed": "已错过允许执行时间",
    "awaiting_verification": "等待核对是否已上线",
    "awaiting_submission": "等待提交平台排期",
    "initial_definition": "首次建立定位",
    "foundation_unclear": "定位底座不清",
    "delivery_inconsistent": "内容兑现不稳定",
    "wrong_audience": "持续吸引错误人群",
    "evidence_insufficient": "证据不足，暂不改定位",
    "create": "建立定位",
    "revise": "修订定位",
    "keep": "保留当前定位",
    "test_first": "先补充验证",
}
CAPABILITY_LABELS = {
    "local_json_storage": "本地保存工作数据",
    "append_audit_log": "追加审计记录",
    "human_approval": "接收人工确认",
    "independent_agent_review": "启动独立上下文的只读文章审计",
    "web_research": "网页资料研究",
    "authenticated_platform_control": "使用已登录的平台页面",
    "native_image_generation": "使用当前工具的原生生图能力",
    "metrics_collection": "采集运营数据",
    "scheduled_execution": "按指定时间唤醒并执行任务",
}
FIELD_LABELS = {
    "objective": "本轮目标",
    "run_type": "任务类型",
    "current_stage": "当前进度",
    "runtime_capabilities": "当前工具能力",
    "runtime_name": "运行工具",
    "captured_at": "记录时间",
    "capability_source": "能力确认来源",
    "discovery_status": "核对进度",
    "execution_mode": "执行方式",
    "capabilities": "能力清单",
    "capability_id": "能力记录",
    "processing_boundary": "数据处理范围",
    "supports_reference_images": "是否支持参考图",
    "returns_local_file": "是否返回本地文件",
    "notes": "备注",
    "data_scope": "数据使用范围",
    "allowed_sources": "允许的数据来源",
    "external_processing": "允许的外部处理",
    "personal_data": "涉及的个人信息",
    "data_categories": "数据类别",
    "purpose": "用途",
    "constraints": "限制条件",
    "measurement_plan": "数据复盘计划",
    "snapshot_windows": "观察时间窗口",
    "trust_metrics": "信任指标",
    "long_tail_checkpoints_days": "长尾复盘时间点（天）",
    "qualitative_rubric_refs": "人工评价标准",
    "errors": "阻塞问题",
    "revision": "版本",
    "supersedes_artifact_id": "替代的旧版本",
    "lifecycle_stage": "账号所处阶段",
    "stage_confidence": "阶段判断把握度",
    "persona_mode": "定位成熟度",
    "play_mode": "运营方式",
    "transition": "阶段变化依据",
    "from_stage": "原阶段",
    "rationale": "判断理由",
    "evidence_refs": "证据记录",
    "alternative_explanations": "其他可能解释",
    "stage_evidence": "阶段证据",
    "signal_id": "证据信号",
    "observation": "观察到的现象",
    "confidence": "判断把握度",
    "content_objectives": "内容目标组合",
    "target_share": "计划占比",
    "seed_ref": "参考样本",
    "publishing_policy": "发布规则",
    "inventory_policy": "内容库存规则",
    "measurement_policy": "数据复盘规则",
    "minimum_observation_hours": "发布后最短观察时间（小时）",
    "same_topic_cooldown_hours": "同主题间隔（小时）",
    "breakout_hold_hours": "高表现内容保护期（小时）",
    "threshold_basis": "规则依据",
    "exceptions_require_human": "例外是否必须人工确认",
    "modification_policy": "发布后修改规则",
    "deletion_policy": "发布后删除规则",
    "target_coverage_days": "库存覆盖天数",
    "target_ready_items": "可发布内容目标数量",
    "experience_seed_refs": "经验样本",
    "limitations": "已知局限",
    "creator_direction": "创作者长期方向",
    "primary_90_day_outcome": "90 天唯一主要结果",
    "business_destination": "长期业务或用途去向",
    "audience_business_fit": "受众与业务承接关系",
    "current_value": "当前价值",
    "future_value": "持续关注价值",
    "relationship_posture": "与受众的关系姿态",
    "trust_engine": "信任形成方式",
    "content_engine": "可持续内容来源",
    "memory_assets": "账号记忆资产",
    "supporting": "辅助记忆资产",
    "red_lines": "创作者表达红线",
    "assumptions": "当前假设",
    "unknowns": "仍待验证",
    "mode": "定位状态",
    "positioning_diagnosis": "定位问题判断",
    "diagnosis_type": "当前问题类型",
    "recommended_action": "建议动作",
    "direction_alignment": "创作者方向在本账号的落地",
    "account_role": "本账号承担的角色",
    "account_current_value": "本账号提供的当前价值",
    "account_future_value": "本账号提供的持续价值",
    "relationship_expression": "关系姿态如何被看见",
    "trust_expression": "信任如何被证明",
    "content_engine_expression": "内容来源如何持续",
    "memory_asset_expression": "主记忆资产如何出现",
    "business_connection": "与业务去向的连接",
    "tensions": "当前冲突与取舍",
    "hypotheses": "待验证假设",
    "hypothesis_id": "假设编号",
    "component": "定位组成部分",
    "statement": "假设内容",
    "observable_implication": "成立时应观察到什么",
    "falsification_signal": "什么现象会推翻它",
    "counter_evidence_refs": "反向证据",
    "review_by": "下次复核时间",
    "positioning_state": "定位生长状态",
    "phase": "当前生长阶段",
    "stable_core": "暂时保持稳定的核心",
    "open_questions": "仍待回答的问题",
    "anti_audience": "不主动吸引的人群",
    "anti_positioning": "不希望形成的账号认知",
    "validation_evidence": "定位收敛证据",
    "review_artifact_refs": "复盘记录",
    "experiment_artifact_refs": "已批准的迭代实验",
    "content_artifact_refs": "共同支持的内容",
    "snapshot_artifact_refs": "数据快照",
    "evidence_streams_covered": "已覆盖证据维度",
    "counter_evidence_reviewed": "是否复核反向证据",
    "reviewed_at": "本次复核时间",
    "validation_plan": "验证计划",
    "sample_target": "计划验证样本数",
    "diversity_dimensions": "需要覆盖的差异维度",
    "success_signals": "支持该定位的信号",
    "stop_conditions": "停止或调整条件",
    "identity": "账号身份与定位",
    "display_name": "账号名称",
    "positioning_statement": "当前定位工作假设",
    "credentials": "可核对的背景依据",
    "niche": "当前探索的问题空间",
    "primary": "当前主要问题空间",
    "subtopics": "细分方向",
    "formats": "内容形式",
    "audience": "目标受众",
    "segment_id": "受众分组",
    "name": "名称",
    "jobs": "希望完成的任务",
    "pains": "主要问题",
    "desired_outcomes": "期望结果",
    "differentiation": "差异化价值",
    "value_proposition": "能提供的独特价值",
    "proof": "支持证据",
    "non_goals": "明确不做",
    "content_pillars": "内容支柱",
    "pillar_id": "内容支柱编号",
    "audience_segment_refs": "服务的受众分组",
    "audience_job": "服务的具体任务",
    "value_delivered": "交付的稳定价值",
    "proof_role": "承担的信任证明",
    "memory_asset": "本篇强化的记忆资产",
    "hypothesis_refs": "关联的待验证假设",
    "positioning_trace": "本篇定位验证任务",
    "persona_revision": "定位版本",
    "probe_type": "验证角色",
    "boundaries": "边界",
    "topic_seeds": "可尝试的选题方向",
    "voice": "表达风格",
    "traits": "风格特点",
    "do": "建议采用",
    "dont": "需要避免",
    "visual": "视觉方向",
    "principles": "设计原则",
    "research_mode": "选题研究方式",
    "requested_topics": "内容负责人提出的选题",
    "evidence": "证据",
    "evidence_id": "证据编号",
    "source_ref": "来源记录",
    "quote": "可核对原文",
    "quote_verified": "原文是否已核对",
    "metrics": "相关数据",
    "candidates": "候选选题",
    "topic_id": "选题编号",
    "premise": "选题核心",
    "audience_need": "受众需求",
    "scores": "综合评分",
    "content_angles": "可执行角度",
    "risks": "风险与反证",
    "decision": "当前决定",
    "selected_topic_ids": "已选择的选题",
    "content_objective": "本篇内容目标",
    "content_sequence_no": "试运营内容序号",
    "format": "内容形式",
    "title": "标题",
    "caption": "正文",
    "hashtags": "话题标签",
    "claims": "事实与观点核对",
    "claim_id": "核对项编号",
    "text": "内容",
    "kind": "类型",
    "source_refs": "来源记录",
    "verification_status": "核对状态",
    "personal_experiences": "个人经历",
    "assets": "素材",
    "asset_id": "素材编号",
    "uri": "素材位置",
    "media_type": "素材类型",
    "rights_status": "权利核对状态",
    "rights_basis": "权利依据",
    "license_or_permission_ref": "授权记录",
    "contains_personal_data": "是否包含个人信息",
    "external_processing_approved": "是否同意外部处理",
    "generation_job_id": "生成任务记录",
    "generator_capability_id": "使用的生成能力",
    "change_summary": "本次修改摘要",
    "safety_notes": "安全提醒",
    "authorship": "稿件作者身份",
    "article_audit_ref": "独立审计引用",
    "contract_version": "审计契约版本",
    "content_artifact_id": "被审计稿件",
    "content_revision": "被审计稿件版本",
    "target_uri": "被审计稿件位置",
    "content_sha256": "被审计内容指纹",
    "hash_mode": "指纹计算方式",
    "author": "稿件作者",
    "reviewer": "独立审计者",
    "context_id": "独立上下文记录",
    "model_id": "模型记录",
    "independence": "写审分离证明",
    "separate_agent": "是否使用不同 Agent",
    "separate_context": "是否使用全新上下文",
    "read_only": "是否保持只读",
    "prompt_injection_treated_as_data": "是否把材料指令仅作为数据",
    "ruleset": "审计规则集",
    "ruleset_id": "规则集名称",
    "version": "规则集版本",
    "core_dimensions": "通用审计维度",
    "custom_profile_refs": "显式定制规则",
    "scope": "审计覆盖范围",
    "surface_paths": "已审阅的最终呈现表面",
    "risk": "内容风险判断",
    "level": "风险等级",
    "model_diversity_used": "是否使用不同模型复核",
    "claim_inventory": "独立提取的主张清单",
    "method": "提取方法",
    "coverage_notes": "覆盖说明",
    "materiality": "主张重要程度",
    "surface_path": "内容位置",
    "findings": "审计发现",
    "finding_id": "问题编号",
    "severity": "问题等级",
    "dimension": "审计维度",
    "locator": "原文位置",
    "excerpt": "相关原文",
    "issue": "问题说明",
    "claim_refs": "关联主张",
    "recommendation": "修订方向",
    "summary": "审计结论",
    "verdict": "审计状态",
    "counts": "尚未解决的问题数量",
    "artifact_path": "审计记录位置",
    "payload_sha256": "审计记录指纹",
    "cards": "图文卡片",
    "shots": "视频分镜",
    "working_title": "工作标题",
    "same_topic_key": "同主题识别",
    "state": "当前状态",
    "planned_publish_at": "计划发布时间",
    "hold_reason": "暂停原因",
    "policy_check": "规则检查",
    "checked_at": "检查时间",
    "action": "操作",
    "reasons": "判断依据",
    "measurement_schedule": "后续复盘安排",
    "schedule_id": "复盘周期编号",
    "anchor_published_at": "复盘起算时间",
    "checkpoint_days": "发布后第几天复盘",
    "due_at": "应完成时间",
    "completed_at": "完成时间",
    "history": "状态变化记录",
    "from": "原状态",
    "to": "新状态",
    "at": "时间",
    "actor_id": "角色标识",
    "actor_type": "操作角色",
    "reason": "原因",
    "target_account_id": "目标账号",
    "platform": "发布平台",
    "visibility": "可见范围",
    "scheduled_at": "定时发布时间",
    "schedule_expires_at": "最晚允许执行时间",
    "schedule_method": "定时发布方式",
    "schedule_reference": "定时任务或平台排期凭据",
    "execution_checks": "到点执行前复核",
    "asset_order": "素材顺序",
    "post_publish_actions": "发布后的人工决定",
    "attempts": "发布尝试记录",
    "remote_id": "平台内容编号",
    "remote_url": "平台链接",
    "published_at": "实际上线时间",
    "published_at_source": "实际上线时间依据",
    "last_error": "最近一次问题",
    "window": "观察窗口",
    "published_at_anchor": "复盘起算时间",
    "window_started_at": "观察开始时间",
    "window_ended_at": "观察结束时间",
    "elapsed_hours": "上线后已观察小时数",
    "measurement_kind": "采集类型",
    "prior_snapshot_artifact_id": "上一份数据快照",
    "stock_metrics": "当前累计数据",
    "flow_metrics": "本观察期新增数据",
    "derived_metrics": "计算指标",
    "qualitative_metrics": "人工评价",
    "missing_fields": "暂缺数据",
    "source": "数据来源",
    "metric": "指标",
    "value": "数值",
    "rubric_ref": "评价标准",
    "assessed_by": "评价人",
    "baseline": "对比基线",
    "time_context": "复盘时间轴",
    "windows": "本次使用的观察周期",
    "observations": "数据直接支持的观察",
    "diagnoses": "暂定判断",
    "recommended_interventions": "建议尝试的行动",
    "lifecycle_assessment": "账号阶段复核",
    "current_stage": "当前进度",
    "proposed_stage": "建议阶段",
    "requires_human_confirmation": "是否需要人工确认",
    "persona_validation": "定位验证情况",
    "hypothesis_results": "假设验证结果",
    "proposed_mode": "建议的定位状态",
    "positioning_evidence_streams": "定位证据全景",
    "market_mirror": "受众如何描述账号",
    "signal_type": "受众信号类型",
    "audience_language": "受众使用的原话或概括",
    "delivery_fidelity": "内容是否兑现定位承诺",
    "qualified_exposure": "是否获得有效曝光",
    "content_artifact_ids": "关联内容",
    "snapshot_artifact_ids": "关联数据快照",
    "revision_recommended": "是否建议修订定位",
    "trust_observations": "信任表现观察",
    "long_tail_observations": "长尾表现观察",
    "review_artifact_id": "复盘记录",
    "hypothesis": "本次实验假设",
    "experiment_mode": "实验方式",
    "probe_question": "本轮要回答的问题",
    "diversity_dimensions": "探索差异维度",
    "evidence_plan": "证据采集计划",
    "required_evidence_streams": "需要采集的证据维度",
    "qualified_exposure_rule": "有效曝光判断规则",
    "delivery_fidelity_rule": "内容兑现判断规则",
    "intervention_type": "实验方向",
    "independent_variable": "唯一调整项",
    "control": "保持不变的部分",
    "target_metric": "目标指标",
    "guardrails": "保护指标与边界",
    "observation_window": "观察时间",
    "sample_size_plan": "样本计划",
    "stop_rule": "停止条件",
    "result": "实验结果",
    "persona_change_proposal": "账号定位修订建议",
    "target_hypothesis_ids": "建议作用的定位假设",
    "requires_new_persona_revision": "是否必须建立新定位版本",
    "migration_actions": "账号表达迁移动作",
    "strategy_change_proposal": "账号策略修订建议",
}
METRIC_LABELS = {
    "profile_visit_rate": "主页访问率",
    "follow_rate": "关注转化率",
    "click_rate": "点击率",
    "like_count": "点赞数",
    "collect_count": "收藏数",
    "comment_count": "评论数",
    "share_count": "分享数",
    "view_count": "浏览量",
}
EVENT_LABELS = {
    "account_initialized": "建立账号工作区",
    "run_created": "创建本轮运营任务",
    "account_strategy_created": "创建账号运营策略草案",
    "inventory_created": "加入内容库存",
    "inventory_transition": "更新内容库存状态",
    "publishing_policy_checked": "完成发布规则检查",
    "post_publish_action_decided": "记录发布后的人工决定",
    "long_tail_checkpoint_completed": "完成长尾复盘检查点",
    "measurement_checkpoint_completed": "完成复盘周期",
    "measurement_schedule_created": "建立复盘周期",
    "publication_transition": "更新发布状态",
    "publication_scheduled": "设置定时发布",
    "publication_schedule_cleared": "取消定时发布",
    "published_time_confirmed": "核对实际上线时间",
    "artifact_superseded": "用新版本替代旧版本",
    "artifact_registered": "登记阶段产物",
    "article_audit_linked": "绑定独立文章审计",
    "gate_approved": "人工确认通过",
    "gate_rejected": "人工退回修改",
    "gate_revoked": "人工撤销确认",
}
REPORT_SECTIONS = {
    "run_manifest": [
        ("本轮任务", ("objective", "run_type", "current_stage", "content_sequence_no")),
        ("运行与授权", ("runtime_capabilities", "data_scope")),
        ("数据复盘计划", ("measurement_plan",)),
        ("需要处理的问题", ("errors",)),
    ],
    "account_strategy": [
        ("创作者方向", ("creator_direction",)),
        ("账号阶段", ("lifecycle_stage", "stage_confidence", "persona_mode", "play_mode", "transition", "stage_evidence")),
        ("内容目标", ("content_objectives",)),
        ("运营规则", ("publishing_policy", "inventory_policy", "measurement_policy")),
        ("依据与局限", ("experience_seed_refs", "limitations")),
    ],
    "persona": [
        ("定位问题判断", ("positioning_diagnosis",)),
        ("创作者方向落地", ("direction_alignment",)),
        ("定位生长状态", ("mode", "positioning_state", "validation_evidence")),
        ("当前账号表达", ("identity", "niche", "audience", "differentiation")),
        ("内容表达", ("content_pillars", "voice", "visual", "boundaries")),
        ("定位假设与验证", ("hypotheses", "validation_plan")),
    ],
    "topic_report": [
        ("选题任务", ("objective", "research_mode", "requested_topics")),
        ("候选与选择", ("candidates", "selected_topic_ids")),
        ("证据与局限", ("evidence", "limitations")),
    ],
    "content": [
        ("内容预览", ("title", "caption", "hashtags", "format", "content_objective", "content_sequence_no")),
        ("本篇定位验证任务", ("positioning_trace",)),
        ("画面与素材", ("cards", "shots", "assets")),
        ("真实性核对", ("claims", "personal_experiences", "safety_notes")),
        ("修改说明", ("change_summary",)),
    ],
    "article_audit": [
        ("审计结论", ("summary", "risk")),
        ("写审分离", ("independence",)),
        ("覆盖范围与规则", ("ruleset", "scope")),
        ("独立提取的主张", ("claim_inventory",)),
        ("审计发现", ("findings",)),
    ],
    "inventory_item": [
        ("库存安排", ("working_title", "state", "content_objective", "format", "planned_publish_at", "hold_reason")),
        ("发布规则检查", ("policy_check",)),
        ("后续复盘", ("measurement_schedule",)),
        ("状态记录", ("history",)),
    ],
    "publication": [
        ("发布安排", ("target_account_id", "platform", "state", "visibility", "scheduled_at", "schedule_expires_at", "schedule_method", "asset_order")),
        ("发布规则检查", ("policy_check", "execution_checks")),
        ("执行结果", ("attempts", "remote_url", "published_at", "published_at_source", "last_error")),
        ("发布后的人工决定", ("post_publish_actions",)),
    ],
    "metrics_snapshot": [
        ("观察周期", ("published_at_anchor", "window", "window_started_at", "window_ended_at", "elapsed_hours", "captured_at", "measurement_kind", "checkpoint_days")),
        ("数据来源", ("source",)),
        ("平台数据", ("stock_metrics", "flow_metrics", "derived_metrics", "trust_metrics")),
        ("人工评价与缺口", ("qualitative_metrics", "missing_fields")),
    ],
    "review": [
        ("复盘时间轴", ("time_context",)),
        ("对比基线与观察", ("baseline", "observations", "trust_observations", "long_tail_observations")),
        ("可能原因", ("hypotheses", "diagnoses")),
        ("下一步建议", ("recommended_interventions",)),
        ("定位证据全景", ("positioning_evidence_streams", "market_mirror")),
        ("账号阶段与定位复核", ("lifecycle_assessment", "persona_validation")),
        ("局限", ("limitations",)),
    ],
    "experiment": [
        ("实验目标", ("experiment_mode", "hypothesis", "hypothesis_refs", "intervention_type", "probe_question")),
        ("探索与控制", ("diversity_dimensions", "independent_variable", "control")),
        ("判断方式", ("evidence_plan", "target_metric", "guardrails", "observation_window", "sample_size_plan", "stop_rule")),
        ("当前结果与修订建议", ("state", "result", "persona_change_proposal", "strategy_change_proposal")),
    ],
}


class WorkflowError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    timestamp = datetime.now().astimezone().strftime("%Y%m%dt%H%M%S")
    return f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"JSON 无法解析：{path}:{exc.lineno}:{exc.colno} {exc.msg}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"顶层必须是 JSON object：{path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def article_audit_contract() -> Any:
    """Load the standalone article-audit contract without coupling writer logic to it."""
    global _ARTICLE_AUDIT_MODULE
    if _ARTICLE_AUDIT_MODULE is not None:
        return _ARTICLE_AUDIT_MODULE
    if not ARTICLE_AUDIT_MODULE_PATH.is_file():
        raise WorkflowError(
            "缺少独立文章审计契约；请确认 article-audit Skill 与 xhs-workflow 一起安装"
        )
    spec = importlib.util.spec_from_file_location(
        "xhs_article_audit_contract", ARTICLE_AUDIT_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise WorkflowError("无法加载独立文章审计契约")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _ARTICLE_AUDIT_MODULE = module
    return module


def approval_view(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: approval_view(item)
            for key, item in value.items()
            if key not in APPROVAL_VOLATILE_FIELDS
        }
    if isinstance(value, list):
        return [approval_view(item) for item in value]
    return value


def payload_hash(artifact: dict[str, Any], gate: str | None = None) -> str:
    raw_payload = artifact.get("payload", {})
    if artifact.get("artifact_type") == "run_manifest" and gate == "G0":
        raw_payload = {
            key: raw_payload.get(key)
            for key in ("objective", "run_type", "runtime_capabilities", "data_scope")
        }
    elif artifact.get("artifact_type") == "run_manifest" and gate == "G5":
        raw_payload = {
            key: raw_payload.get(key)
            for key in ("measurement_plan", "data_scope")
        }
    payload = approval_view(raw_payload)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def datetime_value(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise WorkflowError(f"{field} 必须是带时区的 ISO 8601 字符串")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkflowError(f"{field} 不是有效的 ISO 8601 时间：{value}") from exc
    if parsed.utcoffset() is None:
        raise WorkflowError(f"{field} 必须包含明确时区：{value}")
    return parsed


def parse_datetime(value: Any, field: str, errors: list[str]) -> None:
    try:
        datetime_value(value, field)
    except WorkflowError as exc:
        errors.append(str(exc))


def parse_window_seconds(value: Any, field: str = "观察窗口") -> int:
    if not isinstance(value, str):
        raise WorkflowError(f"{field} 必须使用小时或天表示，例如 24h、72h、发布后7天")
    match = WINDOW_RE.fullmatch(value.strip())
    if not match:
        raise WorkflowError(f"{field} 无法换算为上线后的时间周期：{value}")
    amount = float(match.group(1))
    if amount <= 0:
        raise WorkflowError(f"{field} 必须大于 0：{value}")
    unit = match.group(2).lower()
    seconds = amount * (86400 if unit in {"d", "天"} else 3600)
    if not seconds.is_integer():
        raise WorkflowError(f"{field} 换算后必须是整秒：{value}")
    return int(seconds)


def require_object(value: Any, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{field} 必须是 object")
        return {}
    return value


def require_list(value: Any, field: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{field} 必须是 array")
        return []
    return value


def require_nonempty_string_list(
    value: Any, field: str, errors: list[str]
) -> list[str]:
    items = require_list(value, field, errors)
    valid_items: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] 必须是非空字符串")
            continue
        valid_items.append(item.strip())
    return valid_items


def require_nonempty_text(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} 必须是非空字符串")
        return ""
    return value.strip()


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_positive_int_or_null(value: Any, field: str, errors: list[str]) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
        errors.append(f"{field} 必须是正整数或 null")


def validate_positioning_trace(value: Any, field: str, errors: list[str]) -> dict[str, Any]:
    trace = require_object(value, field, errors)
    revision = trace.get("persona_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision <= 0:
        errors.append(f"{field}.persona_revision 必须是正整数")
    for name in (
        "pillar_id",
        "audience_job",
        "value_delivered",
        "proof_role",
        "memory_asset",
    ):
        require_nonempty_text(trace.get(name), f"{field}.{name}", errors)
    for name in ("audience_segment_refs", "hypothesis_refs"):
        refs = require_nonempty_string_list(trace.get(name), f"{field}.{name}", errors)
        if not refs:
            errors.append(f"{field}.{name} 至少需要一项")
        if len(refs) != len(set(refs)):
            errors.append(f"{field}.{name} 不得重复")
    if trace.get("probe_type") not in {"explore", "confirm", "challenge"}:
        errors.append(f"{field}.probe_type 无效")
    return trace


def validate_policy_check(value: Any, field: str, errors: list[str]) -> None:
    if value is None:
        return
    check = require_object(value, field, errors)
    required = {"checked_at", "strategy_artifact_id", "action", "decision", "reasons"}
    missing = sorted(required - set(check))
    if missing:
        errors.append(f"{field} 缺少字段：" + ", ".join(missing))
    if check.get("checked_at"):
        parse_datetime(check.get("checked_at"), f"{field}.checked_at", errors)
    if check.get("action") not in {"publish", "modify", "delete"}:
        errors.append(f"{field}.action 无效")
    if check.get("decision") not in {"allowed", "blocked", "needs_human"}:
        errors.append(f"{field}.decision 无效")
    require_list(check.get("reasons"), f"{field}.reasons", errors)


def unknown_capability(*, image_generation: bool = False) -> dict[str, Any]:
    capability: dict[str, Any] = {
        "status": "unknown",
        "capability_id": None,
        "notes": [],
    }
    if image_generation:
        capability["processing_boundary"] = "unknown"
        capability["supports_reference_images"] = None
        capability["returns_local_file"] = None
    return capability


def default_runtime_capabilities(timestamp: str, runtime_name: str | None) -> dict[str, Any]:
    return {
        "runtime_name": runtime_name,
        "captured_at": timestamp,
        "capability_source": "unknown",
        "discovery_status": "pending",
        "execution_mode": "undetermined",
        "capabilities": {
            key: unknown_capability(image_generation=key == "native_image_generation")
            for key in sorted(CAPABILITY_KEYS)
        },
        "limitations": [],
    }


def effective_approval(artifact: dict[str, Any], gate: str) -> bool:
    current_hash = payload_hash(artifact, gate)
    approvals = artifact.get("approvals", [])
    if not isinstance(approvals, list):
        return False
    for approval in reversed(approvals):
        if not isinstance(approval, dict) or approval.get("gate") != gate:
            continue
        if approval.get("decision") != "approved":
            return False
        return approval.get("payload_sha256") == current_hash
    return False


def optional_json_schema_errors(artifact: dict[str, Any]) -> list[str]:
    """Run the bundled Draft 2020-12 schema when jsonschema is available."""
    try:
        import jsonschema
    except ImportError:
        return []
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(
            schema,
            format_checker=jsonschema.FormatChecker(),
        )
    except (OSError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
        return [f"无法加载 bundled JSON Schema：{exc}"]
    errors = []
    for error in sorted(validator.iter_errors(artifact), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"JSON Schema {path}: {error.message}")
    return errors


def validate_artifact(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "artifact_type",
        "artifact_id",
        "account_id",
        "run_id",
        "created_at",
        "updated_at",
        "status",
        "provenance",
        "approvals",
        "payload",
    }
    missing = sorted(required - set(artifact))
    if missing:
        errors.append("缺少顶层字段：" + ", ".join(missing))

    schema_version = artifact.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            "schema_version 必须是受支持版本："
            + ", ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
        )
    artifact_type = artifact.get("artifact_type")
    if artifact_type not in ARTIFACT_TYPES:
        errors.append(f"不支持的 artifact_type：{artifact_type}")
    artifact_id = artifact.get("artifact_id")
    if not isinstance(artifact_id, str) or not ID_RE.fullmatch(artifact_id):
        errors.append("artifact_id 格式无效")
    account_id = artifact.get("account_id")
    if not isinstance(account_id, str) or not ACCOUNT_RE.fullmatch(account_id):
        errors.append("account_id 格式无效")
    run_id = artifact.get("run_id")
    if run_id is not None and (not isinstance(run_id, str) or not run_id.startswith("run_") or not ID_RE.fullmatch(run_id)):
        errors.append("run_id 必须为 null 或 run_ 开头的稳定 ID")
    parse_datetime(artifact.get("created_at"), "created_at", errors)
    parse_datetime(artifact.get("updated_at"), "updated_at", errors)
    if artifact.get("status") not in STATUSES:
        errors.append(f"status 无效：{artifact.get('status')}")

    provenance = require_list(artifact.get("provenance"), "provenance", errors)
    for index, source in enumerate(provenance):
        if not isinstance(source, dict):
            errors.append(f"provenance[{index}] 必须是 object")
            continue
        for field in ("source_id", "kind", "captured_at", "summary"):
            if not source.get(field):
                errors.append(f"provenance[{index}] 缺少 {field}")
        if source.get("kind") in {"web_source", "platform_data"} and not source.get("url"):
            errors.append(f"provenance[{index}] 的 {source.get('kind')} 必须包含 url")
        if "quote" in source and source.get("quote_verified") is not True:
            errors.append(f"provenance[{index}] 含 quote 时必须 quote_verified=true")
        if source.get("captured_at"):
            parse_datetime(source.get("captured_at"), f"provenance[{index}].captured_at", errors)

    approvals = require_list(artifact.get("approvals"), "approvals", errors)
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict):
            errors.append(f"approvals[{index}] 必须是 object")
            continue
        if approval.get("gate") not in GATES:
            errors.append(f"approvals[{index}].gate 无效")
        if approval.get("decision") not in {"approved", "rejected", "revoked"}:
            errors.append(f"approvals[{index}].decision 无效")
        if approval.get("actor_type") != "human":
            errors.append(f"approvals[{index}] 只能由 human 作出")
        sha = approval.get("payload_sha256")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            errors.append(f"approvals[{index}].payload_sha256 无效")
        current_hash = payload_hash(artifact, approval.get("gate"))
        if approval.get("decision") == "approved" and sha != current_hash:
            later_same_gate = any(
                isinstance(item, dict) and item.get("gate") == approval.get("gate")
                for item in approvals[index + 1 :]
            )
            if not later_same_gate:
                errors.append(f"{approval.get('gate')} 批准已因 payload 变化失效")
        if approval.get("at"):
            parse_datetime(approval.get("at"), f"approvals[{index}].at", errors)

    payload = require_object(artifact.get("payload"), "payload", errors)
    if artifact_type in PAYLOAD_REQUIRED:
        missing_payload = sorted(PAYLOAD_REQUIRED[artifact_type] - set(payload))
        if missing_payload:
            errors.append("payload 缺少字段：" + ", ".join(missing_payload))
        if schema_version in DIRECTION_SCHEMA_VERSIONS:
            missing_v23 = sorted(PAYLOAD_REQUIRED_V23.get(artifact_type, set()) - set(payload))
            if missing_v23:
                errors.append("payload 缺少 V2.3 字段：" + ", ".join(missing_v23))
        if schema_version == SCHEMA_VERSION:
            missing_v24 = sorted(PAYLOAD_REQUIRED_V24.get(artifact_type, set()) - set(payload))
            if missing_v24:
                errors.append("payload 缺少 V2.4 字段：" + ", ".join(missing_v24))

    if artifact_type == "run_manifest":
        if payload.get("run_type") not in RUN_TYPES:
            errors.append("payload.run_type 无效")
        if payload.get("current_stage") not in {
            "scope", "strategy", "persona", "topics", "content", "inventory",
            "publication", "measurement", "iteration", "complete",
        }:
            errors.append("payload.current_stage 无效")
        for field in ("strategy_artifact_id", "persona_artifact_id"):
            value = payload.get(field)
            if value is not None and (not isinstance(value, str) or not value):
                errors.append(f"payload.{field} 必须是非空字符串或 null")
        validate_positive_int_or_null(
            payload.get("content_sequence_no"), "payload.content_sequence_no", errors
        )
        measurement_plan = require_object(payload.get("measurement_plan"), "payload.measurement_plan", errors)
        for field in ("snapshot_windows", "trust_metrics", "long_tail_checkpoints_days", "qualitative_rubric_refs"):
            require_list(measurement_plan.get(field), f"payload.measurement_plan.{field}", errors)
        checkpoints = measurement_plan.get("long_tail_checkpoints_days", [])
        if isinstance(checkpoints, list):
            if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in checkpoints):
                errors.append("payload.measurement_plan.long_tail_checkpoints_days 只能包含正整数")
            if len(checkpoints) != len(set(checkpoints)):
                errors.append("payload.measurement_plan.long_tail_checkpoints_days 不得重复")
        gates = require_object(payload.get("gate_status"), "payload.gate_status", errors)
        if set(gates) != GATES:
            errors.append("payload.gate_status 必须且只能包含 G0-G6")
        runtime = require_object(payload.get("runtime_capabilities"), "payload.runtime_capabilities", errors)
        if runtime.get("capability_source") not in {"runtime_advertised", "human_declared", "mixed", "unknown"}:
            errors.append("payload.runtime_capabilities.capability_source 无效")
        if runtime.get("discovery_status") not in {"pending", "partial", "complete"}:
            errors.append("payload.runtime_capabilities.discovery_status 无效")
        if runtime.get("execution_mode") not in EXECUTION_MODES:
            errors.append("payload.runtime_capabilities.execution_mode 无效")
        if runtime.get("captured_at"):
            parse_datetime(runtime.get("captured_at"), "payload.runtime_capabilities.captured_at", errors)
        capabilities = require_object(runtime.get("capabilities"), "payload.runtime_capabilities.capabilities", errors)
        capability_names = set(capabilities)
        missing_capabilities = sorted(REQUIRED_CAPABILITY_KEYS - capability_names)
        unknown_capabilities = sorted(capability_names - CAPABILITY_KEYS)
        if missing_capabilities:
            errors.append(
                "payload.runtime_capabilities.capabilities 缺少基础能力："
                + ", ".join(missing_capabilities)
            )
        if unknown_capabilities:
            errors.append(
                "payload.runtime_capabilities.capabilities 包含未知能力："
                + ", ".join(unknown_capabilities)
            )
        for capability_name in sorted(capability_names & CAPABILITY_KEYS):
            entry = require_object(
                capabilities.get(capability_name),
                f"payload.runtime_capabilities.capabilities.{capability_name}",
                errors,
            )
            if entry.get("status") not in CAPABILITY_STATUSES:
                errors.append(f"runtime capability {capability_name} status 无效")
            capability_id = entry.get("capability_id")
            if capability_id is not None and not isinstance(capability_id, str):
                errors.append(f"runtime capability {capability_name} capability_id 必须是 string 或 null")
            if entry.get("status") == "available" and not capability_id:
                errors.append(f"runtime capability {capability_name} 可用时必须记录 capability_id")
            require_list(entry.get("notes"), f"runtime capability {capability_name}.notes", errors)
        image_capability = capabilities.get("native_image_generation", {})
        if isinstance(image_capability, dict):
            if image_capability.get("processing_boundary") not in {"local", "external", "unknown"}:
                errors.append("runtime capability native_image_generation.processing_boundary 无效")
            for field in ("supports_reference_images", "returns_local_file"):
                value = image_capability.get(field)
                if value is not None and not isinstance(value, bool):
                    errors.append(f"runtime capability native_image_generation.{field} 必须是 boolean 或 null")
        require_list(runtime.get("limitations"), "payload.runtime_capabilities.limitations", errors)

        data_scope = require_object(payload.get("data_scope"), "payload.data_scope", errors)
        required_scope_fields = {"allowed_sources", "external_processing", "personal_data"}
        if set(data_scope) != required_scope_fields:
            errors.append("payload.data_scope 必须且只能包含 allowed_sources、external_processing、personal_data")
        require_list(data_scope.get("allowed_sources"), "payload.data_scope.allowed_sources", errors)
        external_processing = require_list(
            data_scope.get("external_processing"), "payload.data_scope.external_processing", errors
        )
        for index, entry in enumerate(external_processing):
            if not isinstance(entry, dict):
                errors.append(f"payload.data_scope.external_processing[{index}] 必须是 object")
                continue
            for field in ("capability_id", "purpose", "data_categories"):
                if not entry.get(field):
                    errors.append(f"payload.data_scope.external_processing[{index}] 缺少 {field}")
            require_list(
                entry.get("data_categories"),
                f"payload.data_scope.external_processing[{index}].data_categories",
                errors,
            )
        require_list(data_scope.get("personal_data"), "payload.data_scope.personal_data", errors)
    elif artifact_type == "account_strategy":
        if schema_version in DIRECTION_SCHEMA_VERSIONS:
            direction = require_object(payload.get("creator_direction"), "payload.creator_direction", errors)
            direction_fields = (
                "primary_90_day_outcome",
                "business_destination",
                "audience_business_fit",
                "current_value",
                "future_value",
                "relationship_posture",
                "trust_engine",
                "content_engine",
            )
            for field in direction_fields:
                value = direction.get(field)
                if value is not None and not isinstance(value, str):
                    errors.append(f"creator_direction.{field} 必须是 string 或 null")
            memory_assets = require_object(
                direction.get("memory_assets"), "payload.creator_direction.memory_assets", errors
            )
            primary_asset = memory_assets.get("primary")
            if primary_asset is not None and not isinstance(primary_asset, str):
                errors.append("creator_direction.memory_assets.primary 必须是 string 或 null")
            supporting_assets = require_nonempty_string_list(
                memory_assets.get("supporting"),
                "payload.creator_direction.memory_assets.supporting",
                errors,
            )
            if len(supporting_assets) > 2:
                errors.append("creator_direction.memory_assets.supporting 最多两个")
            require_nonempty_string_list(
                memory_assets.get("evidence_refs"),
                "payload.creator_direction.memory_assets.evidence_refs",
                errors,
            )
            for field in ("red_lines", "evidence_refs", "assumptions", "unknowns"):
                require_nonempty_string_list(
                    direction.get(field), f"payload.creator_direction.{field}", errors
                )
        if payload.get("lifecycle_stage") not in LIFECYCLE_STAGES:
            errors.append("account_strategy.lifecycle_stage 无效")
        if payload.get("stage_confidence") not in {"low", "medium", "high"}:
            errors.append("account_strategy.stage_confidence 无效")
        if payload.get("persona_mode") not in {"assumed", "validated"}:
            errors.append("account_strategy.persona_mode 无效")
        if payload.get("play_mode") not in {"trend", "ip", "hybrid", "undecided"}:
            errors.append("account_strategy.play_mode 无效")
        transition = require_object(payload.get("transition"), "payload.transition", errors)
        from_stage = transition.get("from_stage")
        if from_stage is not None and from_stage not in LIFECYCLE_STAGES:
            errors.append("account_strategy.transition.from_stage 无效")
        for field in ("rationale", "evidence_refs", "alternative_explanations"):
            if field not in transition:
                errors.append(f"account_strategy.transition 缺少 {field}")
        evidence_refs = require_list(
            transition.get("evidence_refs"), "payload.transition.evidence_refs", errors
        )
        require_list(
            transition.get("alternative_explanations"),
            "payload.transition.alternative_explanations",
            errors,
        )
        if from_stage and from_stage != payload.get("lifecycle_stage") and not evidence_refs:
            errors.append("生命周期阶段发生变化时 transition.evidence_refs 不能为空")
        stage_evidence = require_list(payload.get("stage_evidence"), "payload.stage_evidence", errors)
        for index, item in enumerate(stage_evidence):
            if not isinstance(item, dict):
                errors.append(f"stage_evidence[{index}] 必须是 object")
                continue
            for field in ("signal_id", "observation", "evidence_refs", "confidence"):
                if field not in item:
                    errors.append(f"stage_evidence[{index}] 缺少 {field}")
            if item.get("confidence") not in {"low", "medium", "high"}:
                errors.append(f"stage_evidence[{index}].confidence 无效")
        objectives = require_list(payload.get("content_objectives"), "payload.content_objectives", errors)
        seen_objectives: set[str] = set()
        shares: list[float] = []
        all_shares_present = bool(objectives)
        for index, item in enumerate(objectives):
            if not isinstance(item, dict):
                errors.append(f"content_objectives[{index}] 必须是 object")
                continue
            objective = item.get("objective")
            if objective not in CONTENT_OBJECTIVES:
                errors.append(f"content_objectives[{index}].objective 无效")
            elif objective in seen_objectives:
                errors.append(f"content_objectives[{index}].objective 重复")
            else:
                seen_objectives.add(objective)
            share = item.get("target_share")
            if share is None:
                all_shares_present = False
            elif not is_number(share) or not 0 <= share <= 1:
                errors.append(f"content_objectives[{index}].target_share 必须在 0 到 1 之间或为 null")
            else:
                shares.append(float(share))
        if all_shares_present and objectives and abs(sum(shares) - 1.0) > 1e-6:
            errors.append("content_objectives 全部给出 target_share 时合计必须为 1")
        publishing = require_object(payload.get("publishing_policy"), "payload.publishing_policy", errors)
        if publishing.get("modification_policy") not in {"human_review_required", "prohibited"}:
            errors.append("publishing_policy.modification_policy 无效")
        if publishing.get("deletion_policy") not in {"human_review_required", "prohibited"}:
            errors.append("publishing_policy.deletion_policy 无效")
        if publishing.get("threshold_basis") not in THRESHOLD_BASES:
            errors.append("publishing_policy.threshold_basis 无效")
        if publishing.get("exceptions_require_human") is not True:
            errors.append("publishing_policy.exceptions_require_human 必须为 true")
        for field in ("minimum_observation_hours", "same_topic_cooldown_hours", "breakout_hold_hours"):
            value = publishing.get(field)
            if value is not None and (not is_number(value) or value < 0):
                errors.append(f"publishing_policy.{field} 必须是非负数或 null")
        inventory_policy = require_object(payload.get("inventory_policy"), "payload.inventory_policy", errors)
        if inventory_policy.get("threshold_basis") not in THRESHOLD_BASES:
            errors.append("inventory_policy.threshold_basis 无效")
        coverage = inventory_policy.get("target_coverage_days")
        if coverage is not None and (not is_number(coverage) or coverage < 0):
            errors.append("inventory_policy.target_coverage_days 必须是非负数或 null")
        ready_items = inventory_policy.get("target_ready_items")
        if ready_items is not None and (not isinstance(ready_items, int) or isinstance(ready_items, bool) or ready_items < 0):
            errors.append("inventory_policy.target_ready_items 必须是非负整数或 null")
        measurement = require_object(payload.get("measurement_policy"), "payload.measurement_policy", errors)
        for field in ("trust_metrics", "long_tail_checkpoints_days", "qualitative_rubric_refs"):
            require_list(measurement.get(field), f"measurement_policy.{field}", errors)
        strategy_checkpoints = measurement.get("long_tail_checkpoints_days", [])
        if isinstance(strategy_checkpoints, list):
            if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in strategy_checkpoints):
                errors.append("measurement_policy.long_tail_checkpoints_days 只能包含正整数")
            if len(strategy_checkpoints) != len(set(strategy_checkpoints)):
                errors.append("measurement_policy.long_tail_checkpoints_days 不得重复")
        require_list(payload.get("experience_seed_refs"), "payload.experience_seed_refs", errors)
        require_list(payload.get("limitations"), "payload.limitations", errors)
    elif artifact_type == "persona":
        persona_revision = payload.get("revision")
        if (
            not isinstance(persona_revision, int)
            or isinstance(persona_revision, bool)
            or persona_revision < 1
        ):
            errors.append("persona.revision 必须是正整数")
        if schema_version in DIRECTION_SCHEMA_VERSIONS:
            diagnosis = require_object(
                payload.get("positioning_diagnosis"), "payload.positioning_diagnosis", errors
            )
            diagnosis_type = diagnosis.get("diagnosis_type")
            recommended_action = diagnosis.get("recommended_action")
            if diagnosis_type not in {
                "initial_definition",
                "foundation_unclear",
                "delivery_inconsistent",
                "wrong_audience",
                "evidence_insufficient",
            }:
                errors.append("positioning_diagnosis.diagnosis_type 无效")
            if recommended_action not in {"create", "revise", "keep", "test_first"}:
                errors.append("positioning_diagnosis.recommended_action 无效")
            require_nonempty_text(
                diagnosis.get("rationale"), "payload.positioning_diagnosis.rationale", errors
            )
            diagnosis_evidence = require_nonempty_string_list(
                diagnosis.get("evidence_refs"),
                "payload.positioning_diagnosis.evidence_refs",
                errors,
            )
            if not diagnosis_evidence:
                errors.append("positioning_diagnosis.evidence_refs 至少需要一条依据")
            require_nonempty_string_list(
                diagnosis.get("alternative_explanations"),
                "payload.positioning_diagnosis.alternative_explanations",
                errors,
            )
            if diagnosis_type == "initial_definition" and recommended_action != "create":
                errors.append("首次建立定位时 recommended_action 必须是 create")
            if diagnosis_type != "initial_definition" and recommended_action == "create":
                errors.append("非首次建立定位时不得建议 create")
            if diagnosis_type in {"delivery_inconsistent", "evidence_insufficient"} and recommended_action == "revise":
                errors.append("内容兑现不稳定或证据不足时不得直接建议修订定位")

            alignment = require_object(
                payload.get("direction_alignment"), "payload.direction_alignment", errors
            )
            for field in (
                "account_role",
                "account_current_value",
                "account_future_value",
                "relationship_expression",
                "trust_expression",
                "content_engine_expression",
                "memory_asset_expression",
                "business_connection",
            ):
                require_nonempty_text(
                    alignment.get(field), f"payload.direction_alignment.{field}", errors
                )
            require_nonempty_string_list(
                alignment.get("tensions"), "payload.direction_alignment.tensions", errors
            )
            alignment_evidence = require_nonempty_string_list(
                alignment.get("evidence_refs"),
                "payload.direction_alignment.evidence_refs",
                errors,
            )
            if not alignment_evidence:
                errors.append("direction_alignment.evidence_refs 至少需要一条依据")
        if payload.get("mode") not in {"assumed", "validated"}:
            errors.append("persona.mode 无效")
        hypotheses = require_list(payload.get("hypotheses"), "payload.hypotheses", errors)
        seen_hypothesis_ids: set[str] = set()
        for index, item in enumerate(hypotheses):
            if not isinstance(item, dict):
                errors.append(f"persona.hypotheses[{index}] 必须是 object")
                continue
            required_hypothesis_fields = (
                "hypothesis_id",
                "statement",
                "status",
                "evidence_refs",
            )
            if schema_version == SCHEMA_VERSION:
                required_hypothesis_fields += (
                    "component",
                    "observable_implication",
                    "falsification_signal",
                    "confidence",
                    "scope",
                    "counter_evidence_refs",
                    "review_by",
                )
            for field in required_hypothesis_fields:
                if field not in item:
                    errors.append(f"persona.hypotheses[{index}] 缺少 {field}")
            if schema_version in DIRECTION_SCHEMA_VERSIONS:
                hypothesis_id = require_nonempty_text(
                    item.get("hypothesis_id"),
                    f"persona.hypotheses[{index}].hypothesis_id",
                    errors,
                )
                require_nonempty_text(
                    item.get("statement"),
                    f"persona.hypotheses[{index}].statement",
                    errors,
                )
                require_nonempty_string_list(
                    item.get("evidence_refs"),
                    f"persona.hypotheses[{index}].evidence_refs",
                    errors,
                )
                if schema_version == SCHEMA_VERSION:
                    if item.get("component") not in POSITIONING_HYPOTHESIS_COMPONENTS:
                        errors.append(f"persona.hypotheses[{index}].component 无效")
                    if item.get("status") not in POSITIONING_HYPOTHESIS_STATUSES:
                        errors.append(f"persona.hypotheses[{index}].status 无效")
                    if item.get("confidence") not in {"low", "medium", "high"}:
                        errors.append(f"persona.hypotheses[{index}].confidence 无效")
                    for field in ("observable_implication", "falsification_signal", "scope"):
                        require_nonempty_text(
                            item.get(field),
                            f"persona.hypotheses[{index}].{field}",
                            errors,
                        )
                    counter_refs = require_nonempty_string_list(
                        item.get("counter_evidence_refs"),
                        f"persona.hypotheses[{index}].counter_evidence_refs",
                        errors,
                    )
                    review_by = item.get("review_by")
                    if review_by is not None:
                        parse_datetime(
                            review_by,
                            f"persona.hypotheses[{index}].review_by",
                            errors,
                        )
                    if item.get("status") in {"emerging", "provisionally_established"} and not item.get("evidence_refs"):
                        errors.append(
                            f"persona.hypotheses[{index}] 进入 {item.get('status')} 前必须有支持证据"
                        )
                    if item.get("status") == "refuted" and not (
                        item.get("evidence_refs") or counter_refs
                    ):
                        errors.append(f"persona.hypotheses[{index}] 标记 refuted 时必须有证据")
                elif item.get("status") not in {"pending", "supported", "refuted", "inconclusive"}:
                    errors.append(f"persona.hypotheses[{index}].status 无效")
                if hypothesis_id:
                    if hypothesis_id in seen_hypothesis_ids:
                        errors.append(f"persona.hypotheses[{index}].hypothesis_id 重复")
                    seen_hypothesis_ids.add(hypothesis_id)
            elif item.get("status") not in {"pending", "supported", "refuted", "inconclusive"}:
                errors.append(f"persona.hypotheses[{index}].status 无效")
        validation_plan = require_object(payload.get("validation_plan"), "payload.validation_plan", errors)
        validate_positive_int_or_null(
            validation_plan.get("sample_target"), "payload.validation_plan.sample_target", errors
        )
        for field in ("diversity_dimensions", "success_signals", "stop_conditions"):
            require_list(validation_plan.get(field), f"payload.validation_plan.{field}", errors)
        if payload.get("mode") == "assumed":
            if not hypotheses:
                errors.append("assumed persona 至少需要一个可证伪假设")
            if not validation_plan.get("success_signals") or not validation_plan.get("stop_conditions"):
                errors.append("assumed persona 必须定义 success_signals 和 stop_conditions")
        if schema_version == SCHEMA_VERSION:
            positioning_state = require_object(
                payload.get("positioning_state"), "payload.positioning_state", errors
            )
            phase = positioning_state.get("phase")
            if phase not in POSITIONING_PHASES:
                errors.append("positioning_state.phase 无效")
            require_nonempty_text(
                positioning_state.get("scope"), "payload.positioning_state.scope", errors
            )
            for field in (
                "stable_core",
                "open_questions",
                "anti_audience",
                "anti_positioning",
            ):
                require_nonempty_string_list(
                    positioning_state.get(field), f"payload.positioning_state.{field}", errors
                )
            state_review_by = positioning_state.get("review_by")
            if state_review_by is not None:
                parse_datetime(state_review_by, "payload.positioning_state.review_by", errors)
            if payload.get("mode") == "validated" and phase != "stable_within_scope":
                errors.append("mode=validated 只能表示限定范围内已稳定的定位")
            if payload.get("mode") == "assumed" and phase == "stable_within_scope":
                errors.append("phase=stable_within_scope 时 mode 必须为 validated")

            validation_evidence = require_object(
                payload.get("validation_evidence"), "payload.validation_evidence", errors
            )
            review_refs = require_nonempty_string_list(
                validation_evidence.get("review_artifact_refs"),
                "payload.validation_evidence.review_artifact_refs",
                errors,
            )
            experiment_refs = require_nonempty_string_list(
                validation_evidence.get("experiment_artifact_refs"),
                "payload.validation_evidence.experiment_artifact_refs",
                errors,
            )
            content_refs = require_nonempty_string_list(
                validation_evidence.get("content_artifact_refs"),
                "payload.validation_evidence.content_artifact_refs",
                errors,
            )
            snapshot_refs = require_nonempty_string_list(
                validation_evidence.get("snapshot_artifact_refs"),
                "payload.validation_evidence.snapshot_artifact_refs",
                errors,
            )
            streams = require_nonempty_string_list(
                validation_evidence.get("evidence_streams_covered"),
                "payload.validation_evidence.evidence_streams_covered",
                errors,
            )
            unknown_streams = sorted(set(streams) - POSITIONING_EVIDENCE_STREAMS)
            if unknown_streams:
                errors.append("validation_evidence 包含未知证据流：" + ", ".join(unknown_streams))
            if not isinstance(validation_evidence.get("counter_evidence_reviewed"), bool):
                errors.append("validation_evidence.counter_evidence_reviewed 必须是 boolean")
            reviewed_at = validation_evidence.get("reviewed_at")
            if reviewed_at is not None:
                parse_datetime(reviewed_at, "payload.validation_evidence.reviewed_at", errors)
            require_nonempty_string_list(
                validation_evidence.get("limitations"),
                "payload.validation_evidence.limitations",
                errors,
            )
            if payload.get("mode") == "validated":
                if payload.get("revision", 0) < 2 or not payload.get("supersedes_artifact_id"):
                    errors.append("稳定定位必须是引用上一版本的新 revision")
                unsettled = [
                    item.get("hypothesis_id")
                    for item in hypotheses
                    if isinstance(item, dict)
                    and item.get("status") not in {"provisionally_established", "refuted"}
                ]
                if unsettled:
                    errors.append("稳定定位仍包含未收敛假设：" + ", ".join(str(item) for item in unsettled))
                if not any(
                    isinstance(item, dict)
                    and item.get("status") == "provisionally_established"
                    for item in hypotheses
                ):
                    errors.append("稳定定位至少需要一个阶段性成立的定位假设")
                if not review_refs:
                    errors.append("稳定定位至少需要一份复盘记录")
                if len(set(content_refs)) < 2:
                    errors.append("稳定定位必须由至少两篇不同内容共同支持")
                if not snapshot_refs:
                    errors.append("稳定定位至少需要一份数据快照")
                missing_streams = sorted(REQUIRED_STABLE_EVIDENCE_STREAMS - set(streams))
                if missing_streams:
                    errors.append("稳定定位缺少证据流：" + ", ".join(missing_streams))
                if validation_evidence.get("counter_evidence_reviewed") is not True:
                    errors.append("稳定定位前必须明确复核反向证据")
                if reviewed_at is None or state_review_by is None:
                    errors.append("稳定定位必须记录 reviewed_at 与 review_by")

            allowed_evidence_refs = {
                source.get("source_id")
                for source in provenance
                if isinstance(source, dict) and isinstance(source.get("source_id"), str)
            }
            allowed_evidence_refs.update(review_refs)
            allowed_evidence_refs.update(experiment_refs)
            allowed_evidence_refs.update(content_refs)
            allowed_evidence_refs.update(snapshot_refs)
            evidence_fields: list[tuple[str, list[Any]]] = [
                ("positioning_diagnosis.evidence_refs", diagnosis.get("evidence_refs", [])),
                ("direction_alignment.evidence_refs", alignment.get("evidence_refs", [])),
            ]
            for index, item in enumerate(hypotheses):
                if isinstance(item, dict):
                    evidence_fields.extend(
                        [
                            (f"hypotheses[{index}].evidence_refs", item.get("evidence_refs", [])),
                            (
                                f"hypotheses[{index}].counter_evidence_refs",
                                item.get("counter_evidence_refs", []),
                            ),
                        ]
                    )
            for index, item in enumerate(payload.get("audience", [])):
                if isinstance(item, dict):
                    evidence_fields.append(
                        (f"audience[{index}].evidence_refs", item.get("evidence_refs", []))
                    )
            for field, refs in evidence_fields:
                for ref in refs if isinstance(refs, list) else []:
                    if isinstance(ref, str) and ref not in allowed_evidence_refs:
                        errors.append(f"{field} 引用了未登记证据：{ref}")
        if schema_version in DIRECTION_SCHEMA_VERSIONS:
            audience = require_list(payload.get("audience"), "payload.audience", errors)
            if not audience:
                errors.append("persona.audience 至少需要一个受众分组")
            audience_ids: set[str] = set()
            for index, item in enumerate(audience):
                if not isinstance(item, dict):
                    errors.append(f"persona.audience[{index}] 必须是 object")
                    continue
                segment_id = require_nonempty_text(
                    item.get("segment_id"), f"persona.audience[{index}].segment_id", errors
                )
                require_nonempty_text(
                    item.get("name"), f"persona.audience[{index}].name", errors
                )
                for field in ("jobs", "pains", "desired_outcomes", "evidence_refs"):
                    require_nonempty_string_list(
                        item.get(field), f"persona.audience[{index}].{field}", errors
                    )
                if segment_id:
                    if segment_id in audience_ids:
                        errors.append(f"persona.audience[{index}].segment_id 重复")
                    audience_ids.add(segment_id)
            hypothesis_ids = seen_hypothesis_ids
            pillars = require_list(payload.get("content_pillars"), "payload.content_pillars", errors)
            if not pillars:
                errors.append("persona.content_pillars 至少需要一个内容支柱")
            pillar_ids: set[str] = set()
            for index, item in enumerate(pillars):
                if not isinstance(item, dict):
                    errors.append(f"content_pillars[{index}] 必须是 object")
                    continue
                for field in (
                    "pillar_id",
                    "name",
                    "purpose",
                    "audience_job",
                    "value_delivered",
                    "proof_role",
                    "business_connection",
                ):
                    require_nonempty_text(item.get(field), f"content_pillars[{index}].{field}", errors)
                if schema_version == SCHEMA_VERSION:
                    require_nonempty_text(
                        item.get("memory_asset"),
                        f"content_pillars[{index}].memory_asset",
                        errors,
                    )
                pillar_id = item.get("pillar_id")
                if isinstance(pillar_id, str) and pillar_id.strip():
                    normalized_pillar_id = pillar_id.strip()
                    if normalized_pillar_id in pillar_ids:
                        errors.append(f"content_pillars[{index}].pillar_id 重复")
                    pillar_ids.add(normalized_pillar_id)
                audience_refs = require_nonempty_string_list(
                    item.get("audience_segment_refs"),
                    f"content_pillars[{index}].audience_segment_refs",
                    errors,
                )
                if not audience_refs:
                    errors.append(f"content_pillars[{index}] 至少关联一个受众分组")
                audience_ref_ids = set(audience_refs)
                if len(audience_ref_ids) != len(audience_refs):
                    errors.append(f"content_pillars[{index}].audience_segment_refs 不得重复")
                unknown_audiences = sorted(audience_ref_ids - audience_ids)
                if unknown_audiences:
                    errors.append(
                        f"content_pillars[{index}] 引用了不存在的受众分组："
                        + ", ".join(unknown_audiences)
                    )
                hypothesis_refs = require_nonempty_string_list(
                    item.get("hypothesis_refs"),
                    f"content_pillars[{index}].hypothesis_refs",
                    errors,
                )
                hypothesis_ref_ids = set(hypothesis_refs)
                if len(hypothesis_ref_ids) != len(hypothesis_refs):
                    errors.append(f"content_pillars[{index}].hypothesis_refs 不得重复")
                unknown_hypotheses = sorted(hypothesis_ref_ids - hypothesis_ids)
                if unknown_hypotheses:
                    errors.append(
                        f"content_pillars[{index}] 引用了不存在的定位假设："
                        + ", ".join(unknown_hypotheses)
                    )
                require_nonempty_string_list(
                    item.get("boundaries"), f"content_pillars[{index}].boundaries", errors
                )
                require_nonempty_string_list(
                    item.get("topic_seeds"), f"content_pillars[{index}].topic_seeds", errors
                )
    elif artifact_type == "topic_report":
        if payload.get("research_mode") not in {"trial_diversification", "focused", "trend_window"}:
            errors.append("topic_report.research_mode 无效")
        candidates = require_list(payload.get("candidates"), "payload.candidates", errors)
        if not candidates:
            errors.append("topic_report 至少需要一个候选选题")
        candidate_ids = {item.get("topic_id") for item in candidates if isinstance(item, dict)}
        selected = require_list(payload.get("selected_topic_ids"), "payload.selected_topic_ids", errors)
        unknown = sorted(set(selected) - candidate_ids)
        if unknown:
            errors.append("selected_topic_ids 引用了不存在的候选：" + ", ".join(unknown))
        evidence_items = require_list(payload.get("evidence"), "payload.evidence", errors)
        evidence_ids = set()
        for index, item in enumerate(evidence_items):
            if not isinstance(item, dict):
                errors.append(f"payload.evidence[{index}] 必须是 object")
                continue
            evidence_id = item.get("evidence_id")
            if not evidence_id:
                errors.append(f"payload.evidence[{index}] 缺少 evidence_id")
            elif evidence_id in evidence_ids:
                errors.append(f"payload.evidence[{index}] evidence_id 重复：{evidence_id}")
            else:
                evidence_ids.add(evidence_id)
            for field in ("kind", "source_ref", "captured_at", "observation", "limitations"):
                if field not in item:
                    errors.append(f"payload.evidence[{index}] 缺少 {field}")
            if item.get("quote") and item.get("quote_verified") is not True:
                errors.append(f"payload.evidence[{index}] 含 quote 时必须 quote_verified=true")
            if item.get("captured_at"):
                parse_datetime(item.get("captured_at"), f"payload.evidence[{index}].captured_at", errors)
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                errors.append(f"payload.candidates[{index}] 必须是 object")
                continue
            for ref in candidate.get("evidence_refs", []):
                if ref not in evidence_ids:
                    errors.append(f"candidate {candidate.get('topic_id')} 引用未知 evidence_id：{ref}")
            if candidate.get("confidence") not in {"low", "medium", "high"}:
                errors.append(f"candidate {candidate.get('topic_id')} confidence 无效")
            if schema_version == SCHEMA_VERSION:
                validate_positioning_trace(
                    candidate.get("positioning_trace"),
                    f"payload.candidates[{index}].positioning_trace",
                    errors,
                )
    elif artifact_type == "content":
        if payload.get("content_objective") not in CONTENT_OBJECTIVES:
            errors.append("content.content_objective 无效")
        validate_positive_int_or_null(
            payload.get("content_sequence_no"), "payload.content_sequence_no", errors
        )
        content_format = payload.get("format")
        if content_format not in {"image", "video", "text"}:
            errors.append("payload.format 必须是 image、video 或 text")
        if content_format == "image" and not payload.get("cards"):
            errors.append("图文内容必须包含 cards")
        if content_format == "video" and not payload.get("shots"):
            errors.append("视频内容必须包含 shots")
        if schema_version == SCHEMA_VERSION:
            validate_positioning_trace(
                payload.get("positioning_trace"), "payload.positioning_trace", errors
            )
        claim_ids: set[str] = set()
        for index, claim in enumerate(require_list(payload.get("claims"), "payload.claims", errors)):
            if not isinstance(claim, dict):
                errors.append(f"claims[{index}] 必须是 object")
                continue
            for field in ("claim_id", "text", "kind", "source_refs", "verification_status"):
                if field not in claim:
                    errors.append(f"claims[{index}] 缺少 {field}")
            claim_id = claim.get("claim_id")
            if claim_id in claim_ids:
                errors.append(f"claims[{index}] claim_id 重复：{claim_id}")
            elif claim_id:
                claim_ids.add(claim_id)
            if claim.get("kind") not in {"fact", "opinion", "hypothesis"}:
                errors.append(f"claims[{index}].kind 无效")
            if claim.get("kind") == "fact":
                if claim.get("verification_status") != "verified" or not claim.get("source_refs"):
                    errors.append(f"claims[{index}] 事实主张必须验证并关联来源")
        for index, experience in enumerate(require_list(payload.get("personal_experiences"), "payload.personal_experiences", errors)):
            if not isinstance(experience, dict) or experience.get("confirmed_by_human") is not True or not experience.get("source_ref"):
                errors.append(f"personal_experiences[{index}] 必须有 source_ref 且经人工确认")
        for index, asset in enumerate(require_list(payload.get("assets"), "payload.assets", errors)):
            if not isinstance(asset, dict):
                errors.append(f"assets[{index}] 必须是 object")
                continue
            if asset.get("rights_basis") not in {"owned", "licensed", "permission", "public_domain", "generated"}:
                errors.append(f"assets[{index}].rights_basis 无效")
            if asset.get("rights_status") != "verified":
                errors.append(f"assets[{index}] 权利状态未验证，不得进入 G3")
            sha = asset.get("sha256")
            if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
                errors.append(f"assets[{index}].sha256 无效")
            if not isinstance(asset.get("contains_personal_data"), bool):
                errors.append(f"assets[{index}].contains_personal_data 必须是 boolean")
            if not isinstance(asset.get("external_processing_approved"), bool):
                errors.append(f"assets[{index}].external_processing_approved 必须是 boolean")
            if asset.get("rights_basis") == "generated":
                if not asset.get("generation_job_id") or not asset.get("generator_capability_id"):
                    errors.append(f"assets[{index}] 生成素材必须记录 generation_job_id 和 generator_capability_id")
        authorship = payload.get("authorship")
        if authorship is not None:
            authorship = require_object(authorship, "payload.authorship", errors)
            if authorship.get("actor_type") not in {"agent", "human"}:
                errors.append("payload.authorship.actor_type 无效")
            if not isinstance(authorship.get("actor_id"), str) or not authorship.get("actor_id", "").strip():
                errors.append("payload.authorship.actor_id 必须是非空字符串")
            if authorship.get("actor_type") == "agent" and (
                not isinstance(authorship.get("context_id"), str)
                or not authorship.get("context_id", "").strip()
            ):
                errors.append("Agent 作者必须记录 payload.authorship.context_id")
            if authorship.get("model_id") is not None and (
                not isinstance(authorship.get("model_id"), str)
                or not authorship.get("model_id", "").strip()
            ):
                errors.append("payload.authorship.model_id 必须是非空字符串或 null")
        audit_ref = payload.get("article_audit_ref")
        if audit_ref is not None:
            audit_ref = require_object(audit_ref, "payload.article_audit_ref", errors)
            for field in ("artifact_id", "artifact_path", "payload_sha256", "content_sha256"):
                if field not in audit_ref:
                    errors.append(f"payload.article_audit_ref 缺少 {field}")
            if not isinstance(audit_ref.get("artifact_id"), str) or not audit_ref.get("artifact_id", "").startswith("article_audit_"):
                errors.append("payload.article_audit_ref.artifact_id 无效")
            for field in ("payload_sha256", "content_sha256"):
                value = audit_ref.get(field)
                if not isinstance(value, str) or not SHA_RE.fullmatch(value):
                    errors.append(f"payload.article_audit_ref.{field} 无效")
    elif artifact_type == "article_audit":
        try:
            errors.extend(article_audit_contract().validate_audit_document(artifact))
        except (WorkflowError, OSError) as exc:
            errors.append(str(exc))
    elif artifact_type == "inventory_item":
        state = payload.get("state")
        if state not in INVENTORY_STATES:
            errors.append(f"inventory_item.state 无效：{state}")
        if artifact.get("status") != state:
            errors.append("inventory_item 顶层 status 必须与 payload.state 一致")
        if payload.get("content_objective") not in CONTENT_OBJECTIVES:
            errors.append("inventory_item.content_objective 无效")
        if payload.get("format") not in {"image", "video", "text"}:
            errors.append("inventory_item.format 无效")
        validate_positive_int_or_null(
            payload.get("content_sequence_no"), "payload.content_sequence_no", errors
        )
        if state == "scheduled":
            if not payload.get("planned_publish_at"):
                errors.append("scheduled inventory_item 必须有 planned_publish_at")
            else:
                parse_datetime(payload.get("planned_publish_at"), "payload.planned_publish_at", errors)
        elif payload.get("planned_publish_at") is not None:
            parse_datetime(payload.get("planned_publish_at"), "payload.planned_publish_at", errors)
        if state == "held" and not payload.get("hold_reason"):
            errors.append("held inventory_item 必须说明 hold_reason")
        validate_policy_check(payload.get("policy_check"), "payload.policy_check", errors)
        schedule = require_list(payload.get("measurement_schedule"), "payload.measurement_schedule", errors)
        seen_checkpoints: set[int] = set()
        seen_schedule_ids: set[str] = set()
        for index, item in enumerate(schedule):
            if not isinstance(item, dict):
                errors.append(f"measurement_schedule[{index}] 必须是 object")
                continue
            for field in ("checkpoint_days", "due_at", "status", "snapshot_artifact_id", "completed_at"):
                if field not in item:
                    errors.append(f"measurement_schedule[{index}] 缺少 {field}")
            schedule_id = item.get("schedule_id")
            if schedule_id is not None:
                if not isinstance(schedule_id, str) or not schedule_id:
                    errors.append(f"measurement_schedule[{index}].schedule_id 必须是非空字符串")
                elif schedule_id in seen_schedule_ids:
                    errors.append(f"measurement_schedule schedule_id 重复：{schedule_id}")
                else:
                    seen_schedule_ids.add(schedule_id)
            measurement_kind = item.get("measurement_kind")
            if measurement_kind is not None and measurement_kind not in {"initial", "long_tail"}:
                errors.append(f"measurement_schedule[{index}].measurement_kind 无效")
            checkpoint = item.get("checkpoint_days")
            if measurement_kind == "initial":
                if checkpoint is not None:
                    errors.append(f"measurement_schedule[{index}] 首次采集周期的 checkpoint_days 必须为 null")
            elif not isinstance(checkpoint, int) or isinstance(checkpoint, bool) or checkpoint <= 0:
                errors.append(f"measurement_schedule[{index}].checkpoint_days 必须是正整数")
            elif checkpoint in seen_checkpoints:
                errors.append(f"measurement_schedule checkpoint 重复：{checkpoint}")
            else:
                seen_checkpoints.add(checkpoint)
            if measurement_kind is not None and (not isinstance(item.get("window"), str) or not item.get("window")):
                errors.append(f"measurement_schedule[{index}].window 必须是非空字符串")
            if item.get("anchor_published_at") is not None:
                parse_datetime(item.get("anchor_published_at"), f"measurement_schedule[{index}].anchor_published_at", errors)
            if item.get("due_at"):
                parse_datetime(item.get("due_at"), f"measurement_schedule[{index}].due_at", errors)
            if item.get("status") not in {"pending", "completed", "skipped"}:
                errors.append(f"measurement_schedule[{index}].status 无效")
            if item.get("status") == "completed" and not item.get("snapshot_artifact_id"):
                errors.append(f"measurement_schedule[{index}] 完成时必须引用 snapshot_artifact_id")
            if item.get("completed_at") is not None:
                parse_datetime(item.get("completed_at"), f"measurement_schedule[{index}].completed_at", errors)
        history = require_list(payload.get("history"), "payload.history", errors)
        for index, item in enumerate(history):
            if not isinstance(item, dict):
                errors.append(f"history[{index}] 必须是 object")
                continue
            for field in ("from", "to", "at", "actor_id", "actor_type", "reason"):
                if field not in item:
                    errors.append(f"history[{index}] 缺少 {field}")
            if item.get("from") is not None and item.get("from") not in INVENTORY_STATES:
                errors.append(f"history[{index}].from 无效")
            if item.get("to") not in INVENTORY_STATES:
                errors.append(f"history[{index}].to 无效")
            if item.get("actor_type") not in {"human", "agent"}:
                errors.append(f"history[{index}].actor_type 无效")
            if item.get("at"):
                parse_datetime(item.get("at"), f"history[{index}].at", errors)
    elif artifact_type == "publication":
        state = payload.get("state")
        if state not in PUBLICATION_TRANSITIONS:
            errors.append(f"publication state 无效：{state}")
        if artifact.get("status") != state:
            errors.append("publication 顶层 status 必须与 payload.state 一致")
        if payload.get("target_account_id") != artifact.get("account_id"):
            errors.append("target_account_id 必须与 artifact.account_id 一致")
        scheduled_at = payload.get("scheduled_at")
        schedule_expires_at = payload.get("schedule_expires_at")
        schedule_method = payload.get("schedule_method")
        if scheduled_at is not None:
            parse_datetime(scheduled_at, "payload.scheduled_at", errors)
            if schedule_expires_at is None:
                errors.append("定时发布必须记录 schedule_expires_at")
            else:
                parse_datetime(schedule_expires_at, "payload.schedule_expires_at", errors)
                try:
                    if datetime_value(schedule_expires_at, "payload.schedule_expires_at") <= datetime_value(scheduled_at, "payload.scheduled_at"):
                        errors.append("schedule_expires_at 必须晚于 scheduled_at")
                except WorkflowError:
                    pass
            if schedule_method not in SCHEDULE_METHODS:
                errors.append("定时发布必须记录有效的 schedule_method")
        elif schedule_method is not None or schedule_expires_at is not None:
            errors.append("未设置 scheduled_at 时不得保留定时发布方式或最晚执行时间")
        schedule_reference = payload.get("schedule_reference")
        if schedule_reference is not None and (not isinstance(schedule_reference, str) or not schedule_reference.strip()):
            errors.append("schedule_reference 必须是非空字符串或 null")
        validate_policy_check(payload.get("policy_check"), "payload.policy_check", errors)
        execution_checks = require_list(payload.get("execution_checks", []), "payload.execution_checks", errors)
        for index, check in enumerate(execution_checks):
            validate_policy_check(check, f"payload.execution_checks[{index}]", errors)
        actions = require_list(payload.get("post_publish_actions"), "payload.post_publish_actions", errors)
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                errors.append(f"post_publish_actions[{index}] 必须是 object")
                continue
            for field in ("action", "requested_at", "actor_id", "actor_type", "decision", "reasons"):
                if field not in action:
                    errors.append(f"post_publish_actions[{index}] 缺少 {field}")
            if action.get("action") not in {"modify", "delete"}:
                errors.append(f"post_publish_actions[{index}].action 无效")
            if action.get("actor_type") != "human":
                errors.append(f"post_publish_actions[{index}] 只能由 human 决定")
            if action.get("decision") not in {"approved", "rejected"}:
                errors.append(f"post_publish_actions[{index}].decision 无效")
            if action.get("requested_at"):
                parse_datetime(action.get("requested_at"), f"post_publish_actions[{index}].requested_at", errors)
        if state == "published":
            if not (payload.get("remote_id") or payload.get("remote_url")):
                errors.append("published 状态必须有 remote_id 或 remote_url")
            if not payload.get("published_at"):
                errors.append("published 状态必须记录实际上线时间 published_at")
            else:
                parse_datetime(payload.get("published_at"), "payload.published_at", errors)
            source = payload.get("published_at_source")
            if source is not None and source not in PUBLISHED_AT_SOURCES:
                errors.append("payload.published_at_source 无效")
    elif artifact_type == "metrics_snapshot":
        if payload.get("format") not in {"image", "video", "text"}:
            errors.append("metrics_snapshot.format 无效")
        measurement_kind = payload.get("measurement_kind")
        if measurement_kind not in {"initial", "long_tail"}:
            errors.append("metrics_snapshot.measurement_kind 无效")
        checkpoint_days = payload.get("checkpoint_days")
        validate_positive_int_or_null(checkpoint_days, "payload.checkpoint_days", errors)
        if measurement_kind == "long_tail" and checkpoint_days is None:
            errors.append("long_tail metrics_snapshot 必须记录 checkpoint_days")
        if measurement_kind == "long_tail" and not payload.get("prior_snapshot_artifact_id"):
            errors.append("long_tail metrics_snapshot 必须引用 prior_snapshot_artifact_id")
        parse_datetime(payload.get("captured_at"), "payload.captured_at", errors)
        for field in ("published_at_anchor", "window_started_at", "window_ended_at"):
            if payload.get(field) is not None:
                parse_datetime(payload.get(field), f"payload.{field}", errors)
        elapsed_hours = payload.get("elapsed_hours")
        if elapsed_hours is not None and (not is_number(elapsed_hours) or elapsed_hours < 0):
            errors.append("payload.elapsed_hours 必须是非负数或 null")
        for section in ("stock_metrics", "flow_metrics", "derived_metrics", "trust_metrics"):
            metrics = require_object(payload.get(section), f"payload.{section}", errors)
            for name, value in metrics.items():
                if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
                    errors.append(f"payload.{section}.{name} 必须是 number 或 null")
                if section != "derived_metrics" and isinstance(value, (int, float)) and value < 0:
                    errors.append(f"payload.{section}.{name} 不得为负数")
        for index, item in enumerate(require_list(payload.get("qualitative_metrics"), "payload.qualitative_metrics", errors)):
            if not isinstance(item, dict):
                errors.append(f"qualitative_metrics[{index}] 必须是 object")
                continue
            for field in ("metric", "value", "rubric_ref", "evidence_refs", "assessed_by"):
                if field not in item:
                    errors.append(f"qualitative_metrics[{index}] 缺少 {field}")
            if item.get("assessed_by") != "human":
                errors.append(f"qualitative_metrics[{index}].assessed_by 必须为 human")
    elif artifact_type == "review":
        snapshots = require_list(payload.get("snapshot_artifact_ids"), "payload.snapshot_artifact_ids", errors)
        if not snapshots:
            errors.append("review 至少引用一个 metrics_snapshot")
        time_context = payload.get("time_context")
        if time_context is not None:
            time_context = require_object(time_context, "payload.time_context", errors)
            parse_datetime(time_context.get("published_at"), "payload.time_context.published_at", errors)
            if time_context.get("published_at_source") not in PUBLISHED_AT_SOURCES:
                errors.append("payload.time_context.published_at_source 无效")
            for index, window in enumerate(require_list(time_context.get("windows"), "payload.time_context.windows", errors)):
                if not isinstance(window, dict):
                    errors.append(f"payload.time_context.windows[{index}] 必须是 object")
                    continue
                for field in ("window", "due_at", "captured_at", "elapsed_hours", "snapshot_artifact_id"):
                    if field not in window:
                        errors.append(f"payload.time_context.windows[{index}] 缺少 {field}")
                for field in ("due_at", "captured_at"):
                    if window.get(field) is not None:
                        parse_datetime(window.get(field), f"payload.time_context.windows[{index}].{field}", errors)
                elapsed = window.get("elapsed_hours")
                if elapsed is not None and (not is_number(elapsed) or elapsed < 0):
                    errors.append(f"payload.time_context.windows[{index}].elapsed_hours 必须是非负数")
        for index, hypothesis in enumerate(require_list(payload.get("hypotheses"), "payload.hypotheses", errors)):
            if not isinstance(hypothesis, dict):
                errors.append(f"hypotheses[{index}] 必须是 object")
                continue
            for field in ("hypothesis_id", "statement", "evidence_refs", "alternative_explanations", "confidence"):
                if field not in hypothesis:
                    errors.append(f"hypotheses[{index}] 缺少 {field}")
            if hypothesis.get("confidence") not in {"low", "medium", "high"}:
                errors.append(f"hypotheses[{index}].confidence 无效")
        for index, intervention in enumerate(require_list(payload.get("recommended_interventions"), "payload.recommended_interventions", errors)):
            if not isinstance(intervention, dict) or intervention.get("type") not in {"topic", "creative", "distribution", "positioning", "strategy"}:
                errors.append(f"recommended_interventions[{index}].type 无效")
        lifecycle = require_object(payload.get("lifecycle_assessment"), "payload.lifecycle_assessment", errors)
        if lifecycle.get("current_stage") not in LIFECYCLE_STAGES:
            errors.append("lifecycle_assessment.current_stage 无效")
        proposed_stage = lifecycle.get("proposed_stage")
        if proposed_stage is not None and proposed_stage not in LIFECYCLE_STAGES:
            errors.append("lifecycle_assessment.proposed_stage 无效")
        if lifecycle.get("confidence") not in {"low", "medium", "high"}:
            errors.append("lifecycle_assessment.confidence 无效")
        if lifecycle.get("requires_human_confirmation") is not True:
            errors.append("lifecycle_assessment.requires_human_confirmation 必须为 true")
        require_list(lifecycle.get("evidence_refs"), "lifecycle_assessment.evidence_refs", errors)
        require_list(
            lifecycle.get("alternative_explanations"),
            "lifecycle_assessment.alternative_explanations",
            errors,
        )
        persona_validation = require_object(payload.get("persona_validation"), "payload.persona_validation", errors)
        if persona_validation.get("persona_mode") not in {"assumed", "validated"}:
            errors.append("persona_validation.persona_mode 无效")
        if not isinstance(persona_validation.get("revision_recommended"), bool):
            errors.append("persona_validation.revision_recommended 必须是 boolean")
        hypothesis_results = require_list(
            persona_validation.get("hypothesis_results"),
            "persona_validation.hypothesis_results",
            errors,
        )
        require_list(persona_validation.get("evidence_refs"), "persona_validation.evidence_refs", errors)
        if schema_version == SCHEMA_VERSION:
            require_nonempty_text(
                payload.get("persona_artifact_id"), "payload.persona_artifact_id", errors
            )
            proposed_mode = persona_validation.get("proposed_mode")
            if proposed_mode not in {"assumed", "validated"}:
                errors.append("persona_validation.proposed_mode 无效")
            require_nonempty_text(
                persona_validation.get("scope"), "persona_validation.scope", errors
            )
            result_ids: set[str] = set()
            top_snapshot_ids = set(snapshots)
            for index, result in enumerate(hypothesis_results):
                if not isinstance(result, dict):
                    errors.append(f"persona_validation.hypothesis_results[{index}] 必须是 object")
                    continue
                hypothesis_id = require_nonempty_text(
                    result.get("hypothesis_id"),
                    f"persona_validation.hypothesis_results[{index}].hypothesis_id",
                    errors,
                )
                if hypothesis_id:
                    if hypothesis_id in result_ids:
                        errors.append(
                            f"persona_validation.hypothesis_results[{index}].hypothesis_id 重复"
                        )
                    result_ids.add(hypothesis_id)
                verdict = result.get("verdict")
                if verdict not in POSITIONING_RESULT_VERDICTS:
                    errors.append(f"persona_validation.hypothesis_results[{index}].verdict 无效")
                content_ids = require_nonempty_string_list(
                    result.get("content_artifact_ids"),
                    f"persona_validation.hypothesis_results[{index}].content_artifact_ids",
                    errors,
                )
                if payload.get("content_artifact_id") not in content_ids:
                    errors.append(
                        f"persona_validation.hypothesis_results[{index}] 必须引用本次复盘内容"
                    )
                result_snapshot_ids = require_nonempty_string_list(
                    result.get("snapshot_artifact_ids"),
                    f"persona_validation.hypothesis_results[{index}].snapshot_artifact_ids",
                    errors,
                )
                unknown_snapshots = sorted(set(result_snapshot_ids) - top_snapshot_ids)
                if unknown_snapshots:
                    errors.append(
                        f"persona_validation.hypothesis_results[{index}] 引用了本复盘之外的数据快照："
                        + ", ".join(unknown_snapshots)
                    )
                result_evidence = require_nonempty_string_list(
                    result.get("evidence_refs"),
                    f"persona_validation.hypothesis_results[{index}].evidence_refs",
                    errors,
                )
                require_nonempty_string_list(
                    result.get("counter_evidence_refs"),
                    f"persona_validation.hypothesis_results[{index}].counter_evidence_refs",
                    errors,
                )
                require_nonempty_string_list(
                    result.get("alternative_explanations"),
                    f"persona_validation.hypothesis_results[{index}].alternative_explanations",
                    errors,
                )
                delivery = result.get("delivery_fidelity")
                exposure = result.get("qualified_exposure")
                if delivery not in {"met", "partial", "not_met", "unknown"}:
                    errors.append(
                        f"persona_validation.hypothesis_results[{index}].delivery_fidelity 无效"
                    )
                if exposure not in {"sufficient", "insufficient", "unknown"}:
                    errors.append(
                        f"persona_validation.hypothesis_results[{index}].qualified_exposure 无效"
                    )
                if result.get("confidence") not in {"low", "medium", "high"}:
                    errors.append(f"persona_validation.hypothesis_results[{index}].confidence 无效")
                require_nonempty_text(
                    result.get("scope"),
                    f"persona_validation.hypothesis_results[{index}].scope",
                    errors,
                )
                if verdict in {"supported", "refuted"} and not result_evidence:
                    errors.append(
                        f"persona_validation.hypothesis_results[{index}] 得出方向性结论时必须有证据"
                    )
                if verdict in {"supported", "refuted"} and (
                    delivery != "met" or exposure != "sufficient"
                ):
                    errors.append(
                        f"persona_validation.hypothesis_results[{index}] 内容兑现或有效曝光不足时只能无结论"
                    )

            streams = require_list(
                payload.get("positioning_evidence_streams"),
                "payload.positioning_evidence_streams",
                errors,
            )
            seen_streams: set[str] = set()
            for index, stream in enumerate(streams):
                if not isinstance(stream, dict):
                    errors.append(f"positioning_evidence_streams[{index}] 必须是 object")
                    continue
                stream_name = stream.get("stream")
                if stream_name not in POSITIONING_EVIDENCE_STREAMS:
                    errors.append(f"positioning_evidence_streams[{index}].stream 无效")
                elif stream_name in seen_streams:
                    errors.append(f"positioning_evidence_streams[{index}].stream 重复")
                else:
                    seen_streams.add(stream_name)
                if stream.get("status") not in {
                    "supportive",
                    "concerning",
                    "neutral",
                    "missing",
                    "not_applicable",
                }:
                    errors.append(f"positioning_evidence_streams[{index}].status 无效")
                require_nonempty_text(
                    stream.get("observation"),
                    f"positioning_evidence_streams[{index}].observation",
                    errors,
                )
                require_nonempty_string_list(
                    stream.get("evidence_refs"),
                    f"positioning_evidence_streams[{index}].evidence_refs",
                    errors,
                )
                require_nonempty_string_list(
                    stream.get("limitations"),
                    f"positioning_evidence_streams[{index}].limitations",
                    errors,
                )
            missing_streams = sorted(POSITIONING_EVIDENCE_STREAMS - seen_streams)
            if missing_streams:
                errors.append(
                    "positioning_evidence_streams 必须显式记录全部证据流，缺少："
                    + ", ".join(missing_streams)
                )

            for index, mirror in enumerate(
                require_list(payload.get("market_mirror"), "payload.market_mirror", errors)
            ):
                if not isinstance(mirror, dict):
                    errors.append(f"market_mirror[{index}] 必须是 object")
                    continue
                if mirror.get("signal_type") not in {
                    "recall",
                    "follow_reason",
                    "qualified_demand",
                    "wrong_expectation",
                    "nonresponse",
                }:
                    errors.append(f"market_mirror[{index}].signal_type 无效")
                require_nonempty_text(
                    mirror.get("observation"), f"market_mirror[{index}].observation", errors
                )
                language = mirror.get("audience_language")
                if language is not None and (not isinstance(language, str) or not language.strip()):
                    errors.append(f"market_mirror[{index}].audience_language 必须是非空字符串或 null")
                require_nonempty_string_list(
                    mirror.get("evidence_refs"), f"market_mirror[{index}].evidence_refs", errors
                )
                if mirror.get("confidence") not in {"low", "medium", "high"}:
                    errors.append(f"market_mirror[{index}].confidence 无效")
        require_list(payload.get("trust_observations"), "payload.trust_observations", errors)
        require_list(payload.get("long_tail_observations"), "payload.long_tail_observations", errors)
    elif artifact_type == "experiment":
        intervention = payload.get("intervention_type")
        if intervention not in {"topic", "creative", "distribution", "positioning", "strategy"}:
            errors.append("experiment.intervention_type 无效")
        if intervention == "positioning" and not payload.get("persona_change_proposal"):
            errors.append("positioning 实验必须包含 persona_change_proposal")
        if intervention == "strategy" and not payload.get("strategy_change_proposal"):
            errors.append("strategy 实验必须包含 strategy_change_proposal")
        for field in ("hypothesis", "observation_window", "sample_size_plan", "stop_rule"):
            if not isinstance(payload.get(field), str) or not payload.get(field).strip():
                errors.append(f"experiment.{field} 不能为空")
        if schema_version == SCHEMA_VERSION:
            mode = payload.get("experiment_mode")
            if mode not in {"exploration_probe", "controlled_optimization"}:
                errors.append("experiment.experiment_mode 无效")
            hypothesis_refs = require_nonempty_string_list(
                payload.get("hypothesis_refs"), "experiment.hypothesis_refs", errors
            )
            if intervention == "positioning" and not hypothesis_refs:
                errors.append("定位实验至少需要关联一个 persona 假设")
            diversity = require_nonempty_string_list(
                payload.get("diversity_dimensions"), "experiment.diversity_dimensions", errors
            )
            if mode == "exploration_probe":
                require_nonempty_text(
                    payload.get("probe_question"), "experiment.probe_question", errors
                )
                if not diversity:
                    errors.append("探索实验至少需要一个差异维度")
            if mode == "controlled_optimization":
                for field in ("independent_variable", "control"):
                    require_nonempty_text(payload.get(field), f"experiment.{field}", errors)
            evidence_plan = require_object(
                payload.get("evidence_plan"), "experiment.evidence_plan", errors
            )
            evidence_streams = require_nonempty_string_list(
                evidence_plan.get("required_evidence_streams"),
                "experiment.evidence_plan.required_evidence_streams",
                errors,
            )
            if not evidence_streams:
                errors.append("experiment.evidence_plan 至少需要一个证据流")
            unknown_streams = sorted(set(evidence_streams) - POSITIONING_EVIDENCE_STREAMS)
            if unknown_streams:
                errors.append("experiment.evidence_plan 包含未知证据流：" + ", ".join(unknown_streams))
            for field in ("qualified_exposure_rule", "delivery_fidelity_rule"):
                require_nonempty_text(
                    evidence_plan.get(field), f"experiment.evidence_plan.{field}", errors
                )
            proposal = payload.get("persona_change_proposal")
            if proposal is not None:
                proposal = require_object(proposal, "experiment.persona_change_proposal", errors)
                target_ids = require_nonempty_string_list(
                    proposal.get("target_hypothesis_ids"),
                    "experiment.persona_change_proposal.target_hypothesis_ids",
                    errors,
                )
                if not target_ids:
                    errors.append("persona_change_proposal 至少需要一个目标假设")
                if proposal.get("action") not in {"keep", "revise", "retire", "reopen"}:
                    errors.append("persona_change_proposal.action 无效")
                require_nonempty_text(
                    proposal.get("rationale"), "persona_change_proposal.rationale", errors
                )
                proposal_evidence = require_nonempty_string_list(
                    proposal.get("evidence_refs"),
                    "persona_change_proposal.evidence_refs",
                    errors,
                )
                if not proposal_evidence:
                    errors.append("persona_change_proposal 必须引用复盘证据")
                require_nonempty_string_list(
                    proposal.get("counter_evidence_refs"),
                    "persona_change_proposal.counter_evidence_refs",
                    errors,
                )
                if proposal.get("requires_new_persona_revision") is not True:
                    errors.append("persona_change_proposal 必须要求新建 persona revision")
                require_nonempty_string_list(
                    proposal.get("migration_actions"),
                    "persona_change_proposal.migration_actions",
                    errors,
                )
        else:
            for field in ("independent_variable", "control"):
                if not isinstance(payload.get(field), str) or not payload.get(field).strip():
                    errors.append(f"experiment.{field} 不能为空")

    errors.extend(optional_json_schema_errors(artifact))
    return errors


def find_workspace(start: Path) -> Path:
    start = start.resolve()
    candidates: Iterable[Path] = (start, *start.parents) if start.is_dir() else (start.parent, *start.parents)
    for candidate in candidates:
        if (candidate / "workspace.json").is_file():
            return candidate
    raise WorkflowError(f"无法从 {start} 定位 workspace.json")


def workspace_relative_path(root: Path, raw_path: str, field: str) -> Path:
    candidate = Path(raw_path)
    path = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise WorkflowError(f"{field} 越出当前工作区") from exc
    return path


def load_account_artifact(
    root: Path,
    account_id: str,
    artifact_type: str,
    artifact_id: Any,
) -> tuple[dict[str, Any], Path]:
    if not isinstance(artifact_id, str) or not ID_RE.fullmatch(artifact_id):
        raise WorkflowError(f"{artifact_type} 引用不是有效 artifact_id：{artifact_id}")
    path = root / "artifacts" / account_id / artifact_type / f"{artifact_id}.json"
    artifact = load_json(path)
    if artifact.get("artifact_type") != artifact_type or artifact.get("artifact_id") != artifact_id:
        raise WorkflowError(f"{artifact_id} 未解析到正确的 {artifact_type}")
    if artifact.get("account_id") != account_id:
        raise WorkflowError(f"{artifact_id} 不属于当前账号")
    artifact_errors = validate_artifact(artifact)
    if artifact_errors:
        raise WorkflowError(f"{artifact_id} 未通过校验：" + "; ".join(artifact_errors))
    return artifact, path


def positioning_trace_errors(
    trace: Any,
    persona: dict[str, Any],
    field: str,
) -> list[str]:
    errors: list[str] = []
    trace = validate_positioning_trace(trace, field, errors)
    payload = persona.get("payload", {})
    if persona.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{field} 必须关联当前 Schema 的定位记录")
        return errors
    if trace.get("persona_revision") != payload.get("revision"):
        errors.append(f"{field}.persona_revision 与关联定位版本不一致")
    audience_ids = {
        item.get("segment_id")
        for item in payload.get("audience", [])
        if isinstance(item, dict)
    }
    hypothesis_by_id = {
        item.get("hypothesis_id"): item
        for item in payload.get("hypotheses", [])
        if isinstance(item, dict) and isinstance(item.get("hypothesis_id"), str)
    }
    unknown_audiences = sorted(set(trace.get("audience_segment_refs", [])) - audience_ids)
    if unknown_audiences:
        errors.append(f"{field} 引用了不存在的受众分组：" + ", ".join(unknown_audiences))
    unknown_hypotheses = sorted(set(trace.get("hypothesis_refs", [])) - set(hypothesis_by_id))
    if unknown_hypotheses:
        errors.append(f"{field} 引用了不存在的定位假设：" + ", ".join(unknown_hypotheses))
    retired = sorted(
        hypothesis_id
        for hypothesis_id in trace.get("hypothesis_refs", [])
        if hypothesis_by_id.get(hypothesis_id, {}).get("status") == "refuted"
    )
    if retired:
        errors.append(f"{field} 不得继续把已反驳假设作为内容目标：" + ", ".join(retired))
    pillar = next(
        (
            item
            for item in payload.get("content_pillars", [])
            if isinstance(item, dict) and item.get("pillar_id") == trace.get("pillar_id")
        ),
        None,
    )
    if not isinstance(pillar, dict):
        errors.append(f"{field}.pillar_id 未解析到定位中的内容支柱")
        return errors
    if not set(trace.get("audience_segment_refs", [])).issubset(
        set(pillar.get("audience_segment_refs", []))
    ):
        errors.append(f"{field} 的受众不属于所选内容支柱")
    if not set(trace.get("hypothesis_refs", [])).issubset(set(pillar.get("hypothesis_refs", []))):
        errors.append(f"{field} 的假设不属于所选内容支柱")
    for name in ("audience_job", "value_delivered", "proof_role", "memory_asset"):
        if trace.get(name) != pillar.get(name):
            errors.append(f"{field}.{name} 与所选内容支柱不一致")
    return errors


def require_topic_positioning_links(root: Path, topic_report: dict[str, Any]) -> None:
    payload = topic_report.get("payload", {})
    persona, _ = load_account_artifact(
        root,
        topic_report["account_id"],
        "persona",
        payload.get("persona_artifact_id"),
    )
    if not effective_approval(persona, "G1"):
        raise WorkflowError("G2 前需要关联当前有效的账号定位确认")
    if persona.get("payload", {}).get("strategy_artifact_id") != payload.get("strategy_artifact_id"):
        raise WorkflowError("选题报告与定位引用的账号战略不一致")
    link_errors: list[str] = []
    for index, candidate in enumerate(payload.get("candidates", [])):
        link_errors.extend(
            positioning_trace_errors(
                candidate.get("positioning_trace") if isinstance(candidate, dict) else None,
                persona,
                f"candidates[{index}].positioning_trace",
            )
        )
    if link_errors:
        raise WorkflowError("选题定位追踪未闭合：" + "; ".join(link_errors))


def require_content_positioning_links(root: Path, content: dict[str, Any]) -> None:
    payload = content.get("payload", {})
    persona, _ = load_account_artifact(
        root,
        content["account_id"],
        "persona",
        payload.get("persona_artifact_id"),
    )
    if not effective_approval(persona, "G1"):
        raise WorkflowError("G3 前需要关联当前有效的账号定位确认")
    link_errors = positioning_trace_errors(
        payload.get("positioning_trace"), persona, "content.positioning_trace"
    )
    if link_errors:
        raise WorkflowError("内容定位追踪未闭合：" + "; ".join(link_errors))
    topic_report, _ = load_account_artifact(
        root,
        content["account_id"],
        "topic_report",
        payload.get("topic_report_artifact_id"),
    )
    if not effective_approval(topic_report, "G2"):
        raise WorkflowError("G3 前需要关联当前有效的选题确认")
    topic_payload = topic_report.get("payload", {})
    if topic_payload.get("persona_artifact_id") != payload.get("persona_artifact_id"):
        raise WorkflowError("内容与选题报告引用的定位版本不一致")
    if topic_payload.get("strategy_artifact_id") != payload.get("strategy_artifact_id"):
        raise WorkflowError("内容与选题报告引用的账号战略不一致")
    candidate = next(
        (
            item
            for item in topic_payload.get("candidates", [])
            if isinstance(item, dict) and item.get("topic_id") == payload.get("topic_id")
        ),
        None,
    )
    if not isinstance(candidate, dict) or payload.get("topic_id") not in topic_payload.get(
        "selected_topic_ids", []
    ):
        raise WorkflowError("内容 topic_id 未解析到已确认的选题")
    if candidate.get("positioning_trace") != payload.get("positioning_trace"):
        raise WorkflowError("内容定位追踪必须与已确认选题保持一致；变化时应先修订选题")


def require_review_positioning_links(root: Path, review: dict[str, Any]) -> None:
    payload = review.get("payload", {})
    persona, _ = load_account_artifact(
        root,
        review["account_id"],
        "persona",
        payload.get("persona_artifact_id"),
    )
    content, _ = load_account_artifact(
        root,
        review["account_id"],
        "content",
        payload.get("content_artifact_id"),
    )
    if content.get("payload", {}).get("persona_artifact_id") != persona.get("artifact_id"):
        raise WorkflowError("复盘、内容与账号定位引用不一致")
    persona_validation = payload.get("persona_validation", {})
    if persona_validation.get("persona_mode") != persona.get("payload", {}).get("mode"):
        raise WorkflowError("复盘记录的当前定位状态与关联 persona 不一致")
    traced_ids = set(content.get("payload", {}).get("positioning_trace", {}).get("hypothesis_refs", []))
    result_ids = {
        item.get("hypothesis_id")
        for item in persona_validation.get("hypothesis_results", [])
        if isinstance(item, dict)
    }
    if traced_ids != result_ids:
        missing = sorted(traced_ids - result_ids)
        extra = sorted(result_ids - traced_ids)
        details = []
        if missing:
            details.append("缺少结果：" + ", ".join(missing))
        if extra:
            details.append("出现未测试结果：" + ", ".join(extra))
        raise WorkflowError("复盘必须逐项回应内容绑定的定位假设；" + "；".join(details))
    for snapshot_id in payload.get("snapshot_artifact_ids", []):
        snapshot, _ = load_account_artifact(
            root, review["account_id"], "metrics_snapshot", snapshot_id
        )
        if snapshot.get("status") != "ready":
            raise WorkflowError(f"复盘引用的数据快照尚未 ready：{snapshot_id}")
        if snapshot.get("payload", {}).get("content_artifact_id") != content.get("artifact_id"):
            raise WorkflowError(f"数据快照不属于本次复盘内容：{snapshot_id}")


def require_stable_persona_evidence(root: Path, persona: dict[str, Any]) -> None:
    payload = persona.get("payload", {})
    strategy, _ = load_account_artifact(
        root,
        persona["account_id"],
        "account_strategy",
        payload.get("strategy_artifact_id"),
    )
    if not effective_approval(strategy, "G1"):
        raise WorkflowError("稳定定位批准前需要当前有效的账号战略确认")
    if strategy.get("payload", {}).get("persona_mode") != "validated":
        raise WorkflowError("稳定定位批准前，关联账号战略必须明确 persona_mode=validated")
    predecessor_id = payload.get("supersedes_artifact_id")
    predecessor, _ = load_account_artifact(
        root, persona["account_id"], "persona", predecessor_id
    )
    if not effective_approval(predecessor, "G1"):
        raise WorkflowError("稳定定位必须引用一份当前有效、已经确认的上一版本定位")
    predecessor_hypotheses = {
        item.get("hypothesis_id"): item
        for item in predecessor.get("payload", {}).get("hypotheses", [])
        if isinstance(item, dict)
    }
    established = {
        item.get("hypothesis_id"): item
        for item in payload.get("hypotheses", [])
        if isinstance(item, dict) and item.get("status") == "provisionally_established"
    }
    for hypothesis_id, item in established.items():
        previous = predecessor_hypotheses.get(hypothesis_id)
        if not isinstance(previous, dict) or previous.get("statement") != item.get("statement"):
            raise WorkflowError(
                f"阶段性成立的假设 {hypothesis_id} 必须能追溯到上一版本的同一陈述"
            )

    evidence = payload.get("validation_evidence", {})
    supported_ids: set[str] = set()
    supported_content_ids: set[str] = set()
    supported_snapshot_ids: set[str] = set()
    actual_streams: set[str] = set()
    supportive_streams: set[str] = set()
    market_mirror_count = 0
    for review_id in evidence.get("review_artifact_refs", []):
        review, _ = load_account_artifact(
            root, persona["account_id"], "review", review_id
        )
        if review.get("status") != "ready":
            raise WorkflowError(f"稳定定位引用的复盘尚未 ready：{review_id}")
        require_review_positioning_links(root, review)
        review_payload = review.get("payload", {})
        if review_payload.get("persona_artifact_id") != predecessor_id:
            raise WorkflowError(f"复盘 {review_id} 没有评估被替代的定位版本")
        for stream in review_payload.get("positioning_evidence_streams", []):
            if isinstance(stream, dict) and stream.get("status") not in {"missing", "not_applicable"}:
                actual_streams.add(stream.get("stream"))
                if stream.get("status") == "supportive":
                    supportive_streams.add(stream.get("stream"))
        market_mirror_count += len(review_payload.get("market_mirror", []))
        for result in review_payload.get("persona_validation", {}).get("hypothesis_results", []):
            if not isinstance(result, dict):
                continue
            if (
                result.get("verdict") == "supported"
                and result.get("delivery_fidelity") == "met"
                and result.get("qualified_exposure") == "sufficient"
            ):
                supported_ids.add(result.get("hypothesis_id"))
                supported_content_ids.update(result.get("content_artifact_ids", []))
                supported_snapshot_ids.update(result.get("snapshot_artifact_ids", []))
    missing_hypotheses = sorted(set(established) - supported_ids)
    if missing_hypotheses:
        raise WorkflowError("稳定定位缺少合格复盘支持的假设：" + ", ".join(missing_hypotheses))
    declared_content_ids = set(evidence.get("content_artifact_refs", []))
    if not declared_content_ids.issubset(supported_content_ids):
        raise WorkflowError("validation_evidence.content_artifact_refs 含未被支持性结果引用的内容")
    declared_snapshot_ids = set(evidence.get("snapshot_artifact_refs", []))
    if not declared_snapshot_ids.issubset(supported_snapshot_ids):
        raise WorkflowError("validation_evidence.snapshot_artifact_refs 含未被支持性结果引用的数据快照")
    missing_actual_streams = sorted(REQUIRED_STABLE_EVIDENCE_STREAMS - actual_streams)
    if missing_actual_streams:
        raise WorkflowError("实际复盘仍缺少稳定定位证据流：" + ", ".join(missing_actual_streams))
    missing_supportive_streams = sorted(
        {"audience_resonance", "delivery_fidelity", "creator_fit"} - supportive_streams
    )
    if missing_supportive_streams:
        raise WorkflowError("稳定定位缺少正向证据流：" + ", ".join(missing_supportive_streams))
    if market_mirror_count == 0:
        raise WorkflowError("稳定定位前至少需要一条受众市场镜像，不能只依赖平台指标")
    if not set(evidence.get("evidence_streams_covered", [])).issubset(actual_streams):
        raise WorkflowError("validation_evidence 声明了复盘中并未实际覆盖的证据流")
    for content_id in declared_content_ids:
        linked_content, content_path = load_account_artifact(
            root, persona["account_id"], "content", content_id
        )
        if not effective_content_approval(linked_content, content_path):
            raise WorkflowError(f"稳定定位引用的内容缺少有效定稿确认：{content_id}")
    for snapshot_id in declared_snapshot_ids:
        snapshot, _ = load_account_artifact(
            root, persona["account_id"], "metrics_snapshot", snapshot_id
        )
        if snapshot.get("status") != "ready":
            raise WorkflowError(f"稳定定位引用的数据快照尚未 ready：{snapshot_id}")


def require_experiment_positioning_links(root: Path, experiment: dict[str, Any]) -> None:
    payload = experiment.get("payload", {})
    review, _ = load_account_artifact(
        root,
        experiment["account_id"],
        "review",
        payload.get("review_artifact_id"),
    )
    if review.get("status") != "ready":
        raise WorkflowError("G6 前关联复盘必须是 ready")
    result_ids = {
        item.get("hypothesis_id")
        for item in review.get("payload", {}).get("persona_validation", {}).get(
            "hypothesis_results", []
        )
        if isinstance(item, dict)
    }
    hypothesis_refs = set(payload.get("hypothesis_refs", []))
    unknown = sorted(hypothesis_refs - result_ids)
    if unknown:
        raise WorkflowError("实验引用了复盘未评估的定位假设：" + ", ".join(unknown))
    proposal = payload.get("persona_change_proposal")
    if isinstance(proposal, dict):
        proposal_targets = set(proposal.get("target_hypothesis_ids", []))
        if not proposal_targets.issubset(hypothesis_refs):
            raise WorkflowError("定位修订建议只能作用于本实验关联的定位假设")


def strategy_lineage_contains(
    root: Path,
    account_id: str,
    current_strategy: dict[str, Any],
    ancestor_id: str,
) -> bool:
    """Return whether current_strategy is ancestor_id or descends from it."""
    cursor = current_strategy
    seen: set[str] = set()
    while isinstance(cursor, dict):
        cursor_id = cursor.get("artifact_id")
        if cursor_id == ancestor_id:
            return True
        if not isinstance(cursor_id, str) or cursor_id in seen:
            raise WorkflowError("账号战略版本谱系存在循环或无效编号")
        seen.add(cursor_id)
        parent_id = cursor.get("payload", {}).get("supersedes_artifact_id")
        if not isinstance(parent_id, str) or not parent_id:
            return False
        cursor, _ = load_account_artifact(
            root, account_id, "account_strategy", parent_id
        )
    return False


def require_persona_revision_lineage(root: Path, persona: dict[str, Any]) -> None:
    """Prevent a current-schema persona revision from bypassing strategy or evidence lineage."""
    payload = persona.get("payload", {})
    revision = payload.get("revision")
    predecessor_id = payload.get("supersedes_artifact_id")
    diagnosis = payload.get("positioning_diagnosis", {})
    evidence = payload.get("validation_evidence", {})
    experiment_refs = evidence.get("experiment_artifact_refs", [])

    if revision == 1:
        if predecessor_id is not None:
            raise WorkflowError("首版定位不得声明 supersedes_artifact_id")
        if diagnosis.get("diagnosis_type") != "initial_definition":
            raise WorkflowError("首版定位必须明确记录为首次建立")
        if experiment_refs:
            raise WorkflowError("首版定位没有上一版，不得声明承接定位修订实验")
        return

    if not isinstance(revision, int) or revision < 2 or not isinstance(predecessor_id, str):
        raise WorkflowError("非首版定位必须使用新 revision 并回指上一版")
    predecessor, _ = load_account_artifact(
        root, persona["account_id"], "persona", predecessor_id
    )
    if not effective_approval(predecessor, "G1"):
        raise WorkflowError("定位修订必须回指当前有效、已确认的上一版定位")
    predecessor_revision = predecessor.get("payload", {}).get("revision")
    if not isinstance(predecessor_revision, int) or revision != predecessor_revision + 1:
        raise WorkflowError("定位 revision 必须在上一版基础上连续递增")
    if diagnosis.get("diagnosis_type") == "initial_definition":
        raise WorkflowError("非首版定位不得再标记为首次建立")

    strategy, _ = load_account_artifact(
        root,
        persona["account_id"],
        "account_strategy",
        payload.get("strategy_artifact_id"),
    )
    predecessor_strategy_id = predecessor.get("payload", {}).get("strategy_artifact_id")
    if not isinstance(predecessor_strategy_id, str) or not strategy_lineage_contains(
        root, persona["account_id"], strategy, predecessor_strategy_id
    ):
        raise WorkflowError("新定位引用的账号战略不在上一版战略的版本谱系中")
    strategy_changed = strategy.get("artifact_id") != predecessor_strategy_id

    review_refs = evidence.get("review_artifact_refs", [])
    if not strategy_changed and not review_refs:
        raise WorkflowError("同一账号战略下修订定位，至少需要一份评估上一版定位的真实复盘")

    declared_review_ids = set(review_refs)
    for review_id in review_refs:
        review, _ = load_account_artifact(
            root, persona["account_id"], "review", review_id
        )
        if review.get("status") != "ready":
            raise WorkflowError(f"定位修订引用的复盘尚未 ready：{review_id}")
        require_review_positioning_links(root, review)
        if review.get("payload", {}).get("persona_artifact_id") != predecessor_id:
            raise WorkflowError(f"复盘 {review_id} 没有评估被替代的定位版本")

    for experiment_id in experiment_refs:
        experiment, _ = load_account_artifact(
            root, persona["account_id"], "experiment", experiment_id
        )
        if not effective_approval(experiment, "G6"):
            raise WorkflowError(f"定位修订引用的实验缺少当前有效 G6：{experiment_id}")
        require_experiment_positioning_links(root, experiment)
        linked_review_id = experiment.get("payload", {}).get("review_artifact_id")
        if linked_review_id not in declared_review_ids:
            raise WorkflowError(
                f"实验 {experiment_id} 的关联复盘未列入 validation_evidence.review_artifact_refs"
            )


def require_independent_review_capability(root: Path, content: dict[str, Any]) -> None:
    run_id = content.get("run_id")
    run = load_json(root / "runs" / str(run_id) / "run.json")
    capability = (
        run.get("payload", {})
        .get("runtime_capabilities", {})
        .get("capabilities", {})
        .get("independent_agent_review", {})
    )
    if capability.get("status") != "available" or not capability.get("capability_id"):
        raise WorkflowError(
            "本轮尚未确认可启动独立上下文的文章审计 Agent，不能进入独立审计或内容定稿"
        )


def load_linked_article_audit(
    content: dict[str, Any],
    content_path: Path,
) -> tuple[dict[str, Any], Path]:
    root = find_workspace(content_path)
    ref = content.get("payload", {}).get("article_audit_ref")
    if not isinstance(ref, dict):
        raise WorkflowError("content 尚未绑定独立文章审计")
    raw_audit_path = ref.get("artifact_path")
    if not isinstance(raw_audit_path, str) or not raw_audit_path:
        raise WorkflowError("content.article_audit_ref 缺少审计记录位置")
    audit_path = workspace_relative_path(root, raw_audit_path, "独立审计记录位置")
    audit = load_json(audit_path)
    if audit.get("artifact_type") != "article_audit":
        raise WorkflowError("content.article_audit_ref 未指向 article_audit artifact")
    if audit.get("artifact_id") != ref.get("artifact_id"):
        raise WorkflowError("content.article_audit_ref 的 artifact_id 与文件不一致")
    if audit.get("account_id") != content.get("account_id") or audit.get("run_id") != content.get("run_id"):
        raise WorkflowError("独立审计与 content 的 account_id/run_id 不一致")
    audit_errors = validate_artifact(audit)
    binding_errors = article_audit_contract().validate_audit_document(audit, content=content)
    errors = audit_errors + [item for item in binding_errors if item not in audit_errors]
    if errors:
        raise WorkflowError("独立文章审计未通过校验：" + "; ".join(errors))
    actual_audit_hash = article_audit_contract().audit_payload_hash(audit)
    if ref.get("payload_sha256") != actual_audit_hash:
        raise WorkflowError("独立审计 artifact 已在绑定后发生变化")
    actual_content_hash = article_audit_contract().auditable_content_hash(content)
    if ref.get("content_sha256") != actual_content_hash:
        raise WorkflowError("content 已在独立审计后发生变化，必须重新审计")
    try:
        content_relative = str(content_path.resolve().relative_to(root))
    except ValueError as exc:
        raise WorkflowError("content 越出当前工作区") from exc
    if audit.get("payload", {}).get("target_uri") != content_relative:
        raise WorkflowError("独立审计记录的 target_uri 与当前 content 路径不一致")
    return audit, audit_path


def latest_effective_gate_approval(
    artifact: dict[str, Any], gate: str
) -> dict[str, Any] | None:
    current_hash = payload_hash(artifact, gate)
    approvals = artifact.get("approvals", [])
    if not isinstance(approvals, list):
        return None
    for approval in reversed(approvals):
        if not isinstance(approval, dict) or approval.get("gate") != gate:
            continue
        if approval.get("decision") != "approved":
            return None
        return approval if approval.get("payload_sha256") == current_hash else None
    return None


def effective_content_approval(content: dict[str, Any], content_path: Path) -> bool:
    approval = latest_effective_gate_approval(content, "G3")
    if approval is None:
        return False
    try:
        audit, _ = load_linked_article_audit(content, content_path)
    except WorkflowError:
        return False
    verdict = audit.get("payload", {}).get("summary", {}).get("verdict")
    if verdict == "passed":
        return True
    if verdict == "human_decision_required":
        return bool(str(approval.get("notes") or "").strip())
    return False


def append_audit(root: Path, event: dict[str, Any]) -> None:
    audit_path = root / "audit" / "events.ndjson"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def audit_event(
    root: Path,
    artifact: dict[str, Any],
    actor: str,
    actor_type: str,
    event_type: str,
    reason: str,
    before_status: str | None = None,
    after_status: str | None = None,
) -> None:
    append_audit(
        root,
        {
            "event_id": new_id("event"),
            "at": now_iso(),
            "actor_id": actor,
            "actor_type": actor_type,
            "event_type": event_type,
            "artifact_id": artifact.get("artifact_id"),
            "account_id": artifact.get("account_id"),
            "run_id": artifact.get("run_id"),
            "before_status": before_status,
            "after_status": after_status,
            "payload_sha256": payload_hash(artifact),
            "reason": reason,
        },
    )


def command_init(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    if not ACCOUNT_RE.fullmatch(args.account_id):
        raise WorkflowError("account-id 只能包含小写字母、数字、下划线和连字符，长度 2-64")
    root.mkdir(parents=True, exist_ok=True)
    workspace_path = root / "workspace.json"
    if workspace_path.exists():
        workspace = load_json(workspace_path)
        if workspace.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
            raise WorkflowError("现有 workspace.json 版本不兼容")
        workspace["schema_version"] = SCHEMA_VERSION
    else:
        workspace = {
            "schema_version": SCHEMA_VERSION,
            "workspace_id": new_id("workspace"),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "account_ids": [],
        }
    account_path = root / "accounts" / args.account_id / "account.json"
    if account_path.exists():
        raise WorkflowError(f"账号已存在：{args.account_id}")
    account = {
        "schema_version": SCHEMA_VERSION,
        "account_id": args.account_id,
        "display_name": args.display_name,
        "platform": "xiaohongshu",
        "created_at": now_iso(),
        "status": "active",
    }
    atomic_write_json(account_path, account)
    if args.account_id not in workspace["account_ids"]:
        workspace["account_ids"].append(args.account_id)
        workspace["account_ids"].sort()
    workspace["updated_at"] = now_iso()
    atomic_write_json(workspace_path, workspace)
    for relative in ("runs", "artifacts", "assets", "renders", "audit"):
        (root / relative).mkdir(exist_ok=True)
    audit_event(root, {"artifact_id": None, "account_id": args.account_id, "run_id": None, "payload": account}, args.actor, "human", "account_initialized", "创建账号隔离工作区")
    print(account_path)


def command_new_run(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    workspace = load_json(root / "workspace.json")
    if args.account_id not in workspace.get("account_ids", []):
        raise WorkflowError(f"工作区不存在账号：{args.account_id}")
    run_type = args.run_type
    strategy: dict[str, Any] | None = None
    persona: dict[str, Any] | None = None
    artifact_paths: dict[str, str] = {}

    def load_account_reference(raw_path: str | None, expected_type: str, role: str) -> dict[str, Any] | None:
        if not raw_path:
            return None
        candidate = Path(raw_path)
        path = (candidate if candidate.is_absolute() else root / candidate).resolve()
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise WorkflowError(f"{role} 必须位于当前工作区") from exc
        artifact = load_json(path)
        artifact_errors = validate_artifact(artifact)
        if artifact_errors:
            raise WorkflowError(f"{role} 未通过校验：" + "; ".join(artifact_errors))
        if artifact.get("artifact_type") != expected_type:
            raise WorkflowError(f"{role} 必须指向 {expected_type}")
        if artifact.get("account_id") != args.account_id:
            raise WorkflowError(f"{role} 与本轮 account_id 不一致")
        if artifact.get("status") != "approved":
            raise WorkflowError(f"{role} 必须是 approved，不能引用 {artifact.get('status')} revision")
        if not effective_approval(artifact, "G1"):
            raise WorkflowError(f"{role} 必须具有当前 payload 对应的有效 G1 批准")
        artifact_paths[role] = str(relative)
        return artifact

    strategy = load_account_reference(args.strategy, "account_strategy", "account_strategy")
    persona = load_account_reference(args.persona, "persona", "persona")
    operational_types = RUN_TYPES - {"full_cycle", "strategy_review"}
    if run_type in operational_types and (strategy is None or persona is None):
        raise WorkflowError(f"{run_type} run 必须显式提供已批准的 --strategy 和 --persona")
    if persona and strategy and persona.get("payload", {}).get("strategy_artifact_id") != strategy.get("artifact_id"):
        raise WorkflowError("persona.strategy_artifact_id 与 --strategy 不一致")
    if run_type == "trial_content" and persona and persona.get("payload", {}).get("mode") != "assumed":
        raise WorkflowError("trial_content 必须使用 mode=assumed 的试运营 persona")
    if run_type == "trial_content" and args.content_sequence_no is None:
        raise WorkflowError("trial_content 必须提供 --content-sequence-no")

    run_id = new_id("run")
    timestamp = now_iso()
    strategy_measurement = strategy.get("payload", {}).get("measurement_policy", {}) if strategy else {}
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "run_manifest",
        "artifact_id": new_id("run_manifest"),
        "account_id": args.account_id,
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "status": "review_required",
        "provenance": [
            {
                "source_id": new_id("source"),
                "kind": "user_input",
                "captured_at": timestamp,
                "summary": f"由 {args.actor} 发起本轮目标",
            }
        ],
        "approvals": [],
        "payload": {
            "objective": args.objective,
            "run_type": run_type,
            "strategy_artifact_id": strategy.get("artifact_id") if strategy else None,
            "persona_artifact_id": persona.get("artifact_id") if persona else None,
            "content_sequence_no": args.content_sequence_no,
            "current_stage": "scope",
            "runtime_capabilities": default_runtime_capabilities(timestamp, args.runtime_name),
            "data_scope": {
                "allowed_sources": [],
                "external_processing": [],
                "personal_data": [],
            },
            "measurement_plan": {
                "snapshot_windows": [],
                "trust_metrics": list(strategy_measurement.get("trust_metrics", [])),
                "long_tail_checkpoints_days": list(strategy_measurement.get("long_tail_checkpoints_days", [])),
                "qualitative_rubric_refs": list(strategy_measurement.get("qualitative_rubric_refs", [])),
            },
            "artifact_paths": artifact_paths,
            "gate_status": {gate: "pending" for gate in sorted(GATES)},
            "errors": [],
        },
    }
    if strategy is not None and persona is not None:
        artifact["payload"]["gate_status"]["G1"] = "approved"
    errors = validate_artifact(artifact)
    if errors:
        raise WorkflowError("无法创建 run：" + "; ".join(errors))
    path = root / "runs" / run_id / "run.json"
    atomic_write_json(path, artifact)
    audit_event(root, artifact, args.actor, "human", "run_created", args.objective, None, artifact["status"])
    print(path)


def command_validate(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    errors = validate_artifact(load_json(path))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise WorkflowError(f"校验失败，共 {len(errors)} 项")
    print(f"PASS: {path}")


def command_validate_workspace(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    load_json(root / "workspace.json")
    files = sorted((root / "runs").glob("**/*.json")) + sorted((root / "artifacts").glob("**/*.json"))
    failed = 0
    for path in files:
        errors = validate_artifact(load_json(path))
        if errors:
            failed += 1
            print(f"FAIL: {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS: {path}")
    if failed:
        raise WorkflowError(f"工作区有 {failed} 个不合法 artifact")
    print(f"PASS: {len(files)} artifacts")


def command_link_article_audit(args: argparse.Namespace) -> None:
    content_path = Path(args.content).resolve()
    audit_path = Path(args.audit).resolve()
    content = load_json(content_path)
    audit = load_json(audit_path)
    if content.get("artifact_type") != "content":
        raise WorkflowError("--content 必须指向 content artifact")
    if audit.get("artifact_type") != "article_audit":
        raise WorkflowError("--audit 必须指向 article_audit artifact")
    if effective_approval(content, "G3"):
        raise WorkflowError("当前 content 已具有有效 G3；请先由内容负责人撤销定稿确认")
    content_errors = validate_artifact(content)
    if content_errors:
        raise WorkflowError("content 未通过校验：" + "; ".join(content_errors))
    audit_errors = validate_artifact(audit)
    if audit_errors:
        raise WorkflowError("article_audit 未通过校验：" + "; ".join(audit_errors))
    root = find_workspace(content_path)
    audit_root = find_workspace(audit_path)
    if audit_root != root:
        raise WorkflowError("content 与 article_audit 必须位于同一工作区")
    require_independent_review_capability(root, content)
    try:
        content_relative = str(content_path.relative_to(root))
        audit_relative = str(audit_path.relative_to(root))
    except ValueError as exc:
        raise WorkflowError("content 与 article_audit 必须位于当前工作区") from exc
    if audit.get("payload", {}).get("target_uri") != content_relative:
        raise WorkflowError("article_audit.target_uri 与当前 content 路径不一致")
    binding_errors = article_audit_contract().validate_audit_document(audit, content=content)
    if binding_errors:
        raise WorkflowError("article_audit 与 content 绑定校验失败：" + "; ".join(binding_errors))
    content_hash = article_audit_contract().auditable_content_hash(content)
    content["payload"]["article_audit_ref"] = {
        "artifact_id": audit["artifact_id"],
        "artifact_path": audit_relative,
        "payload_sha256": article_audit_contract().audit_payload_hash(audit),
        "content_sha256": content_hash,
    }
    before = content.get("status")
    content["status"] = "review_required"
    content["updated_at"] = now_iso()
    linked_errors = validate_artifact(content)
    if linked_errors:
        raise WorkflowError("绑定审计后的 content 不合法：" + "; ".join(linked_errors))
    run_path = root / "runs" / str(content.get("run_id")) / "run.json"
    run = load_json(run_path)
    run["payload"]["artifact_paths"]["article_audit"] = audit_relative
    run["payload"]["gate_status"]["G3"] = "pending"
    run["payload"]["current_stage"] = "content"
    run["updated_at"] = now_iso()
    run_errors = validate_artifact(run)
    if run_errors:
        raise WorkflowError("登记独立审计后的 run manifest 不合法：" + "; ".join(run_errors))
    atomic_write_json(content_path, content)
    atomic_write_json(run_path, run)
    audit_event(
        root,
        content,
        args.actor,
        args.actor_type,
        "article_audit_linked",
        audit["artifact_id"],
        before,
        content["status"],
    )
    print(content_path)


def command_approve(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    artifact = load_json(path)
    artifact_type = artifact.get("artifact_type")
    if args.gate not in GATE_BY_TYPE.get(artifact_type, set()):
        raise WorkflowError(f"{artifact_type} 不接受门禁 {args.gate}")
    if args.decision == "approved" and args.gate == "G2" and not artifact.get("payload", {}).get("selected_topic_ids"):
        raise WorkflowError("G2 批准前必须明确 selected_topic_ids")
    if (
        args.decision == "approved"
        and args.gate == "G2"
        and artifact.get("schema_version") == SCHEMA_VERSION
    ):
        require_topic_positioning_links(find_workspace(path), artifact)
    if args.decision == "approved" and args.gate == "G1" and artifact_type == "account_strategy":
        strategy_payload = artifact.get("payload", {})
        if not strategy_payload.get("stage_evidence"):
            raise WorkflowError("账号战略 G1 批准前至少需要一条 stage_evidence")
        if not strategy_payload.get("content_objectives"):
            raise WorkflowError("账号战略 G1 批准前至少需要一个 content_objective")
        if artifact.get("schema_version") in DIRECTION_SCHEMA_VERSIONS:
            direction = strategy_payload.get("creator_direction")
            if not isinstance(direction, dict):
                raise WorkflowError("账号战略 G1 批准前必须完成创作者方向")
            for field in (
                "primary_90_day_outcome",
                "business_destination",
                "audience_business_fit",
                "current_value",
                "future_value",
                "relationship_posture",
                "trust_engine",
                "content_engine",
            ):
                if not isinstance(direction.get(field), str) or not direction[field].strip():
                    raise WorkflowError(f"账号战略 G1 批准前必须填写 creator_direction.{field}")
            memory_assets = direction.get("memory_assets")
            if not isinstance(memory_assets, dict) or not isinstance(memory_assets.get("primary"), str) or not memory_assets["primary"].strip():
                raise WorkflowError("账号战略 G1 批准前必须确定一个主记忆资产")
            if not direction.get("evidence_refs"):
                raise WorkflowError("账号战略 G1 批准前必须记录创作者方向的 evidence_refs")
    if args.decision == "approved" and args.gate == "G1" and artifact_type == "persona":
        root = find_workspace(path)
        persona_payload = artifact.get("payload", {})
        strategy, _ = load_account_artifact(
            root,
            artifact["account_id"],
            "account_strategy",
            persona_payload.get("strategy_artifact_id"),
        )
        if not effective_approval(strategy, "G1"):
            raise WorkflowError("账号定位 G1 前需要当前有效的账号战略确认")
        if strategy.get("payload", {}).get("persona_mode") != persona_payload.get("mode"):
            raise WorkflowError("账号战略与账号定位的定位成熟度摘要不一致")
        if artifact.get("schema_version") == SCHEMA_VERSION:
            require_persona_revision_lineage(root, artifact)
            if persona_payload.get("mode") == "validated":
                require_stable_persona_evidence(root, artifact)
    if args.decision == "approved" and args.gate == "G3":
        content_payload = artifact.get("payload", {})
        if not isinstance(content_payload.get("authorship"), dict):
            raise WorkflowError("G3 批准前必须记录稿件作者身份")
        root = find_workspace(path)
        if artifact.get("schema_version") == SCHEMA_VERSION:
            require_content_positioning_links(root, artifact)
        require_independent_review_capability(root, artifact)
        audit, _ = load_linked_article_audit(artifact, path)
        verdict = audit.get("payload", {}).get("summary", {}).get("verdict")
        if verdict == "audit_failed":
            raise WorkflowError("独立文章审计未通过，不能批准 G3")
        if verdict == "human_decision_required" and not str(args.notes or "").strip():
            raise WorkflowError("独立审计存在待人工决定事项，G3 必须用 --notes 记录决定理由")
        if verdict not in {"passed", "human_decision_required"}:
            raise WorkflowError("独立文章审计结论无效，不能批准 G3")
    if args.decision == "approved" and args.gate == "G4":
        publication_payload = artifact.get("payload", {})
        policy_check = publication_payload.get("policy_check")
        if not isinstance(policy_check, dict):
            raise WorkflowError("G4 批准前必须完成发布 policy_check")
        if policy_check.get("action") != "publish":
            raise WorkflowError("G4 只能接受 action=publish 的 policy_check")
        if policy_check.get("strategy_artifact_id") != publication_payload.get("strategy_artifact_id"):
            raise WorkflowError("policy_check.strategy_artifact_id 与 publication 不一致")
        if policy_check.get("decision") == "blocked":
            raise WorkflowError("发布策略检查结果为 blocked，不能批准 G4")
        if policy_check.get("decision") not in {"allowed", "needs_human"}:
            raise WorkflowError("G4 批准前 policy_check.decision 必须是 allowed 或 needs_human")
        if policy_check.get("decision") == "needs_human" and not args.notes:
            raise WorkflowError("policy_check=needs_human 时，G4 必须用 --notes 记录人工例外理由")
        root = find_workspace(path)
        inventory_id = publication_payload.get("inventory_item_artifact_id")
        inventory_path = root / "artifacts" / artifact["account_id"] / "inventory_item" / f"{inventory_id}.json"
        inventory = load_json(inventory_path)
        inventory_errors = validate_artifact(inventory)
        if inventory_errors:
            raise WorkflowError("G4 关联的 inventory_item 未通过校验：" + "; ".join(inventory_errors))
        if inventory.get("status") not in {"ready", "scheduled"}:
            raise WorkflowError("G4 关联的 inventory_item 必须是 ready 或 scheduled")
        inventory_payload = inventory.get("payload", {})
        if inventory_payload.get("strategy_artifact_id") != publication_payload.get("strategy_artifact_id"):
            raise WorkflowError("publication 与 inventory_item 的战略引用不一致")
        if inventory_payload.get("content_artifact_id") != publication_payload.get("content_artifact_id"):
            raise WorkflowError("publication 与 inventory_item 的内容引用不一致")
        content_relative = inventory_payload.get("content_artifact_path")
        if not content_relative:
            raise WorkflowError("G4 关联的 inventory_item 缺少 content_artifact_path")
        content_path = (root / content_relative).resolve()
        try:
            content_path.relative_to(root)
        except ValueError as exc:
            raise WorkflowError("inventory_item 的 content_artifact_path 越出工作区") from exc
        content = load_json(content_path)
        content_errors = validate_artifact(content)
        if content_errors:
            raise WorkflowError("G4 关联的 content 未通过校验：" + "; ".join(content_errors))
        if content.get("artifact_id") != publication_payload.get("content_artifact_id"):
            raise WorkflowError("publication.content_artifact_id 与本地 content 不一致")
        if not effective_content_approval(content, content_path):
            raise WorkflowError("G4 前需要关联 content 的当前有效 G3 和匹配的独立文章审计")
        if publication_payload.get("scheduled_at"):
            if inventory.get("status") != "scheduled":
                raise WorkflowError("定时发布必须关联已排期的内容库存项")
            scheduled_at = datetime_value(publication_payload.get("scheduled_at"), "定时发布时间")
            inventory_planned_at = datetime_value(inventory_payload.get("planned_publish_at"), "内容库存计划发布时间")
            if inventory_planned_at != scheduled_at:
                raise WorkflowError("内容库存的计划发布时间必须与发布记录的定时时间一致")
            expires_at = datetime_value(publication_payload.get("schedule_expires_at"), "最晚允许执行时间")
            if scheduled_at <= datetime_value(now_iso(), "当前时间"):
                raise WorkflowError("发布前确认时，定时发布时间必须仍在未来")
            if expires_at <= scheduled_at:
                raise WorkflowError("最晚允许执行时间必须晚于定时发布时间")
            run_path = root / "runs" / artifact.get("run_id", "") / "run.json"
            run = load_json(run_path)
            runtime_capabilities = run.get("payload", {}).get("runtime_capabilities", {}).get("capabilities", {})
            schedule_method = publication_payload.get("schedule_method")
            if schedule_method == "agent_wakeup" and runtime_capabilities.get("scheduled_execution", {}).get("status") != "available":
                raise WorkflowError("当前运行工具未确认具备按指定时间唤醒执行能力，不能选择由运行工具到点执行")
            if schedule_method == "platform_native" and runtime_capabilities.get("authenticated_platform_control", {}).get("status") != "available":
                raise WorkflowError("当前未确认可操作已登录的平台页面，不能选择平台原生定时发布")
        elif inventory.get("status") == "scheduled":
            raise WorkflowError("已排期的内容库存项必须在发布记录中保留对应的定时时间")
    if args.decision == "approved" and args.gate == "G0":
        payload = artifact.get("payload", {})
        data_scope = payload.get("data_scope", {})
        if not data_scope.get("allowed_sources"):
            raise WorkflowError("G0 批准前必须明确至少一个 allowed_sources")
        runtime = payload.get("runtime_capabilities", {})
        if runtime.get("discovery_status") not in {"partial", "complete"}:
            raise WorkflowError("G0 批准前必须完成或部分完成运行时能力发现")
        if runtime.get("capability_source") == "unknown":
            raise WorkflowError("G0 批准前必须记录能力信息来源")
        mode = runtime.get("execution_mode")
        if mode not in {"full", "assisted", "document_only"}:
            raise WorkflowError("G0 批准前必须明确 execution_mode")
        capabilities = runtime.get("capabilities", {})
        if capabilities.get("human_approval", {}).get("status") != "available":
            raise WorkflowError("G0 不能在 human_approval 能力不可用时批准")
        if mode in {"full", "assisted"} and capabilities.get("local_json_storage", {}).get("status") != "available":
            raise WorkflowError(f"{mode} 模式需要可用的 local_json_storage")
        if mode == "full" and capabilities.get("append_audit_log", {}).get("status") != "available":
            raise WorkflowError("full 模式需要可用的 append_audit_log")
        if mode == "document_only" and not runtime.get("limitations"):
            raise WorkflowError("document_only 模式必须明确记录自动化限制")
        declared_ids = {
            entry.get("capability_id")
            for entry in capabilities.values()
            if isinstance(entry, dict) and entry.get("capability_id")
        }
        unknown_processing = [
            entry.get("capability_id")
            for entry in data_scope.get("external_processing", [])
            if isinstance(entry, dict) and entry.get("capability_id") not in declared_ids
        ]
        if unknown_processing:
            raise WorkflowError(
                "external_processing 引用了未在能力快照中声明的 capability_id："
                + ", ".join(str(item) for item in unknown_processing)
            )
    if args.decision == "approved" and args.gate == "G5":
        run_payload = artifact.get("payload", {})
        data_scope = run_payload.get("data_scope", {})
        if not data_scope.get("allowed_sources"):
            raise WorkflowError("G5 批准前必须明确至少一个 allowed_sources")
        measurement_plan = run_payload.get("measurement_plan", {})
        if not measurement_plan.get("snapshot_windows"):
            raise WorkflowError("G5 批准前必须明确至少一个 snapshot_window")
        for index, window in enumerate(measurement_plan.get("snapshot_windows", [])):
            parse_window_seconds(window, f"第 {index + 1} 个观察窗口")
        if not measurement_plan.get("trust_metrics"):
            raise WorkflowError("G5 批准前必须明确至少一个 trust_metric")
    if (
        args.decision == "approved"
        and args.gate == "G6"
        and artifact.get("schema_version") == SCHEMA_VERSION
    ):
        require_experiment_positioning_links(find_workspace(path), artifact)
    before = artifact.get("status")
    decision = {
        "gate": args.gate,
        "decision": args.decision,
        "actor_type": "human",
        "actor_id": args.actor,
        "at": now_iso(),
        "payload_sha256": payload_hash(artifact, args.gate),
        "notes": args.notes or "",
    }
    artifact.setdefault("approvals", []).append(decision)
    if artifact_type == "run_manifest":
        artifact["payload"]["gate_status"][args.gate] = args.decision
        if args.gate == "G0" and args.decision == "approved":
            run_type = artifact["payload"].get("run_type")
            artifact["payload"]["current_stage"] = {
                "full_cycle": "strategy",
                "strategy_review": "strategy",
                "trial_content": "topics",
                "content_production": "topics",
                "batch_creation": "topics",
                "publication": "publication",
                "measurement": "measurement",
                "long_tail_review": "measurement",
            }[run_type]
            artifact["status"] = "approved"
    elif artifact_type == "publication":
        if args.decision == "approved":
            if artifact["payload"].get("state") != "review_required":
                raise WorkflowError("只有 review_required 的 publication 可以批准 G4")
            artifact["payload"]["state"] = "approved"
            artifact["status"] = "approved"
        elif args.decision == "revoked":
            if artifact["payload"].get("state") != "approved":
                raise WorkflowError("只有尚未发布且已批准的 publication 可以撤销 G4")
            artifact["payload"]["state"] = "review_required"
            artifact["status"] = "review_required"
        else:
            if artifact["payload"].get("state") != "review_required":
                raise WorkflowError("只有 review_required 的 publication 可以拒绝 G4")
            artifact["status"] = "review_required"
    else:
        if args.decision == "approved":
            artifact["status"] = "approved"
            if artifact_type == "experiment":
                artifact["payload"]["state"] = "approved"
        elif args.decision == "rejected":
            artifact["status"] = "rejected"
        else:
            artifact["status"] = "review_required"
    artifact["updated_at"] = now_iso()
    errors = validate_artifact(artifact)
    if errors:
        raise WorkflowError("批准后 artifact 不合法：" + "; ".join(errors))
    atomic_write_json(path, artifact)
    root = find_workspace(path)
    audit_event(root, artifact, args.actor, "human", f"gate_{args.decision}", args.notes or args.gate, before, artifact["status"])
    print(f"{args.decision}: {args.gate} {path}")


def command_set_schedule(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    artifact = load_json(path)
    if artifact.get("artifact_type") != "publication":
        raise WorkflowError("只有发布记录可以设置定时发布")
    if artifact.get("status") not in {"draft", "review_required"}:
        raise WorkflowError("定时安排必须在发布前确认之前设置；已确认时请先撤销发布前确认")
    scheduled_at = datetime_value(args.scheduled_at, "定时发布时间")
    expires_at = datetime_value(args.expires_at, "最晚允许执行时间")
    recorded_at = datetime_value(args.at or now_iso(), "记录时间")
    if scheduled_at <= recorded_at:
        raise WorkflowError("定时发布时间必须晚于当前记录时间")
    if expires_at <= scheduled_at:
        raise WorkflowError("最晚允许执行时间必须晚于定时发布时间")
    payload = artifact["payload"]
    payload.update(
        {
            "scheduled_at": scheduled_at.isoformat(timespec="seconds"),
            "schedule_expires_at": expires_at.isoformat(timespec="seconds"),
            "schedule_method": args.method,
            "schedule_reference": None,
            "execution_checks": [],
        }
    )
    artifact["updated_at"] = recorded_at.isoformat(timespec="seconds")
    errors = validate_artifact(artifact)
    if errors:
        raise WorkflowError("设置定时发布后记录不合法：" + "; ".join(errors))
    atomic_write_json(path, artifact)
    root = find_workspace(path)
    audit_event(
        root,
        artifact,
        args.actor,
        args.actor_type,
        "publication_scheduled",
        f"{payload['scheduled_at']} 至 {payload['schedule_expires_at']}；{args.method}",
    )
    print(path)


def command_clear_schedule(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    artifact = load_json(path)
    if artifact.get("artifact_type") != "publication":
        raise WorkflowError("只有发布记录可以取消定时发布")
    if artifact.get("status") not in {"draft", "review_required"}:
        raise WorkflowError("取消定时安排前必须撤销尚未消费的发布前确认")
    payload = artifact["payload"]
    if payload.get("scheduled_at") is None:
        raise WorkflowError("当前发布记录没有定时安排")
    for field in ("scheduled_at", "schedule_expires_at", "schedule_method", "schedule_reference"):
        payload[field] = None
    payload["execution_checks"] = []
    artifact["updated_at"] = now_iso()
    errors = validate_artifact(artifact)
    if errors:
        raise WorkflowError("取消定时发布后记录不合法：" + "; ".join(errors))
    atomic_write_json(path, artifact)
    root = find_workspace(path)
    audit_event(root, artifact, args.actor, args.actor_type, "publication_schedule_cleared", args.reason)
    print(path)


def command_scheduled_due(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    load_json(root / "workspace.json")
    as_of = datetime_value(args.as_of or now_iso(), "查询时间")
    actionable: list[dict[str, Any]] = []
    for path in sorted((root / "artifacts").glob("*/publication/*.json")):
        artifact = load_json(path)
        errors = validate_artifact(artifact)
        if errors:
            continue
        payload = artifact.get("payload", {})
        if not payload.get("scheduled_at") or artifact.get("status") not in {"approved", "publishing"}:
            continue
        if not effective_approval(artifact, "G4"):
            continue
        scheduled_at = datetime_value(payload["scheduled_at"], "定时发布时间")
        expires_at = datetime_value(payload["schedule_expires_at"], "最晚允许执行时间")
        method = payload.get("schedule_method")
        action_status: str | None = None
        if artifact.get("status") == "approved" and method == "platform_native":
            action_status = "awaiting_submission" if as_of < expires_at else "missed"
        elif artifact.get("status") == "approved" and as_of >= scheduled_at:
            action_status = "due" if as_of <= expires_at else "missed"
        elif artifact.get("status") == "publishing" and method == "platform_native" and as_of >= scheduled_at:
            action_status = "awaiting_verification"
        if action_status:
            actionable.append(
                {
                    "account_id": artifact["account_id"],
                    "publication_artifact_id": artifact["artifact_id"],
                    "publication_path": str(path.relative_to(root)),
                    "scheduled_at": payload["scheduled_at"],
                    "schedule_expires_at": payload["schedule_expires_at"],
                    "schedule_method": method,
                    "action_status": action_status,
                }
            )
    actionable.sort(key=lambda item: (item["scheduled_at"], item["account_id"], item["publication_artifact_id"]))
    print(json.dumps(actionable, ensure_ascii=False, indent=2))


def command_transition(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    artifact = load_json(path)
    if artifact.get("artifact_type") != "publication":
        raise WorkflowError("transition 当前只用于 publication")
    payload = artifact["payload"]
    current = payload.get("state")
    target = args.to
    if target not in PUBLICATION_TRANSITIONS.get(current, set()):
        raise WorkflowError(f"不允许的发布状态变化：{current} -> {target}")
    transition_at = datetime_value(args.at or now_iso(), "状态更新时间")
    if current == "approved" and target == "publishing":
        if not effective_approval(artifact, "G4"):
            raise WorkflowError("进入 publishing 前需要当前 payload 对应的有效 G4 批准")
        scheduled_at_raw = payload.get("scheduled_at")
        if scheduled_at_raw:
            scheduled_at = datetime_value(scheduled_at_raw, "定时发布时间")
            expires_at = datetime_value(payload.get("schedule_expires_at"), "最晚允许执行时间")
            method = payload.get("schedule_method")
            if transition_at > expires_at:
                raise WorkflowError("已经错过允许执行时间；不得自动补发，请重新安排并确认")
            if method == "platform_native":
                if not args.schedule_reference:
                    raise WorkflowError("平台原生定时提交成功后必须记录平台排期凭据")
            else:
                if transition_at < scheduled_at:
                    raise WorkflowError("尚未到定时发布时间，不得提前执行")
                if method == "manual_handoff" and args.actor_type != "human":
                    raise WorkflowError("人工到点交接只能由账号负责人确认开始执行")
                checks = payload.get("execution_checks", [])
                latest = checks[-1] if checks else None
                if not isinstance(latest, dict) or latest.get("decision") != "allowed":
                    raise WorkflowError("到点执行前必须重新检查发布规则，且结果为符合当前规则")
                checked_at = datetime_value(latest.get("checked_at"), "到点执行前检查时间")
                if checked_at < scheduled_at or checked_at > transition_at:
                    raise WorkflowError("到点执行前检查必须在定时发布时间之后、实际执行之前完成")
    if current == "unknown" and args.actor_type != "human":
        raise WorkflowError("unknown 只能由人工核对远端状态后解决")
    if current == "failed" and args.actor_type != "human":
        raise WorkflowError("failed 只能由人工决定是否回到 review_required")
    if target == "published" and not (args.remote_id or args.remote_url or payload.get("remote_id") or payload.get("remote_url")):
        raise WorkflowError("published 状态必须提供 remote-id 或 remote-url")

    before = artifact["status"]
    timestamp = transition_at.isoformat(timespec="seconds")
    if target == "publishing":
        if args.schedule_reference:
            payload["schedule_reference"] = args.schedule_reference
        payload.setdefault("attempts", []).append(
            {
                "attempt_id": new_id("attempt"),
                "started_at": timestamp,
                "ended_at": None,
                "status": "scheduled" if payload.get("schedule_method") == "platform_native" else "publishing",
                "actor_id": args.actor,
                "error": None,
            }
        )
    elif current == "publishing" and payload.get("attempts"):
        payload["attempts"][-1].update({"ended_at": timestamp, "status": target, "error": args.error})
    if target == "published":
        if not args.published_at or not args.published_at_source:
            raise WorkflowError("确认已发布时必须同时提供实际上线时间及其核对依据")
        actual_published_at = datetime_value(args.published_at, "实际上线时间")
        if actual_published_at > transition_at:
            raise WorkflowError("实际上线时间不能晚于本次核对时间")
        payload["remote_id"] = args.remote_id or payload.get("remote_id")
        payload["remote_url"] = args.remote_url or payload.get("remote_url")
        payload["published_at"] = actual_published_at.isoformat(timespec="seconds")
        payload["published_at_source"] = args.published_at_source
        payload["last_error"] = None
    elif target in {"failed", "unknown"}:
        payload["last_error"] = args.error or "未提供错误详情"
    elif current == "failed" and target == "review_required":
        artifact.setdefault("approvals", []).append(
            {
                "gate": "G4",
                "decision": "revoked",
                "actor_type": "human",
                "actor_id": args.actor,
                "at": timestamp,
                "payload_sha256": payload_hash(artifact, "G4"),
                "notes": "失败后重新审阅，旧发布批准失效",
            }
        )
    payload["state"] = target
    artifact["status"] = target
    artifact["updated_at"] = timestamp
    errors = validate_artifact(artifact)
    if errors:
        raise WorkflowError("状态变化后 artifact 不合法：" + "; ".join(errors))
    atomic_write_json(path, artifact)
    root = find_workspace(path)
    audit_event(root, artifact, args.actor, args.actor_type, "publication_transition", args.reason, before, target)
    print(f"{current} -> {target}: {path}")


def command_register(args: argparse.Namespace) -> None:
    run_path = Path(args.run).resolve()
    artifact_path = Path(args.artifact).resolve()
    run = load_json(run_path)
    artifact = load_json(artifact_path)
    if run.get("artifact_type") != "run_manifest":
        raise WorkflowError("--run 必须指向 run_manifest")
    artifact_errors = validate_artifact(artifact)
    if artifact_errors:
        raise WorkflowError("待登记 artifact 未通过校验：" + "; ".join(artifact_errors))
    if run.get("account_id") != artifact.get("account_id") or run.get("run_id") != artifact.get("run_id"):
        raise WorkflowError("run 与 artifact 的 account_id/run_id 不一致")
    rule = REGISTER_RULES.get(args.role)
    if not rule:
        raise WorkflowError(f"不支持的登记角色：{args.role}")
    expected_type, required_gate, next_stage = rule
    if artifact.get("artifact_type") != expected_type:
        raise WorkflowError(f"角色 {args.role} 需要 {expected_type}，实际为 {artifact.get('artifact_type')}")
    if required_gate:
        if expected_type == "content":
            if not effective_content_approval(artifact, artifact_path):
                raise WorkflowError("登记 content 前需要当前有效 G3 和匹配的独立文章审计")
        elif not effective_approval(artifact, required_gate):
            raise WorkflowError(f"登记 {args.role} 前需要有效 {required_gate}")
    if expected_type == "publication" and artifact.get("status") != "published":
        raise WorkflowError("publication 只有 published 后才能登记为完成")
    if expected_type == "inventory_item" and artifact.get("status") not in {"ready", "scheduled"}:
        raise WorkflowError("inventory_item 必须达到 ready 或 scheduled 才能登记并进入发布阶段")
    if expected_type in {"metrics_snapshot", "review"} and artifact.get("status") != "ready":
        raise WorkflowError(f"{expected_type} 必须是 ready 状态")
    if expected_type in {"metrics_snapshot", "review"} and not effective_approval(run, "G5"):
        raise WorkflowError(f"登记 {expected_type} 前 run manifest 需要有效 G5")
    root = find_workspace(run_path)
    if expected_type == "review" and artifact.get("schema_version") == SCHEMA_VERSION:
        require_review_positioning_links(root, artifact)
    try:
        relative = artifact_path.relative_to(root)
    except ValueError as exc:
        raise WorkflowError("artifact 必须位于同一工作区") from exc
    run["payload"]["artifact_paths"][args.role] = str(relative)
    if expected_type == "account_strategy":
        run["payload"]["strategy_artifact_id"] = artifact.get("artifact_id")
    if expected_type == "persona":
        strategy_id = run["payload"].get("strategy_artifact_id")
        if not strategy_id:
            raise WorkflowError("登记 persona 前必须先登记或引用 account_strategy")
        if artifact.get("payload", {}).get("strategy_artifact_id") != strategy_id:
            raise WorkflowError("persona.strategy_artifact_id 与 run 的账号战略不一致")
        run["payload"]["persona_artifact_id"] = artifact.get("artifact_id")
    if required_gate:
        run["payload"]["gate_status"][required_gate] = "approved"
    run["payload"]["current_stage"] = next_stage
    run["updated_at"] = now_iso()
    run_errors = validate_artifact(run)
    if run_errors:
        raise WorkflowError("登记后 run manifest 不合法：" + "; ".join(run_errors))
    superseded: dict[str, Any] | None = None
    superseded_path: Path | None = None
    supersedes_id = artifact.get("payload", {}).get("supersedes_artifact_id")
    if expected_type in {"account_strategy", "persona"} and supersedes_id:
        superseded_path = root / "artifacts" / artifact["account_id"] / expected_type / f"{supersedes_id}.json"
        superseded = load_json(superseded_path)
        if superseded.get("artifact_type") != expected_type or superseded.get("artifact_id") != supersedes_id:
            raise WorkflowError("supersedes_artifact_id 未解析到正确的旧 artifact")
        if superseded.get("account_id") != artifact.get("account_id"):
            raise WorkflowError("新旧 revision 的 account_id 不一致")
        old_status = superseded.get("status")
        superseded["status"] = "superseded"
        superseded["updated_at"] = now_iso()
        superseded_errors = validate_artifact(superseded)
        if superseded_errors:
            raise WorkflowError("旧 revision 无法标记 superseded：" + "; ".join(superseded_errors))
    atomic_write_json(run_path, run)
    if superseded is not None and superseded_path is not None:
        atomic_write_json(superseded_path, superseded)
        audit_event(root, superseded, args.actor, args.actor_type, "artifact_superseded", artifact["artifact_id"], old_status, "superseded")
    audit_event(root, artifact, args.actor, args.actor_type, "artifact_registered", args.role)
    print(relative)


def human_gate_label(gate: str | None, artifact_type: str | None = None) -> str:
    if not gate:
        return "无需单独确认"
    return CONTEXTUAL_GATE_LABELS.get((artifact_type or "", gate), GATE_LABELS.get(gate, "人工确认"))


def human_field_label(field: str, parent_field: str | None = None) -> str:
    if field in CAPABILITY_LABELS:
        return CAPABILITY_LABELS[field]
    if field in FIELD_LABELS:
        return FIELD_LABELS[field]
    if field in METRIC_LABELS:
        return METRIC_LABELS[field]
    if re.search(r"[\u3400-\u9fff]", field):
        return field
    if parent_field in {"scores", "stock_metrics", "flow_metrics", "derived_metrics", "trust_metrics", "metrics"}:
        return "自定义指标"
    return "补充信息"


def human_value(value: Any) -> str:
    if value is None:
        return "未填写"
    if value is True:
        return "是"
    if value is False:
        return "否"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text in CAPABILITY_LABELS:
        return CAPABILITY_LABELS[text]
    if text in METRIC_LABELS:
        return METRIC_LABELS[text]
    if text in EVENT_LABELS:
        return EVENT_LABELS[text]
    if text in GATE_LABELS:
        return GATE_LABELS[text]
    if text in VALUE_LABELS:
        return VALUE_LABELS[text]
    extra_values = {
        "xiaohongshu": "小红书",
        "user_input": "内容负责人提供",
        "web_source": "公开网页资料",
        "platform_data": "平台数据",
        "derived": "根据已有资料计算",
        "generated": "由运行助手生成",
        "verified": "已核对",
        "unverified": "尚未核对",
        "not_applicable": "无需核对",
        "supported": "已有证据支持",
        "refuted": "已有证据反驳",
        "inconclusive": "证据不足，暂不能判断",
        "proposed": "待确认",
        "running": "进行中",
        "stopped": "已停止",
        "publish": "发布",
        "modify": "修改已发布内容",
        "delete": "删除已发布内容",
    }
    if text in extra_values:
        return extra_values[text]
    duration = re.fullmatch(r"(\d+(?:\.\d+)?)([hd])", text)
    if duration:
        unit = "小时" if duration.group(2) == "h" else "天"
        return f"{duration.group(1)} {unit}"
    id_labels = {
        "account_strategy_": "账号策略记录",
        "run_manifest_": "任务记录",
        "persona_": "账号定位记录",
        "topic_report_": "选题报告记录",
        "topic_": "选题记录",
        "content_": "内容记录",
        "article_audit_": "独立审计记录",
        "inventory_": "库存记录",
        "publication_": "发布记录",
        "metrics_": "数据快照记录",
        "review_": "复盘记录",
        "experiment_": "实验记录",
        "evidence_": "证据记录",
        "source_": "来源记录",
        "claim_": "核对项",
        "asset_": "素材记录",
    }
    for prefix, label in id_labels.items():
        if text.startswith(prefix):
            suffix = text[-6:] if len(text) > 6 else text
            return f"{label}（…{suffix}）"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", text):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%Y年%m月%d日 %H:%M")
        except ValueError:
            pass
    return text


def render_scalar(value: Any) -> str:
    rendered = human_value(value)
    escaped = html.escape(rendered)
    if isinstance(value, str) and re.fullmatch(r"https?://[^\s]+", value):
        return f'<a href="{html.escape(value, quote=True)}" rel="noopener noreferrer">{escaped}</a>'
    if value is None:
        return f'<span class="muted">{escaped}</span>'
    return escaped


def render_human_value(value: Any, field: str | None = None, depth: int = 0) -> str:
    if depth > 7:
        return '<span class="muted">内容层级较深，请查看关联的专项审阅页。</span>'
    if isinstance(value, dict):
        if not value:
            return '<span class="muted">暂无记录</span>'
        if field == "capabilities":
            items = []
            for capability_name, detail in value.items():
                detail = detail if isinstance(detail, dict) else {"status": detail}
                status = detail.get("status")
                status_label = "尚未确认" if status == "unknown" else human_value(status)
                notes = detail.get("notes") or []
                note_html = render_human_value(notes, "notes", depth + 1) if notes else '<span class="muted">无补充说明</span>'
                items.append(
                    '<article class="mini-card">'
                    f'<div class="mini-title">{html.escape(human_field_label(capability_name))}</div>'
                    f'<div class="pill {status_tone(status)}">{html.escape(status_label)}</div>'
                    f'<div class="mini-body">{note_html}</div>'
                    '</article>'
                )
            return '<div class="mini-grid">' + "".join(items) + "</div>"
        rows = []
        for child_field, child_value in value.items():
            label = human_field_label(str(child_field), field)
            rows.append(
                '<div class="detail-row">'
                f'<div class="detail-label">{html.escape(label)}</div>'
                f'<div class="detail-value">{render_human_value(child_value, str(child_field), depth + 1)}</div>'
                '</div>'
            )
        return '<div class="detail-list">' + "".join(rows) + "</div>"
    if isinstance(value, list):
        if not value:
            return '<span class="muted">暂无记录</span>'
        if all(not isinstance(item, (dict, list)) for item in value):
            return '<div class="tag-list">' + "".join(
                f'<span class="tag">{render_scalar(item)}</span>' for item in value
            ) + "</div>"
        return '<div class="item-list">' + "".join(
            '<article class="list-card">'
            f'<div class="item-number">{index}</div>'
            f'<div class="item-content">{render_human_value(item, field, depth + 1)}</div>'
            '</article>'
            for index, item in enumerate(value, 1)
        ) + "</div>"
    return render_scalar(value)


def status_tone(value: Any) -> str:
    if value in {"approved", "ready", "published", "completed", "allowed", "available", "validated", "supported", "provisionally_established", "supportive", "passed", "resolved"}:
        return "positive"
    if value in {"rejected", "failed", "blocked", "prohibited", "refuted", "audit_failed", "P0"}:
        return "negative"
    if value in {"review_required", "unknown", "held", "needs_human", "pending", "testing", "emerging", "under_review", "inconclusive", "not_tested", "insufficient", "concerning", "human_decision_required", "P1"}:
        return "warning"
    return "neutral"


def review_gate(artifact: dict[str, Any]) -> str | None:
    artifact_type = artifact.get("artifact_type")
    if artifact_type == "run_manifest":
        if not effective_approval(artifact, "G0"):
            return "G0"
        if artifact.get("payload", {}).get("current_stage") == "measurement" and not effective_approval(artifact, "G5"):
            return "G5"
        return None
    gates = sorted(GATE_BY_TYPE.get(artifact_type, set()))
    return gates[0] if gates else None


def decision_guidance(artifact_type: str) -> str:
    return {
        "run_manifest": "请确认目标账号、可使用的数据来源、登录状态和外部处理范围是否符合预期。",
        "account_strategy": "请确认创作者的 90 天主要结果、长期业务去向、价值、关系姿态、信任与记忆资产，以及账号阶段、内容目标和运营规则是否符合实际。",
        "persona": "请确认定位问题判断、稳定边界、开放问题、逐项假设和验证计划是否可以执行；这里批准的是当前搜索空间，不代表永久正确。",
        "topic_report": "请从候选中明确选择要进入创作的选题，并确认它服务的受众任务、定位假设、证据职责和当前局限。",
        "content": "请先查看独立文章审计的结论与未解决问题，再确认标题、正文、图片或视频、事实表述、个人经历和素材权利。任何内容修改都会使旧审计与定稿确认失效。",
        "article_audit": "本页是独立审计结果，不代替内容负责人的定稿决定。请根据问题等级修订稿件或记录人工取舍。",
        "publication": "请核对目标账号、最终内容、素材顺序、可见范围，以及立即或定时发布安排。定时发布还需确认时区、最晚允许执行时间和执行方式；本次确认只授权一次发布或排期尝试。",
        "metrics_snapshot": "请核对实际上线时间、观察周期、应采集时间与实际采集时间是否一致，再判断本次数据是否可以进入复盘。",
        "experiment": "请先确认本轮属于探索未知还是受控优化，再核对定位假设、证据维度、有效曝光、内容兑现、观察时间和停止条件。",
    }.get(artifact_type, "请审阅本页信息，并明确选择确认通过、退回修改或暂停处理。")


def decision_panel(
    artifact: dict[str, Any],
    *,
    content_approval_effective: bool | None = None,
    article_audit_error: str | None = None,
) -> str:
    artifact_type = artifact.get("artifact_type", "")
    gate = review_gate(artifact)
    gate_is_effective = effective_approval(artifact, gate) if gate else False
    if artifact_type == "content" and content_approval_effective is not None:
        gate_is_effective = content_approval_effective
    if gate and gate_is_effective:
        state = "当前版本已由内容负责人确认"
        detail = "如内容发生修改，原确认会自动失效，需要重新审阅。"
        tone = "positive"
    elif gate:
        approvals = [item for item in artifact.get("approvals", []) if item.get("gate") == gate]
        last = approvals[-1].get("decision") if approvals else None
        if artifact_type == "content" and last == "approved" and content_approval_effective is False:
            state = "旧的定稿确认已失效"
            detail = article_audit_error or "稿件或独立审计已发生变化，需要重新审计并确认。"
            tone = "warning"
        else:
            state = human_value(last) if last else "等待内容负责人决定"
            detail = decision_guidance(artifact_type)
            tone = status_tone(last or "review_required")
    else:
        state = "本页用于查看进度与证据"
        detail = "如需推进高影响操作，系统会在对应步骤单独请求人工确认。"
        tone = "neutral"
    return (
        f'<section class="decision-panel {tone}">'
        '<div><div class="eyebrow">当前需要关注</div>'
        f'<h2>{html.escape(state)}</h2><p>{html.escape(detail)}</p></div>'
        f'<div class="decision-name">{html.escape(human_gate_label(gate, artifact_type))}</div>'
        '</section>'
    )


def payload_sections_html(artifact: dict[str, Any]) -> str:
    artifact_type = artifact.get("artifact_type", "")
    payload = artifact.get("payload", {})
    sections = []
    for title, fields in REPORT_SECTIONS.get(artifact_type, [("主要信息", tuple(payload.keys()))]):
        rows = []
        for field in fields:
            if field not in payload:
                continue
            rows.append(
                '<div class="report-field">'
                f'<h3>{html.escape(human_field_label(field))}</h3>'
                f'<div>{render_human_value(payload.get(field), field)}</div>'
                '</div>'
            )
        if rows:
            sections.append(f'<section class="report-section"><h2>{html.escape(title)}</h2>{"".join(rows)}</section>')
    return "".join(sections) or '<section class="report-section"><h2>主要信息</h2><p class="muted">暂无可展示内容。</p></section>'


def provenance_html(artifact: dict[str, Any]) -> str:
    sources = artifact.get("provenance", [])
    if not sources:
        return '<section class="report-section"><h2>信息来源</h2><p class="muted">尚未登记信息来源。</p></section>'
    cards = []
    for source in sources:
        url = source.get("url")
        link = render_scalar(url) if url else '<span class="muted">无外部链接</span>'
        cards.append(
            '<article class="source-card">'
            f'<div class="pill neutral">{html.escape(human_value(source.get("kind")))}</div>'
            f'<h3>{html.escape(str(source.get("summary") or "未填写来源说明"))}</h3>'
            f'<p>{html.escape(human_value(source.get("captured_at")))}</p>'
            f'<div>{link}</div>'
            '</article>'
        )
    return '<section class="report-section"><h2>信息来源</h2><div class="source-grid">' + "".join(cards) + "</div></section>"


def approvals_html(artifact: dict[str, Any]) -> str:
    approvals = artifact.get("approvals", [])
    if not approvals:
        return '<section class="report-section"><h2>人工决定记录</h2><p class="muted">尚无人工决定。</p></section>'
    items = []
    for approval in reversed(approvals):
        gate_label = human_gate_label(approval.get("gate"), artifact.get("artifact_type"))
        decision = human_value(approval.get("decision"))
        notes = approval.get("notes") or "无补充说明"
        items.append(
            '<article class="timeline-item">'
            f'<div class="timeline-dot {status_tone(approval.get("decision"))}"></div>'
            '<div class="timeline-body">'
            f'<div class="timeline-title">{html.escape(gate_label)} · {html.escape(decision)}</div>'
            f'<div class="timeline-meta">{html.escape(str(approval.get("actor_id") or "未记录"))} · {html.escape(human_value(approval.get("at")))}</div>'
            f'<p>{html.escape(str(notes))}</p>'
            '</div></article>'
        )
    return '<section class="report-section"><h2>人工决定记录</h2><div class="timeline">' + "".join(items) + "</div></section>"


def linked_article_audit_html(
    audit: dict[str, Any] | None,
    error: str | None,
) -> str:
    if audit is None:
        message = error or "尚未完成独立文章审计，不能进入内容定稿。"
        return (
            '<section class="report-section audit-callout warning">'
            '<h2>独立文章审计</h2>'
            f'<div class="pill warning">需要处理</div><p>{html.escape(message)}</p>'
            '</section>'
        )

    payload = audit.get("payload", {})
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    verdict = summary.get("verdict")
    findings = payload.get("findings", []) if isinstance(payload.get("findings"), list) else []
    open_findings = [
        item for item in findings
        if isinstance(item, dict) and item.get("status") == "open"
    ]
    finding_cards = []
    for finding in open_findings:
        severity = finding.get("severity")
        finding_cards.append(
            '<article class="audit-finding">'
            f'<div class="pill {status_tone(severity)}">{html.escape(human_value(severity))}</div>'
            f'<h3>{html.escape(str(finding.get("issue") or "未填写问题说明"))}</h3>'
            f'<p><strong>位置：</strong>{html.escape(str(finding.get("locator") or human_value(finding.get("surface_path"))))}</p>'
            f'<p><strong>修订方向：</strong>{html.escape(str(finding.get("recommendation") or "未填写"))}</p>'
            '</article>'
        )
    findings_html = (
        '<div class="audit-findings">' + "".join(finding_cards) + '</div>'
        if finding_cards
        else '<p class="muted">没有尚未解决的审计问题。</p>'
    )
    risk = payload.get("risk", {}) if isinstance(payload.get("risk"), dict) else {}
    counts = summary.get("counts", {}) if isinstance(summary.get("counts"), dict) else {}
    count_text = "、".join(
        f'{human_value(level)} {counts.get(level, 0)} 项' for level in ("P0", "P1", "P2")
    )
    return (
        '<section class="report-section audit-callout">'
        '<h2>独立文章审计</h2>'
        f'<div class="audit-summary"><div class="pill {status_tone(verdict)}">{html.escape(human_value(verdict))}</div>'
        f'<span>内容风险：{html.escape(human_value(risk.get("level")))}</span>'
        f'<span>{html.escape(count_text)}</span></div>'
        f'{findings_html}'
        '<p class="muted">审计由与写作者不同的 Agent 在全新、只读上下文中完成；结论不代替内容负责人的定稿决定。</p>'
        '</section>'
    )


def page_style() -> str:
    return """
:root{color-scheme:light;--ink:#172033;--muted:#6b7280;--line:#e6e8ee;--paper:#fff;--bg:#f3f5f9;--brand:#bf3a55;--brand-soft:#fff0f3;--positive:#17795c;--positive-soft:#eaf8f2;--warning:#9a5b00;--warning-soft:#fff7df;--negative:#b4233d;--negative-soft:#fff0f2}
*{box-sizing:border-box}body{margin:0;overflow-x:hidden;background:linear-gradient(145deg,#f9fafc 0%,#f2f4f8 55%,#f8eef1 100%);color:var(--ink);font-family:"PingFang SC","Microsoft YaHei",system-ui,-apple-system,sans-serif;line-height:1.65}
.shell{width:min(1120px,calc(100% - 32px));margin:32px auto 64px}.hero{padding:34px;border:1px solid rgba(255,255,255,.9);border-radius:28px;background:rgba(255,255,255,.9);box-shadow:0 24px 70px rgba(34,42,64,.09)}
.eyebrow{font-size:13px;font-weight:700;letter-spacing:.08em;color:var(--brand);margin-bottom:6px}.hero h1{font-size:clamp(28px,4vw,44px);line-height:1.15;margin:0 0 10px}.hero p{margin:0;color:var(--muted)}
.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:26px}.summary-card{min-width:0;padding:16px;border:1px solid var(--line);border-radius:18px;background:#fff}.summary-label{font-size:13px;color:var(--muted)}.summary-value{min-width:0;font-size:17px;font-weight:700;line-height:1.35;margin-top:5px;overflow-wrap:anywhere;word-break:break-word}
.decision-panel{display:flex;justify-content:space-between;gap:24px;align-items:center;margin:20px 0;padding:24px 28px;border-radius:22px;border:1px solid var(--line);background:#fff}.decision-panel h2{margin:2px 0 5px;font-size:23px}.decision-panel p{margin:0;color:var(--muted)}.decision-panel.positive{background:var(--positive-soft);border-color:#bfe9da}.decision-panel.warning{background:var(--warning-soft);border-color:#f1d795}.decision-name{min-width:190px;text-align:center;padding:11px 16px;border-radius:999px;background:rgba(255,255,255,.82);font-weight:700}
.report-section{margin-top:18px;padding:26px 28px;border-radius:22px;border:1px solid var(--line);background:var(--paper);box-shadow:0 10px 30px rgba(34,42,64,.045)}.report-section>h2{font-size:21px;margin:0 0 18px}.report-field{padding:18px 0;border-top:1px solid var(--line)}.report-field:first-of-type{padding-top:0;border-top:0}.report-field>h3{font-size:14px;color:var(--muted);margin:0 0 9px}
.detail-list{display:grid;gap:9px;min-width:0}.detail-row{display:grid;grid-template-columns:minmax(140px,220px) minmax(0,1fr);gap:16px;min-width:0;padding:10px 12px;border-radius:12px;background:#f8f9fb}.detail-label{color:var(--muted);font-size:14px}.detail-value{min-width:0;overflow-wrap:anywhere;word-break:break-word;white-space:pre-wrap}.muted{color:var(--muted)}
.tag-list{display:flex;flex-wrap:wrap;gap:8px}.tag,.pill{display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:#f1f3f6;font-size:13px}.pill{font-weight:700}.pill.positive{color:var(--positive);background:var(--positive-soft)}.pill.warning{color:var(--warning);background:var(--warning-soft)}.pill.negative{color:var(--negative);background:var(--negative-soft)}.pill.neutral{color:#526077;background:#edf1f7}
.mini-grid,.source-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;min-width:0}.mini-card,.source-card,.list-card{min-width:0;border:1px solid var(--line);border-radius:16px;background:#fff;padding:15px}.mini-title{font-weight:700;margin-bottom:8px}.mini-body{min-width:0;margin-top:10px;font-size:14px}.item-list{display:grid;gap:12px;min-width:0}.list-card{display:grid;grid-template-columns:30px minmax(0,1fr);gap:10px}.item-number{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:var(--brand-soft);color:var(--brand);font-weight:700;font-size:13px}.item-content{min-width:0}.source-card h3{font-size:16px;margin:10px 0 5px}.source-card p{color:var(--muted);font-size:13px;margin:0 0 8px}a{color:#a52643;text-underline-offset:3px}
.timeline{position:relative}.timeline-item{display:grid;grid-template-columns:20px 1fr;gap:12px;padding-bottom:20px}.timeline-item:last-child{padding-bottom:0}.timeline-dot{width:12px;height:12px;margin-top:7px;border-radius:50%;background:#8290a8;box-shadow:0 0 0 5px #edf1f7}.timeline-dot.positive{background:var(--positive);box-shadow:0 0 0 5px var(--positive-soft)}.timeline-dot.warning{background:#d78a13;box-shadow:0 0 0 5px var(--warning-soft)}.timeline-dot.negative{background:var(--negative);box-shadow:0 0 0 5px var(--negative-soft)}.timeline-title{font-weight:700}.timeline-meta{color:var(--muted);font-size:13px}.timeline-body p{margin:5px 0 0}
.audit-callout.warning{background:var(--warning-soft);border-color:#f1d795}.audit-summary{display:flex;align-items:center;flex-wrap:wrap;gap:10px 18px;margin-bottom:16px}.audit-findings{display:grid;gap:12px}.audit-finding{padding:16px;border:1px solid var(--line);border-radius:16px;background:#fff}.audit-finding h3{margin:9px 0 5px;font-size:17px}.audit-finding p{margin:4px 0;color:#4b5563}
details.trace{margin-top:18px;padding:16px 20px;border:1px dashed #cfd5df;border-radius:16px;color:var(--muted);background:rgba(255,255,255,.64)}details.trace summary{cursor:pointer;font-weight:700;color:#526077}.trace-grid{display:grid;grid-template-columns:180px 1fr;gap:7px 14px;margin-top:14px;font-size:13px;overflow-wrap:anywhere}.footer{margin-top:20px;text-align:center;color:var(--muted);font-size:13px}
@media(max-width:760px){.shell{width:min(100% - 20px,1120px);margin-top:10px}.hero,.report-section{padding:21px}.summary-grid{grid-template-columns:repeat(2,1fr)}.decision-panel{align-items:flex-start;flex-direction:column}.decision-name{min-width:0}.detail-row{grid-template-columns:1fr;gap:4px}.mini-grid,.source-grid{grid-template-columns:1fr}.trace-grid{grid-template-columns:1fr}}
"""


def trace_details(artifact: dict[str, Any]) -> str:
    fingerprint = payload_hash(artifact)[:16] + "…"
    values = [
        ("账号内部标识", artifact.get("account_id")),
        ("记录编号", artifact.get("artifact_id")),
        ("本轮任务编号", artifact.get("run_id")),
        ("数据结构版本", artifact.get("schema_version")),
        ("内容校验指纹", fingerprint),
    ]
    payload = artifact.get("payload", {})
    if artifact.get("artifact_type") == "content" and isinstance(payload.get("article_audit_ref"), dict):
        audit_ref = payload["article_audit_ref"]
        values.extend([
            ("独立审计记录", audit_ref.get("artifact_id")),
            ("独立审计位置", audit_ref.get("artifact_path")),
            ("独立审计指纹", audit_ref.get("payload_sha256")),
            ("被审稿件指纹", audit_ref.get("content_sha256")),
        ])
    if artifact.get("artifact_type") == "article_audit":
        author = payload.get("author", {}) if isinstance(payload.get("author"), dict) else {}
        reviewer = payload.get("reviewer", {}) if isinstance(payload.get("reviewer"), dict) else {}
        values.extend([
            ("被审稿件", payload.get("content_artifact_id")),
            ("被审稿件版本", payload.get("content_revision")),
            ("被审稿件位置", payload.get("target_uri")),
            ("被审稿件指纹", payload.get("content_sha256")),
            ("写作者记录", author.get("actor_id")),
            ("写作上下文", author.get("context_id")),
            ("独立审计者记录", reviewer.get("actor_id")),
            ("审计上下文", reviewer.get("context_id")),
            ("审计模型记录", reviewer.get("model_id")),
        ])
    rows = "".join(
        f'<div>{html.escape(label)}</div><div>{html.escape(str(value) if value is not None else "未填写")}</div>'
        for label, value in values
    )
    return f'<details class="trace"><summary>查看追溯信息</summary><div class="trace-grid">{rows}</div></details>'


def html_render(
    artifact: dict[str, Any],
    account_display_name: str | None = None,
    *,
    linked_article_audit: dict[str, Any] | None = None,
    article_audit_error: str | None = None,
    content_approval_effective: bool | None = None,
) -> str:
    artifact_type = artifact.get("artifact_type", "")
    title = ARTIFACT_LABELS.get(artifact_type, "运营审阅页")
    status = artifact.get("status")
    summary = (
        ("当前状态", human_value(status)),
        ("账号", account_display_name or artifact.get("account_id") or "未填写"),
        ("创建时间", human_value(artifact.get("created_at"))),
        ("最后更新", human_value(artifact.get("updated_at"))),
    )
    summary_html = "".join(
        '<div class="summary-card">'
        f'<div class="summary-label">{html.escape(label)}</div>'
        f'<div class="summary-value">{html.escape(str(value))}</div>'
        '</div>'
        for label, value in summary
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}｜人工审阅</title><style>{page_style()}</style></head>
<body><main class="shell"><header class="hero"><div class="eyebrow">小红书运营工作流 · 人工审阅</div>
<h1>{html.escape(title)}</h1><p>页面已把内部记录转换为业务语言，供内容负责人判断；页面不展示机器原始数据。</p>
<div class="summary-grid">{summary_html}</div></header>
{decision_panel(artifact, content_approval_effective=content_approval_effective, article_audit_error=article_audit_error)}
{linked_article_audit_html(linked_article_audit, article_audit_error) if artifact_type == "content" else ""}
{payload_sections_html(artifact)}
{provenance_html(artifact)}
{approvals_html(artifact)}
{trace_details(artifact)}
<div class="footer">本页由内部事实记录确定性生成。修改业务内容后，请重新生成审阅页。</div>
</main></body></html>"""


def load_audit_events(root: Path) -> list[dict[str, Any]]:
    path = root / "audit" / "events.ndjson"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"审计记录第 {line_number} 行无法读取：{exc.msg}") from exc
        if not isinstance(event, dict):
            raise WorkflowError(f"审计记录第 {line_number} 行不是有效事件")
        events.append(event)
    return events


def human_audit_reason(reason: Any) -> str:
    text = human_value(reason)
    if ":" in text:
        left, right = text.split(":", 1)
        left_translated = human_value(left.strip())
        right_translated = human_value(right.strip())
        return f"{left_translated}：{right_translated}"
    if text.startswith("day "):
        return "完成发布后第 " + text[4:] + " 天的复盘"
    return text


def audit_report_html(
    events: list[dict[str, Any]],
    title: str,
    account_id: str | None,
    run_id: str | None,
    account_display_name: str | None = None,
) -> str:
    human_decisions = sum(1 for event in events if str(event.get("event_type", "")).startswith("gate_"))
    attention = sum(1 for event in events if event.get("after_status") in {"failed", "unknown", "rejected", "held"})
    actors = len({event.get("actor_id") for event in events if event.get("actor_id")})
    scope_parts = []
    if account_id:
        scope_parts.append(f"账号 {account_display_name or account_id}")
    if run_id:
        scope_parts.append("指定的一轮运营任务")
    scope = "、".join(scope_parts) if scope_parts else "全部账号与任务"
    summary = (
        ("记录范围", scope),
        ("事件数量", str(len(events))),
        ("人工决定", str(human_decisions)),
        ("需要关注", str(attention)),
    )
    summary_html = "".join(
        '<div class="summary-card">'
        f'<div class="summary-label">{html.escape(label)}</div>'
        f'<div class="summary-value">{html.escape(value)}</div>'
        '</div>'
        for label, value in summary
    )
    timeline_items = []
    for event in reversed(events):
        event_type = event.get("event_type")
        before = event.get("before_status")
        after = event.get("after_status")
        transition = ""
        if before is not None or after is not None:
            transition = f'<div class="tag-list"><span class="tag">{html.escape(human_value(before))}</span><span class="muted">→</span><span class="tag">{html.escape(human_value(after))}</span></div>'
        actor_role = human_value(event.get("actor_type"))
        actor_name = event.get("actor_id") or "未记录"
        timeline_items.append(
            '<article class="timeline-item">'
            f'<div class="timeline-dot {status_tone(after)}"></div>'
            '<div class="timeline-body">'
            f'<div class="timeline-title">{html.escape(human_value(event_type))}</div>'
            f'<div class="timeline-meta">{html.escape(human_value(event.get("at")))} · {html.escape(actor_role)}：{html.escape(str(actor_name))}</div>'
            f'{transition}<p>{html.escape(human_audit_reason(event.get("reason")))}</p>'
            '</div></article>'
        )
    timeline = "".join(timeline_items) or '<p class="muted">当前范围内尚无审计记录。</p>'
    generated = datetime.now().astimezone().strftime("%Y年%m月%d日 %H:%M")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{page_style()}</style></head><body><main class="shell">
<header class="hero"><div class="eyebrow">小红书运营工作流 · 人工审计</div><h1>{html.escape(title)}</h1>
<p>报告按时间展示发生过的操作、人工决定与异常状态；报告不包含机器原始数据。</p><div class="summary-grid">{summary_html}</div></header>
<section class="report-section"><h2>操作与决定时间线</h2><div class="timeline">{timeline}</div></section>
<details class="trace"><summary>查看报告范围</summary><div class="trace-grid"><div>账号范围</div><div>{html.escape(account_id or "全部账号")}</div><div>任务范围</div><div>{html.escape("已指定" if run_id else "全部任务")}</div><div>涉及角色数量</div><div>{actors}</div><div>报告生成时间</div><div>{generated}</div></div></details>
<div class="footer">审计报告由追加式内部记录生成；如发现缺失或异常，请暂停高影响操作并核对来源。</div>
</main></body></html>"""


def command_render(args: argparse.Namespace) -> None:
    path = Path(args.path).resolve()
    artifact = load_json(path)
    account_display_name: str | None = None
    try:
        root = find_workspace(path)
        account = load_json(root / "accounts" / artifact.get("account_id", "") / "account.json")
        account_display_name = account.get("display_name")
    except WorkflowError:
        pass
    linked_audit: dict[str, Any] | None = None
    audit_error: str | None = None
    content_approval_effective: bool | None = None
    if artifact.get("artifact_type") == "content":
        try:
            linked_audit, _ = load_linked_article_audit(artifact, path)
        except WorkflowError as exc:
            audit_error = str(exc)
        content_approval_effective = effective_content_approval(artifact, path)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        html_render(
            artifact,
            account_display_name,
            linked_article_audit=linked_audit,
            article_audit_error=audit_error,
            content_approval_effective=content_approval_effective,
        ),
        encoding="utf-8",
    )
    print(output)


def command_audit_report(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    load_json(root / "workspace.json")
    events = load_audit_events(root)
    if args.account_id:
        events = [event for event in events if event.get("account_id") == args.account_id]
    if args.run_id:
        events = [event for event in events if event.get("run_id") == args.run_id]
    account_display_name: str | None = None
    if args.account_id:
        account_path = root / "accounts" / args.account_id / "account.json"
        if account_path.exists():
            account_display_name = load_json(account_path).get("display_name")
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    title = args.title or "小红书运营人工审计报告"
    output.write_text(
        audit_report_html(events, title, args.account_id, args.run_id, account_display_name),
        encoding="utf-8",
    )
    print(output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="小红书运营工作流数据与状态辅助器")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="初始化工作区或添加账号")
    init.add_argument("--root", required=True)
    init.add_argument("--account-id", required=True)
    init.add_argument("--display-name", required=True)
    init.add_argument("--actor", default="content-owner")
    init.set_defaults(func=command_init)

    new_run = sub.add_parser("new-run", help="创建本轮 manifest")
    new_run.add_argument("--root", required=True)
    new_run.add_argument("--account-id", required=True)
    new_run.add_argument("--objective", required=True)
    new_run.add_argument("--actor", required=True)
    new_run.add_argument("--run-type", choices=sorted(RUN_TYPES), default="full_cycle")
    new_run.add_argument("--strategy", help="工作区内已批准的 account_strategy JSON 绝对或相对路径")
    new_run.add_argument("--persona", help="工作区内已批准的 persona JSON 绝对或相对路径")
    new_run.add_argument("--content-sequence-no", type=int)
    new_run.add_argument("--runtime-name", help="可选的当前 Agent 运行时名称；不确定时留空")
    new_run.set_defaults(func=command_new_run)

    validate = sub.add_parser("validate", help="校验单个 artifact")
    validate.add_argument("path")
    validate.set_defaults(func=command_validate)

    validate_workspace = sub.add_parser("validate-workspace", help="校验整个工作区")
    validate_workspace.add_argument("--root", required=True)
    validate_workspace.set_defaults(func=command_validate_workspace)

    link_article_audit = sub.add_parser(
        "link-article-audit", help="把独立文章审计绑定到冻结 content"
    )
    link_article_audit.add_argument("--content", required=True)
    link_article_audit.add_argument("--audit", required=True)
    link_article_audit.add_argument("--actor", required=True)
    link_article_audit.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    link_article_audit.set_defaults(func=command_link_article_audit)

    approve = sub.add_parser("approve", help="记录人工门禁决定")
    approve.add_argument("path")
    approve.add_argument("--gate", required=True, choices=sorted(GATES))
    approve.add_argument("--actor", required=True)
    approve.add_argument("--decision", choices=["approved", "rejected", "revoked"], required=True)
    approve.add_argument("--notes")
    approve.set_defaults(func=command_approve)

    schedule = sub.add_parser("set-schedule", help="在发布前确认之前设置定时发布")
    schedule.add_argument("path")
    schedule.add_argument("--scheduled-at", required=True, help="带时区的定时发布时间")
    schedule.add_argument("--expires-at", required=True, help="超过该时间不得自动补发")
    schedule.add_argument("--method", required=True, choices=sorted(SCHEDULE_METHODS))
    schedule.add_argument("--actor", required=True)
    schedule.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    schedule.add_argument("--at", help="测试或回放用记录时间；默认当前时间")
    schedule.set_defaults(func=command_set_schedule)

    clear_schedule = sub.add_parser("clear-schedule", help="在重新确认前取消定时发布")
    clear_schedule.add_argument("path")
    clear_schedule.add_argument("--actor", required=True)
    clear_schedule.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    clear_schedule.add_argument("--reason", required=True)
    clear_schedule.set_defaults(func=command_clear_schedule)

    scheduled_due = sub.add_parser("scheduled-due", help="列出需要提交、到点执行、核对或重新安排的定时发布")
    scheduled_due.add_argument("--root", required=True)
    scheduled_due.add_argument("--as-of", help="测试或回放用查询时间；默认当前时间")
    scheduled_due.set_defaults(func=command_scheduled_due)

    transition = sub.add_parser("transition", help="改变 publication 状态")
    transition.add_argument("path")
    transition.add_argument("--to", required=True, choices=sorted(PUBLICATION_TRANSITIONS))
    transition.add_argument("--actor", required=True)
    transition.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    transition.add_argument("--reason", required=True)
    transition.add_argument("--remote-id")
    transition.add_argument("--remote-url")
    transition.add_argument("--published-at", help="平台确认的实际上线时间，必须包含时区")
    transition.add_argument("--published-at-source", choices=sorted(PUBLISHED_AT_SOURCES))
    transition.add_argument("--schedule-reference", help="平台原生定时任务或排期记录凭据")
    transition.add_argument("--at", help="测试或回放用状态更新时间；默认当前时间")
    transition.add_argument("--error")
    transition.set_defaults(func=command_transition)

    register = sub.add_parser("register", help="把 artifact 路径登记到 run manifest")
    register.add_argument("--run", required=True)
    register.add_argument("--artifact", required=True)
    register.add_argument("--role", required=True)
    register.add_argument("--actor", required=True)
    register.add_argument("--actor-type", choices=["human", "agent"], default="agent")
    register.set_defaults(func=command_register)

    render = sub.add_parser("render", help="生成中文 HTML 人工审阅页")
    render.add_argument("path")
    render.add_argument("--format", choices=["html"], default="html", help="人工审阅页固定为 HTML")
    render.add_argument("--output", required=True)
    render.set_defaults(func=command_render)

    audit_report = sub.add_parser("audit-report", help="生成中文 HTML 人工审计报告")
    audit_report.add_argument("--root", required=True)
    audit_report.add_argument("--output", required=True)
    audit_report.add_argument("--account-id")
    audit_report.add_argument("--run-id")
    audit_report.add_argument("--title")
    audit_report.set_defaults(func=command_audit_report)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except WorkflowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
