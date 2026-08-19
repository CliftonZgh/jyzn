#!/usr/bin/env python3
"""Validate one guide ledger and derive its patient-visible Markdown views."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


PACKAGE_FIELDS = {
    "name",
    "is_example",
    "campus_item_id",
    "scope_item_id",
    "safety_item_id",
    "fallback_item_id",
    "current_stage",
    "active_conditions",
}
ITEM_FIELDS = {
    "id",
    "name",
    "type",
    "conditions",
    "source",
    "evidence",
    "status",
    "verified_on",
    "expires_on",
    "maintainer",
    "reviewer",
    "dependencies",
}
STATUSES = {"pending", "partial", "verified", "expired", "disputed", "withdrawn"}
ARRIVAL_PLAN_FIELDS = {
    "audience",
    "before_departure",
    "arrival_anchor_id",
    "failure_trigger",
    "preferred_alternative",
    "final_fallback",
    "risk_rank",
}
ROUTE_SEGMENT_FIELDS = {
    "start_landmark",
    "action",
    "along_landmarks",
    "end_landmark",
    "route_mode",
}
JOURNEY_BRANCH_FIELDS = {"branch_key", "selection_basis", "differences"}
EXAMINATION_CARD_FIELDS = {
    "category",
    "official_exam_name",
    "hospital_arrangements",
    "general_safety",
    "unconfirmed",
}
EXAMINATION_STAGES = ("before_departure", "after_arrival", "after_completion")
ARRANGEMENT_EVIDENCE = {"current_hospital", "appointment_order"}
OPERATIONS_FIELDS = {
    "gaps",
    "evidence_rules",
    "collection_matrix",
    "route_evidence_packages",
    "promotion_gates",
    "review_cycles",
    "event_triggers",
    "conflict_policy",
    "feedback_policy",
    "audit_fields",
    "emergency_policy",
    "promotion_reviews",
    "events",
    "feedback_clues",
    "audit_records",
}
GAP_FIELDS = {"item_id", "owner", "required_evidence", "next_action", "excluded"}
ROUTE_EVIDENCE_FIELDS = {
    "route_item_id",
    "start_node",
    "end_node",
    "action_and_landmarks",
    "direction_and_floor_change",
    "conditions",
    "collected_at",
    "applicable_times",
    "photo_privacy_check",
}
REQUIRED_COLLECTION_TARGETS = {
    "公共交通出口",
    "下客点",
    "院内停车人行出口",
    "备用停车场",
    "门诊入口",
    "通用服务点",
    "独立无障碍路线",
}
REQUIRED_EVIDENCE_KINDS = {
    "官方资料",
    "电话或工作人员确认",
    "现场标识照片",
    "路线走测",
}
REQUIRED_PROMOTION_GATES = {
    "服务点",
    "连续路线",
    "无障碍路线",
    "入口开放",
    "停车收费",
    "医疗准备",
}
REQUIRED_AUDIT_FIELDS = {
    "变更前",
    "变更后",
    "操作者",
    "时间",
    "原因",
    "证据",
    "复核结果",
    "受影响内容",
}
EVENT_FIELDS = {"id", "type", "affected_item_ids", "owner", "occurred_at", "next_action"}
EVENT_STATUSES = {
    "announcement": "partial",
    "renovation": "partial",
    "source_conflict": "disputed",
    "correction": "partial",
    "expiry": "expired",
    "safety": "withdrawn",
}
FEEDBACK_FIELDS = {"id", "location", "observation", "observed_on", "status"}
FORBIDDEN_FEEDBACK_FIELDS = {
    "patient_name",
    "face",
    "medical_record",
    "appointment",
    "exam_result",
}
AUDIT_RECORD_FIELDS = {
    "before",
    "after",
    "operator",
    "occurred_at",
    "reason",
    "evidence",
    "review_result",
    "affected_routes",
    "affected_cards",
    "affected_outputs",
}
RELEASE_FIELDS = {
    "spec_delivery",
    "schematics",
    "qr_targets",
    "external_maps",
    "print",
    "accessibility_checks",
    "privacy_checks",
    "publication_checks",
    "representative_tests",
    "workflow",
    "pilot",
    "owners",
}
REQUIRED_ACCESSIBILITY_CHECKS = {
    "320px宽度",
    "字体放大",
    "键盘与清晰焦点",
    "触控",
    "屏幕阅读器基本阅读顺序",
    "非颜色唯一编码",
    "图片文字等价",
    "黑白打印",
}
REQUIRED_PRIVACY_CHECKS = {
    "患者页面",
    "链接参数",
    "二维码",
    "图片",
    "反馈入口",
    "汇总统计",
}
REQUIRED_TEST_TASKS = {
    "公共交通到院",
    "停车满位切换",
    "寻找服务点",
    "核对检查项目",
    "报告领取或离院",
}
REQUIRED_RELEASE_WORKFLOW = {
    "编辑草稿",
    "证据与风险复核",
    "内部预览",
    "小范围现场试运行",
    "严重问题修正",
    "正式公开",
}
PRIVATE_DATA_MARKERS = {
    "patient_name",
    "medical_record",
    "appointment",
    "exam_result",
    "姓名=",
    "病历=",
    "预约=",
    "检查结果=",
}


def patient_items(
    ledger: dict[str, Any], as_of: date
) -> list[dict[str, Any]]:
    items_by_id = {item["id"]: item for item in ledger["items"]}
    active_conditions = set(ledger["package"]["active_conditions"])
    visibility: dict[str, bool] = {}

    def is_visible(item_id: str, visiting: set[str]) -> bool:
        if item_id in visibility:
            return visibility[item_id]
        if item_id in visiting:
            raise ValueError(f"dependency cycle at {item_id}")
        item = items_by_id.get(item_id)
        if item is None:
            raise ValueError(f"unknown dependency: {item_id}")
        visiting.add(item_id)
        visible = (
            item["status"] in {"verified", "partial"}
            and date.fromisoformat(item["expires_on"]) >= as_of
            and set(item["conditions"]).issubset(active_conditions)
            and all(
                is_visible(dependency, visiting)
                for dependency in item["dependencies"]
            )
        )
        visiting.remove(item_id)
        visibility[item_id] = visible
        return visible

    return [item for item in ledger["items"] if is_visible(item["id"], set())]


def validate(ledger: dict[str, Any], as_of: date) -> None:
    package = ledger.get("package")
    items = ledger.get("items")
    if not isinstance(package, dict):
        raise ValueError("package must be an object")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty list")
    missing_package = sorted(
        field for field in PACKAGE_FIELDS if not package.get(field)
    )
    if missing_package:
        raise ValueError(f"missing package fields: {', '.join(missing_package)}")
    if package["is_example"] is not True:
        raise ValueError("is_example must be true for this demonstration package")
    if (
        not isinstance(package["active_conditions"], list)
        or not package["active_conditions"]
    ):
        raise ValueError("active_conditions must be a non-empty list")

    identifiers: set[str] = set()
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"item {position} must be an object")
        missing_item = sorted(
            field
            for field in ITEM_FIELDS
            if field not in item or item[field] in (None, "")
        )
        if missing_item:
            raise ValueError(
                f"item {position} missing fields: {', '.join(missing_item)}"
            )
        if item["id"] in identifiers:
            raise ValueError(f"duplicate item id: {item['id']}")
        identifiers.add(item["id"])
        if item["status"] not in STATUSES:
            raise ValueError(f"invalid status for {item['id']}: {item['status']}")
        if not isinstance(item["conditions"], list) or not item["conditions"]:
            raise ValueError(f"conditions must be non-empty for {item['id']}")
        if not isinstance(item["dependencies"], list):
            raise ValueError(f"dependencies must be a list for {item['id']}")
        try:
            verified_on = date.fromisoformat(item["verified_on"])
            expires_on = date.fromisoformat(item["expires_on"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid verification date for {item['id']}") from error
        if verified_on > expires_on:
            raise ValueError(f"verified_on is after expires_on for {item['id']}")
        if item["type"] == "arrival_plan":
            missing = sorted(field for field in ARRIVAL_PLAN_FIELDS if not item.get(field))
            if missing:
                raise ValueError(
                    f"arrival plan {item['id']} missing fields: {', '.join(missing)}"
                )
            if not isinstance(item["risk_rank"], int) or item["risk_rank"] < 1:
                raise ValueError(f"invalid risk_rank for {item['id']}")
        if item["type"] == "route_segment":
            missing = sorted(field for field in ROUTE_SEGMENT_FIELDS if not item.get(field))
            if missing:
                raise ValueError(
                    f"route segment {item['id']} missing fields: {', '.join(missing)}"
                )
            if not isinstance(item["along_landmarks"], list):
                raise ValueError(f"along_landmarks must be a list for {item['id']}")
        if item["type"] == "service_point":
            if not item.get("service_id"):
                raise ValueError(f"service point {item['id']} missing service_id")
        if item["type"] == "journey_step":
            if not isinstance(item.get("journey_order"), int):
                raise ValueError(f"journey step {item['id']} missing journey_order")
        if item["type"] == "journey_branch":
            missing = sorted(field for field in JOURNEY_BRANCH_FIELDS if not item.get(field))
            if missing:
                raise ValueError(
                    f"journey branch {item['id']} missing fields: {', '.join(missing)}"
                )
            if not isinstance(item["differences"], list):
                raise ValueError(f"differences must be a list for {item['id']}")
        if item["type"] == "examination_card":
            missing = sorted(
                field for field in EXAMINATION_CARD_FIELDS if not item.get(field)
            )
            if missing:
                raise ValueError(
                    f"examination card {item['id']} missing fields: {', '.join(missing)}"
                )
            arrangements = item["hospital_arrangements"]
            if not isinstance(arrangements, dict) or any(
                not isinstance(arrangements.get(stage), list)
                for stage in EXAMINATION_STAGES
            ):
                raise ValueError(
                    f"examination card {item['id']} must define all three stages"
                )
            for stage in EXAMINATION_STAGES:
                for arrangement in arrangements[stage]:
                    if (
                        not isinstance(arrangement, dict)
                        or not arrangement.get("text")
                        or arrangement.get("supported_by") not in ARRANGEMENT_EVIDENCE
                    ):
                        raise ValueError(
                            "unsupported or conflicting arrangement for "
                            f"{item['id']} at {stage}"
                        )

    visible_ids = {item["id"] for item in patient_items(ledger, as_of)}
    expected_types = {
        "campus_item_id": "campus",
        "scope_item_id": "scope",
        "safety_item_id": "safety_notice",
        "fallback_item_id": "fallback",
    }
    items_by_id = {item["id"]: item for item in items}
    selected_exam_item_id = package.get("selected_exam_item_id")
    if selected_exam_item_id:
        selected_exam = items_by_id.get(selected_exam_item_id)
        if selected_exam is None or selected_exam["type"] != "examination_card":
            raise ValueError(
                "selected_exam_item_id must reference an examination_card item"
            )
    for item in items:
        if item["type"] == "arrival_plan":
            anchor = items_by_id.get(item["arrival_anchor_id"])
            if anchor is None or anchor["type"] != "arrival_anchor":
                raise ValueError(
                    f"arrival_anchor_id must reference an arrival_anchor for {item['id']}"
                )
        if item["type"] == "service_point":
            service = items_by_id.get(item["service_id"])
            if service is None or service["type"] != "service":
                raise ValueError(
                    f"service_id must reference a service for {item['id']}"
                )
    for reference, expected_type in expected_types.items():
        item_id = package[reference]
        item = items_by_id.get(item_id)
        if item is None or item["type"] != expected_type:
            raise ValueError(f"{reference} must reference a {expected_type} item")
        if item_id not in visible_ids:
            raise ValueError(f"{reference} must reference a publishable item")

    visible_items = patient_items(ledger, as_of)
    established_items = [item for item in items if item["status"] != "pending"]
    ledger_types = {item["type"] for item in established_items}
    for required_type in ("arrival_anchor", "route_segment", "service_point"):
        if required_type not in ledger_types:
            raise ValueError(f"missing {required_type} item")
    if not any(
        item.get("stage") == package["current_stage"]
        and item["id"] not in {
            package["campus_item_id"],
            package["scope_item_id"],
            package["safety_item_id"],
            package["fallback_item_id"],
        }
        for item in established_items
    ):
        raise ValueError("current_stage has no patient action")

    for item in visible_items:
        if item["status"] != "partial":
            continue
        rendered_fields = {"name", "stage", "conditions", "patient_text"}
        if item.get("next_action"):
            rendered_fields.add("next_action")
        confirmed_fields = set(item.get("confirmed_fields", ()))
        missing_confirmations = rendered_fields - confirmed_fields
        if missing_confirmations:
            raise ValueError(
                f"partial item {item['id']} has unconfirmed patient fields: "
                + ", ".join(sorted(missing_confirmations))
            )

    printable_items = [
        item
        for item in visible_items
        if item["id"] not in {
            package["campus_item_id"],
            package["scope_item_id"],
            package["safety_item_id"],
            package["fallback_item_id"],
        }
        and item["type"] not in {
            "journey_step",
            "journey_branch",
            "examination_category",
            "examination_card",
        }
    ]
    printable_characters = sum(
        len(str(item.get(field, "")))
        for item in printable_items
        for field in ("name", "patient_text", "next_action")
    )
    if len(printable_items) > 12 or printable_characters > 4_000:
        raise ValueError("print view exceeds one-page budget")

    operations = ledger.get("operations")
    if operations is not None:
        if not isinstance(operations, dict):
            raise ValueError("operations must be an object")
        missing = sorted(
            field
            for field in OPERATIONS_FIELDS
            if field not in operations or operations[field] is None
        )
        if missing:
            raise ValueError(f"operations missing fields: {', '.join(missing)}")
        for position, gap in enumerate(operations["gaps"]):
            missing = sorted(field for field in GAP_FIELDS if not gap.get(field))
            if missing:
                raise ValueError(
                    f"gap {position} missing fields: {', '.join(missing)}"
                )
            if gap["item_id"] not in items_by_id:
                raise ValueError(f"gap references unknown item: {gap['item_id']}")
        missing_evidence = REQUIRED_EVIDENCE_KINDS - set(operations["evidence_rules"])
        if missing_evidence:
            raise ValueError("evidence_rules missing: " + ", ".join(sorted(missing_evidence)))
        missing_targets = REQUIRED_COLLECTION_TARGETS - set(operations["collection_matrix"])
        if missing_targets:
            raise ValueError(
                "collection_matrix missing: " + ", ".join(sorted(missing_targets))
            )
        for position, evidence_package in enumerate(operations["route_evidence_packages"]):
            missing = sorted(
                field for field in ROUTE_EVIDENCE_FIELDS if not evidence_package.get(field)
            )
            if missing:
                raise ValueError(
                    f"route evidence package {position} missing fields: {', '.join(missing)}"
                )
            route = items_by_id.get(evidence_package["route_item_id"])
            if route is None or route["type"] != "route_segment":
                raise ValueError("route evidence package must reference a route_segment")
        missing_gates = REQUIRED_PROMOTION_GATES - set(operations["promotion_gates"])
        if missing_gates:
            raise ValueError("promotion_gates missing: " + ", ".join(sorted(missing_gates)))
        cycles = operations["review_cycles"]
        for field in ("high_risk_days", "route_days", "standard_days"):
            if not isinstance(cycles.get(field), int) or cycles[field] < 1:
                raise ValueError(f"review_cycles missing or invalid: {field}")
        expected_cycles = {
            "high_risk_days": 30,
            "route_days": 90,
            "standard_days": 180,
        }
        for field, expected in expected_cycles.items():
            if cycles[field] != expected:
                raise ValueError(f"{field} must be {expected}")
        audit_fields = set(operations["audit_fields"])
        if not REQUIRED_AUDIT_FIELDS.issubset(audit_fields):
            raise ValueError("audit_fields incomplete")
        controlled_types = {
            "arrival_anchor",
            "route_segment",
            "service_point",
            "examination_card",
        }
        promotion_reviews = operations["promotion_reviews"]
        for item in items:
            if item["status"] != "verified" or item["type"] not in controlled_types:
                continue
            review = promotion_reviews.get(item["id"])
            if not isinstance(review, dict):
                raise ValueError(f"missing promotion review for {item['id']}")
            if (
                review.get("outcome") != "approved"
                or review.get("reviewer") == item["maintainer"]
                or not review.get("evidence_kinds")
            ):
                raise ValueError(f"invalid promotion review for {item['id']}")
            required_kind = {
                "route_segment": "路线走测",
                "arrival_anchor": "现场标识照片",
                "service_point": "现场标识照片",
                "examination_card": "官方资料",
            }[item["type"]]
            if required_kind not in review["evidence_kinds"]:
                raise ValueError(
                    f"promotion review for {item['id']} requires {required_kind}"
                )
        for position, event in enumerate(operations["events"]):
            missing = sorted(field for field in EVENT_FIELDS if not event.get(field))
            if missing:
                raise ValueError(f"event {position} missing fields: {', '.join(missing)}")
            if event["type"] not in EVENT_STATUSES:
                raise ValueError(f"invalid event type: {event['type']}")
            if not event["affected_item_ids"] or any(
                item_id not in items_by_id for item_id in event["affected_item_ids"]
            ):
                raise ValueError(f"event {event['id']} has invalid affected_item_ids")
        for position, clue in enumerate(operations["feedback_clues"]):
            forbidden = sorted(FORBIDDEN_FEEDBACK_FIELDS & set(clue))
            if forbidden:
                raise ValueError("forbidden feedback field: " + ", ".join(forbidden))
            missing = sorted(field for field in FEEDBACK_FIELDS if not clue.get(field))
            if missing:
                raise ValueError(
                    f"feedback clue {position} missing fields: {', '.join(missing)}"
                )
            if clue["status"] != "pending_verification":
                raise ValueError("feedback clues must remain pending_verification")
        for position, record in enumerate(operations["audit_records"]):
            missing = sorted(field for field in AUDIT_RECORD_FIELDS if field not in record)
            if missing:
                raise ValueError(
                    f"audit record {position} missing fields: {', '.join(missing)}"
                )

    release = ledger.get("release")
    if release is not None:
        if not isinstance(release, dict):
            raise ValueError("release must be an object")
        missing = sorted(field for field in RELEASE_FIELDS if not release.get(field))
        if missing:
            raise ValueError(f"release missing fields: {', '.join(missing)}")
        serialized_release = json.dumps(release, ensure_ascii=False).lower()
        if any(marker.lower() in serialized_release for marker in PRIVATE_DATA_MARKERS):
            raise ValueError("release contains forbidden private data")
        delivery = release["spec_delivery"]
        for field in (
            "fields_and_templates_complete",
            "evidence_and_gaps_complete",
            "acceptance_checklist_complete",
            "example_not_publication",
        ):
            if not delivery.get(field):
                raise ValueError(f"spec delivery gate incomplete: {field}")
        if not REQUIRED_ACCESSIBILITY_CHECKS.issubset(release["accessibility_checks"]):
            raise ValueError("accessibility checks incomplete")
        if not REQUIRED_PRIVACY_CHECKS.issubset(release["privacy_checks"]):
            raise ValueError("privacy checks incomplete")
        for schematic in release["schematics"]:
            route_ids = schematic.get("route_item_ids", [])
            if (
                not schematic.get("name")
                or not schematic.get("coverage")
                or not schematic.get("breakpoint")
                or not route_ids
                or any(
                    items_by_id.get(item_id, {}).get("type") != "route_segment"
                    for item_id in route_ids
                )
            ):
                raise ValueError("invalid local schematic")
        for target in release["qr_targets"]:
            required = {
                "name",
                "campus_item_id",
                "url",
                "short_url",
                "verified_on",
                "fallback",
                "dependent_item_ids",
                "public_and_updatable",
            }
            if any(not target.get(field) for field in required):
                raise ValueError("invalid QR target")
            if (
                not target["url"].startswith("https://")
                or not target["short_url"].startswith("https://")
                or target["campus_item_id"] != package["campus_item_id"]
                or any(item_id not in items_by_id for item_id in target["dependent_item_ids"])
            ):
                raise ValueError("QR target must use a stable public page")
        for external_map in release["external_maps"]:
            item = items_by_id.get(external_map.get("item_id"))
            if (
                item is None
                or item["type"] not in {"campus", "arrival_anchor"}
                or not external_map.get("url", "").startswith("https://")
                or "室内点位不作为服务点证据" not in external_map.get("scope", "")
            ):
                raise ValueError("external map must reference campus or outdoor anchor only")
        publication = release["publication_checks"]
        route_ids = publication.get("end_to_end_route_item_ids", [])
        publication_routes = [items_by_id.get(item_id) for item_id in route_ids]
        if (
            not publication_routes
            or any(
                route is None
                or route["type"] != "route_segment"
                for route in publication_routes
            )
            or any(
                current["end_landmark"] != following["start_landmark"]
                for current, following in zip(
                    publication_routes, publication_routes[1:]
                )
            )
        ):
            raise ValueError("publication gate requires an end-to-end route")
        service_point = items_by_id.get(publication.get("general_service_point_item_id"))
        if (
            service_point is None
            or service_point["type"] != "service_point"
            or publication_routes[-1]["id"] not in service_point["dependencies"]
        ):
            raise ValueError("publication gate requires a general service point")
        for field in (
            "high_risk_review_complete",
            "derived_consistency_complete",
            "technical_and_accessibility_complete",
            "limited_coverage",
        ):
            if not publication.get(field):
                raise ValueError(f"publication gate incomplete: {field}")
        tests = release["representative_tests"]
        if tests.get("tester_count", 0) < 5 or not tests.get("editors_excluded"):
            raise ValueError("publication gate requires at least 5 representative testers")
        if not REQUIRED_TEST_TASKS.issubset(tests.get("tasks", [])):
            raise ValueError("representative test tasks incomplete")
        for field in (
            "dangerous_advice_count",
            "wrong_route_count",
            "false_continuity_count",
        ):
            if tests.get(field) != 0:
                raise ValueError(f"representative tests failed: {field}")
        if not REQUIRED_RELEASE_WORKFLOW.issubset(release["workflow"]):
            raise ValueError("release workflow incomplete")
        if not all(release["pilot"].get(field) for field in (
            "completed",
            "declared_conditions_walked",
            "serious_issues_resolved",
        )):
            raise ValueError("onsite pilot incomplete")
        if any(not release["owners"].get(field) for field in (
            "maintenance",
            "expiry_reminders",
            "feedback_queue",
            "emergency_withdrawal",
            "restoration",
        )):
            raise ValueError("release owners incomplete")


def apply_operational_events(ledger: dict[str, Any]) -> dict[str, Any]:
    effective = copy.deepcopy(ledger)
    items_by_id = {item["id"]: item for item in effective["items"]}
    for event in effective.get("operations", {}).get("events", []):
        effective_status = EVENT_STATUSES[event["type"]]
        for item_id in event["affected_item_ids"]:
            items_by_id[item_id]["status"] = effective_status
    return effective


def operations_markdown(operations: dict[str, Any]) -> str:
    lines = [
        "# 内容核验、采集与纠错工作流",
        "",
        "本页供维护者与复核者使用，不是患者指南。",
        "",
        "## 逐项资料缺口",
    ]
    for gap in operations["gaps"]:
        lines.extend(
            [
                "",
                f"### {gap['item_id']}",
                "",
                f"**责任人：** {gap['owner']}",
                "",
                f"**所需证据：** {gap['required_evidence']}",
                "",
                f"**下一步采集动作：** {gap['next_action']}",
                "",
                f"**明确不采集：** {gap['excluded']}",
            ]
        )
    lines.extend(["", "## 证据要求"])
    for kind, rule in operations["evidence_rules"].items():
        lines.extend(["", f"- **{kind}：** {rule}"])
    lines.extend(["", "## 首轮采集矩阵"])
    for target, action in operations["collection_matrix"].items():
        lines.extend(["", f"- **{target}：** {action}"])
    lines.extend(["", "## 路线段证据包"])
    labels = {
        "start_node": "起点行动节点",
        "end_node": "终点行动节点",
        "action_and_landmarks": "行动与标志",
        "direction_and_floor_change": "方向及楼层变化",
        "conditions": "通行条件",
        "collected_at": "采集日期时间",
        "applicable_times": "适用时段",
        "photo_privacy_check": "照片隐私检查",
    }
    for package in operations["route_evidence_packages"]:
        lines.extend(["", f"### {package['route_item_id']}"])
        for field, label in labels.items():
            lines.extend(["", f"**{label}：** {package[field]}"])
    lines.extend(["", "## 状态提升与独立复核门槛"])
    for subject, rule in operations["promotion_gates"].items():
        lines.extend(["", f"- **{subject}：** {rule}"])
    cycles = operations["review_cycles"]
    lines.extend(
        [
            "",
            "## 定期复核与事件触发",
            "",
            f"- 高风险信息：{cycles['high_risk_days']} 天",
            f"- 路线与入口：{cycles['route_days']} 天",
            f"- 普通稳定信息：{cycles['standard_days']} 天",
        ]
    )
    for event, action in operations["event_triggers"].items():
        lines.append(f"- **{event}：** {action}")
    if operations["events"]:
        lines.extend(["", "## 当前事件队列"])
        for event in operations["events"]:
            lines.append(
                f"- **{event['id']}：** {event['type']} · 责任人 {event['owner']} · "
                f"影响 {', '.join(event['affected_item_ids'])} · {event['next_action']}"
            )
    lines.extend(["", "## 待核验反馈线索"])
    for clue in operations["feedback_clues"]:
        lines.append(
            f"- **{clue['id']}：** {clue['location']} · {clue['observation']} · "
            f"{clue['status']}"
        )
    lines.extend(
        [
            "",
            "## 冲突、反馈与紧急处置",
            "",
            operations["conflict_policy"],
            "",
            operations["feedback_policy"],
            "",
            operations["emergency_policy"],
            "",
            "## 审计记录",
            "",
            "每次状态或内容变化必须记录：" + "、".join(operations["audit_fields"]) + "。",
        ]
    )
    for record in operations["audit_records"]:
        lines.extend(
            [
                "",
                f"### {record['occurred_at']} · {record['operator']}",
                "",
                f"- 变更前：{record['before']}",
                f"- 变更后：{record['after']}",
                f"- 原因：{record['reason']}",
                f"- 证据：{record['evidence']}",
                f"- 复核结果：{record['review_result']}",
                f"- 受影响路线：{', '.join(record['affected_routes']) or '无'}",
                f"- 受影响卡片：{', '.join(record['affected_cards']) or '无'}",
                f"- 受影响派生载体：{', '.join(record['affected_outputs']) or '无'}",
            ]
        )
    return "\n".join(lines) + "\n"


def fact_markdown(item: dict[str, Any], fallback: str) -> str:
    confirmed_fields = set(item.get("confirmed_fields", ()))
    text = item.get("patient_text", "")
    if item["status"] == "partial" and "patient_text" not in confirmed_fields:
        text = ""
    if not text:
        return ""
    lines = [
        f"### {item['name']}",
        "",
        f"**当前阶段：** {item.get('stage', '请按预约单确认')}",
        "",
        f"**必要条件：** {'、'.join(item['conditions'])}",
        "",
        text,
        "",
        f"**事实编号：{item['id']}** · 资料状态："
        + ("已核验" if item["status"] == "verified" else "部分核验"),
    ]
    show_next_action = item.get("next_action") and (
        item["status"] == "verified" or "next_action" in confirmed_fields
    )
    if show_next_action:
        lines.extend(["", f"**下一步：** {item['next_action']}"])
    lines.extend(["", f"**无法确认时：** {fallback}"])
    return "\n".join(lines)


def arrival_plan_markdown(item: dict[str, Any], items_by_id: dict[str, Any]) -> str:
    anchor = items_by_id[item["arrival_anchor_id"]]
    realtime = item.get("realtime")
    lines = [
        f"### {item['risk_rank']}. {item['name']}",
        "",
        f"**适用人群：** {item['audience']}",
        "",
        f"**出发前：** {item['before_departure']}",
        "",
        f"**到院锚点：** {anchor['patient_text']}（事实编号：{anchor['id']}）",
        "",
        f"**切换条件：** {item['failure_trigger']}",
        "",
        f"**首选替代：** {item['preferred_alternative']}",
        "",
        f"**最终兜底：** {item['final_fallback']}",
    ]
    if realtime:
        lines.extend(
            [
                "",
                f"**实时查询：** [{realtime['label']}]({realtime['url']})；"
                f"{realtime['when_to_check']}。余位、预约、收费、道路管制和当天入口"
                "状态不在本页静态承诺。",
            ]
        )
    if item.get("passenger_action"):
        lines.extend(["", f"**乘客：** {item['passenger_action']}"])
    if item.get("driver_action"):
        lines.extend(["", f"**司机：** {item['driver_action']}"])
    lines.extend(["", f"**事实编号：{item['id']}** · 资料状态：已核验"])
    return "\n".join(lines)


def route_segment_markdown(item: dict[str, Any], fallback: str) -> str:
    return "\n".join(
        [
            f"### {item['name']}",
            "",
            f"**路线类型：** {item['route_mode']}（不与其他路线互相推断）",
            "",
            f"**起点标志：** {item['start_landmark']}",
            "",
            f"**行动：** {item['action']}",
            "",
            f"**沿途标志：** {'、'.join(item['along_landmarks'])}",
            "",
            f"**终点标志：** {item['end_landmark']}",
            "",
            f"**通行条件：** {'、'.join(item['conditions'])}",
            "",
            f"**无法继续时：** 在最近可靠行动节点停止。{fallback}",
            "",
            f"**事实编号：{item['id']}** · 资料状态："
            + ("已核验" if item["status"] == "verified" else "部分核验"),
        ]
    )


def service_point_markdown(item: dict[str, Any], items_by_id: dict[str, Any], fallback: str) -> str:
    service = items_by_id[item["service_id"]]
    location = " · ".join(
        item.get(field, "待确认")
        for field in ("campus", "building", "floor", "zone")
    )
    lines = [
            f"### {service['name']}：{item['name']}",
            "",
            f"**正式位置：** {location}",
            "",
            f"**适用条件：** {'、'.join(item['conditions'])}",
            "",
            item["patient_text"],
            "",
            f"**事实编号：{item['id']}** · 服务编号：{service['id']}",
    ]
    confirmed_fields = set(item.get("confirmed_fields", ()))
    if item.get("next_action") and (
        item["status"] == "verified" or "next_action" in confirmed_fields
    ):
        lines.extend(["", f"**下一步：** {item['next_action']}"])
    lines.extend(["", f"**无法确认时：** {fallback}"])
    return "\n".join(lines)


def journey_markdown(
    view_items: list[dict[str, Any]],
    ledger: dict[str, Any],
    visible_ids: set[str],
    stage: str | None,
) -> str:
    package = ledger["package"]
    steps = sorted(
        (item for item in view_items if item["type"] == "journey_step"),
        key=lambda item: item["journey_order"],
    )
    if not steps:
        return ""
    lines = ["## 共享核心旅程"]
    for item in steps:
        lines.extend(
            [
                "",
                f"### {item['journey_order']}. {item['name']}",
                "",
                item["patient_text"],
                "",
                f"**事实编号：{item['id']}**",
            ]
        )

    selected_branch = package.get("selected_branch")
    if selected_branch:
        branch = next(
            (
                item
                for item in ledger["items"]
                if item["type"] == "journey_branch"
                and item["branch_key"] == selected_branch
            ),
            None,
        )
        if stage is not None and branch and branch.get("stage") != stage:
            branch = None
            selected_branch = None
    if selected_branch:
        lines.extend(
            [
                "",
                "## 手动选择的旅程分支",
                "",
                f"**当前分支：** {selected_branch}",
                "",
                "**选择规则：** 用户依据预约单、医嘱或院方正式服务名称手动选择；"
                "不根据年龄、性别、症状或健康数据自动推断。",
            ]
        )
        if (
            branch
            and branch["status"] == "verified"
            and branch["id"] in visible_ids
        ):
            lines.extend(
                [
                    "",
                    f"**用户依据：** {branch['selection_basis']}",
                    "",
                    *[f"- {difference}" for difference in branch["differences"]],
                    "",
                    f"**事实编号：{branch['id']}**",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "分支资料暂不可用，继续使用共享核心旅程；"
                    "查看预约单、联系检查科室或询问工作人员。",
                ]
            )
    lines.extend(
        [
            "",
            "本次显示不会保存患者身份、预约内容或检查结果，也不会跨设备同步。",
        ]
    )
    return "\n".join(lines)


def examination_card_markdown(item: dict[str, Any]) -> str:
    stage_labels = {
        "before_departure": "出发前",
        "after_arrival": "到院后",
        "after_completion": "完成后",
    }
    lines = [
        f"## 检查卡：{item['name']}",
        "",
        "检查大类仅用于查找；进入卡片前核对完整检查项目名称。"
        "相近但流程不同的项目不共享准备要求。",
        "",
        f"**检查大类：** {item['category']}",
        "",
        f"**完整检查项目名称：** {item['official_exam_name']}",
    ]
    for stage in EXAMINATION_STAGES:
        lines.extend(
            [
                "",
                f"## {stage_labels[stage]}",
                "",
                "### 本次或本院安排",
                "",
                *[
                    f"- {arrangement['text']}（依据："
                    + (
                        "当前本院资料"
                        if arrangement["supported_by"] == "current_hospital"
                        else "本次预约单"
                    )
                    + "）"
                    for arrangement in item["hospital_arrangements"][stage]
                ],
            ]
        )
    lines.extend(
        [
            "",
            "### 通用安全提醒",
            "",
            *[f"- {text}" for text in item["general_safety"]],
            "",
            "### 尚待确认",
            "",
            *[f"- {text}" for text in item["unconfirmed"]],
            "",
            "本指南不指导停药、剂量调整、镇静、增强或造影风险处置，"
            "也不解读检查报告；特殊情况请主动向检查科室申报。",
            "",
            f"**事实编号：{item['id']}**",
        ]
    )
    return "\n".join(lines)


def schematic_markdown(ledger: dict[str, Any], as_of: date) -> str:
    visible_ids = {item["id"] for item in patient_items(ledger, as_of)}
    items_by_id = {item["id"]: item for item in ledger["items"]}
    fallback = items_by_id[ledger["package"]["fallback_item_id"]]["patient_text"]
    lines = [
        "# 局部示意图",
        "",
        "局部示意图只表达结构化底稿中已核验的限定路线，不是完整院区地图。",
    ]
    for schematic in ledger["release"]["schematics"]:
        routes = [items_by_id[item_id] for item_id in schematic["route_item_ids"]]
        if any(
            route["id"] not in visible_ids or route["status"] != "verified"
            for route in routes
        ):
            lines.extend(
                [
                    "",
                    f"## {schematic['name']}",
                    "",
                    '!!! warning "局部示意图暂不可用"',
                    f"    依赖路线已过期、有争议或下架。{fallback}",
                ]
            )
            continue
        lines.extend(
            [
                "",
                f"## {schematic['name']}",
                "",
                f"**限定起点：** {routes[0]['start_landmark']}",
                "",
                f"**限定终点：** {routes[-1]['end_landmark']}",
                "",
                f"**覆盖区域：** {schematic['coverage']}",
                "",
                f"**路线断点：** {schematic['breakpoint']}",
                "",
                "### 文字等价说明",
                "",
            ]
        )
        for route in routes:
            lines.append(
                f"- {route['start_landmark']} → {route['action']} → "
                f"{route['end_landmark']}（信息项编号：{route['id']}）"
            )
        lines.extend(["", f"**无法继续时：** {fallback}"])
    return "\n".join(lines) + "\n"


def qr_targets_markdown(ledger: dict[str, Any], as_of: date) -> str:
    visible_ids = {item["id"] for item in patient_items(ledger, as_of)}
    items_by_id = {item["id"]: item for item in ledger["items"]}
    campus = items_by_id[ledger["package"]["campus_item_id"]]["patient_text"]
    lines = [
        "# 二维码目标",
        "",
        "二维码只指向可更新的稳定公共页面，不编码患者信息或指南事实。",
    ]
    for target in ledger["release"]["qr_targets"]:
        lines.extend(["", f"## {target['name']}", ""])
        if any(item_id not in visible_ids for item_id in target["dependent_item_ids"]):
            lines.extend(
                [
                    '!!! warning "目标已紧急下架"',
                    f"    {target['fallback']}",
                ]
            )
            continue
        lines.extend(
            [
                f"**目标名称：** {target['name']}",
                "",
                f"**适用院区：** {campus}",
                "",
                f"**稳定公共页面：** [{target['url']}]({target['url']})",
                "",
                f"![{target['name']}二维码]({target['id']}.svg)"
                '{ loading="lazy" width="224" }',
                "",
                f"**短链接：** {target['short_url']}",
                "",
                f"**核验日期：** {target['verified_on']}",
                "",
                f"**扫码失败：** {target['fallback']}",
            ]
        )
    lines.extend(["", "## 外部地图边界"])
    for external_map in ledger["release"]["external_maps"]:
        item = items_by_id[external_map["item_id"]]
        if item["id"] in visible_ids:
            lines.extend(
                [
                    "",
                    f"- [{external_map['name']}]({external_map['url']})："
                    f"{external_map['scope']}（信息项编号：{item['id']}）",
                ]
            )
    return "\n".join(lines) + "\n"


def publication_ready(ledger: dict[str, Any], as_of: date) -> bool:
    release = ledger["release"]
    items_by_id = {item["id"]: item for item in ledger["items"]}
    visible_ids = {item["id"] for item in patient_items(ledger, as_of)}
    publication = release["publication_checks"]
    controlled_ids = [
        *publication["end_to_end_route_item_ids"],
        publication["general_service_point_item_id"],
    ]
    return all(
        item_id in visible_ids
        and (
            items_by_id[item_id]["type"] == "service_point"
            or items_by_id[item_id]["status"] == "verified"
        )
        for item_id in controlled_ids
    )


def release_markdown(release: dict[str, Any], is_publication_ready: bool) -> str:
    tests = release["representative_tests"]
    owners = release["owners"]
    lines = [
        "# 发布验收记录",
        "",
        "**规范交付就绪：** 通过",
        "",
        release["spec_delivery"]["example_not_publication"],
        "",
        (
            "**指南发布就绪：** 通过（仅限虚构示例）"
            if is_publication_ready
            else "**指南发布就绪：** 未通过；受影响内容已降级或下架"
        ),
        "",
        f"有限覆盖声明：{release['publication_checks']['limited_coverage']}",
        "",
        "## 代表性用户测试",
        "",
        f"{tests['tester_count']} 名未参与编辑的代表性测试者已完成："
        + "、".join(tests["tasks"]) + "。",
        "",
        "危险建议、错误路线和虚假连续导航均为 0。",
        "",
        "## 发布流程",
        "",
        " → ".join(release["workflow"]),
        "",
        "## 技术、无障碍与隐私检查",
        "",
        "- 技术与无障碍：" + "、".join(release["accessibility_checks"]),
        "- 隐私：" + "、".join(release["privacy_checks"]),
        "",
        "## 运营责任",
        "",
        f"- 维护责任：{owners['maintenance']}",
        f"- 到期提醒：{owners['expiry_reminders']}",
        f"- 反馈队列：{owners['feedback_queue']}",
        f"- 紧急下架及恢复责任：{owners['emergency_withdrawal']} / {owners['restoration']}",
    ]
    return "\n".join(lines) + "\n"


def render_view(
    ledger: dict[str, Any],
    as_of: date,
    title: str,
    intro: str,
    css_class: str | None = None,
    stage: str | None = None,
) -> str:
    package = ledger["package"]
    items_by_id = {item["id"]: item for item in ledger["items"]}
    header_ids = {
        package["campus_item_id"],
        package["scope_item_id"],
        package["safety_item_id"],
        package["fallback_item_id"],
    }
    publishable_items = patient_items(ledger, as_of)
    visible_ids = {item["id"] for item in publishable_items}
    items = [
        item
        for item in publishable_items
        if item["id"] not in header_ids
        and (stage is None or item.get("stage") == stage)
    ]
    campus = items_by_id[package["campus_item_id"]]
    scope = items_by_id[package["scope_item_id"]]
    safety = items_by_id[package["safety_item_id"]]
    fallback_item = items_by_id[package["fallback_item_id"]]
    fallback = fallback_item["patient_text"]
    reviewed_on = max(
        items_by_id[item_id]["verified_on"] for item_id in header_ids
    )
    sections = [
        "---",
        "hide:",
        "  - navigation",
        "---",
        "",
        f'<div class="{css_class}" markdown>' if css_class else "",
        "",
        f"# {title}",
        "",
        '!!! danger "演示资料：非真实患者指引"',
        "    本页所有院区、入口、路线和服务点均为虚构示例，不可用于实际就医。",
        "",
        f"**适用院区：** {campus['patient_text']}（事实编号：{campus['id']}）",
        "",
        f"**覆盖范围：** {scope['patient_text']}（事实编号：{scope['id']}）",
        "",
        f"**最近核验：{reviewed_on}**（依据：{', '.join(sorted(header_ids))}）",
        "",
        '!!! warning "使用前先核对"',
        f"    {safety['patient_text']}（事实编号：{safety['id']}）",
        "",
        "[完整指南](index.md) · [当前阶段速查](quick.md) · [一页打印版](print.md)",
        "",
        intro,
    ]
    if css_class == "guide-print-view" and ledger.get("release"):
        print_settings = ledger["release"]["print"]
        sections.extend(
            [
                f"**生成日期：** {as_of.isoformat()}",
                f"**资料核验日期：** {reviewed_on}",
                f"**过期提示：** {print_settings['expiry_warning']}",
                f"**在线复核：** {print_settings['online_review_url']}",
                f"**官方兜底：** {print_settings['official_fallback']}",
            ]
        )
    arrival_plans = (
        []
        if css_class == "guide-print-view"
        else sorted(
            (item for item in items if item["type"] == "arrival_plan"),
            key=lambda item: item["risk_rank"],
        )
    )
    if arrival_plans:
        sections.extend(["## 到院方案（按风险排序）"])
        sections.extend(arrival_plan_markdown(item, items_by_id) for item in arrival_plans)
    journey = journey_markdown(items, ledger, visible_ids, stage)
    if journey:
        sections.append(journey)
    examination_cards = [
        item
        for item in items
        if item["type"] == "examination_card"
        and item["id"] == package.get("selected_exam_item_id")
    ]
    sections.extend(examination_card_markdown(item) for item in examination_cards)
    selected_exam_id = package.get("selected_exam_item_id")
    selected_exam = items_by_id.get(selected_exam_id) if selected_exam_id else None
    exam_is_relevant = (
        selected_exam is not None
        and (stage is None or selected_exam.get("stage") == stage)
    )
    if selected_exam_id and exam_is_relevant and not examination_cards:
        sections.extend(
            [
                '!!! warning "所选检查卡资料暂不可用"',
                "    查看预约单并联系检查科室，确认完整检查项目名称和本次准备要求；"
                "不要套用相近项目的指引。",
            ]
        )
    regular_items = [
        item
        for item in items
        if item["type"] not in {
            "arrival_plan",
            "service",
            "journey_step",
            "journey_branch",
            "examination_card",
            "examination_category",
        }
    ]
    for item in regular_items:
        if item["type"] == "route_segment":
            sections.append(route_segment_markdown(item, fallback))
        elif item["type"] == "service_point":
            sections.append(service_point_markdown(item, items_by_id, fallback))
        else:
            sections.append(fact_markdown(item, fallback))
    if arrival_plans:
        sections.extend(
            [
                '!!! warning "驾驶安全"',
                "    驾驶员不要滚动阅读或操作实时查询。查询与切换只能在出发前、"
                "由乘客操作，或安全停车后进行。",
            ]
        )
    degraded = any(
        item["status"] in {"expired", "disputed", "withdrawn"}
        or (
            item["status"] in {"verified", "partial"}
            and any(dependency not in visible_ids for dependency in item["dependencies"])
        )
        for item in ledger["items"]
    )
    if degraded:
        sections.extend(
            [
                '!!! warning "路线或服务信息暂不可用"',
                f"    上游事实未达到可发布状态。{fallback}（事实编号：{fallback_item['id']}）",
            ]
        )
    if css_class:
        sections.append("</div>")
    return "\n\n".join(section for section in sections if section) + "\n"


def build(ledger: dict[str, Any], output: Path, as_of: date) -> None:
    validate(ledger, as_of)
    effective_ledger = apply_operational_events(ledger)
    views = {
        "index.md": render_view(
            effective_ledger,
            as_of,
            effective_ledger["package"]["name"],
            "按旅程查看已证实的信息；每项事实均显示可追溯编号。",
        ),
        "quick.md": render_view(
            effective_ledger,
            as_of,
            "当前阶段速查",
            "只执行与你当前阶段相符的下一步；不确定时立即采用现场确认兜底。",
            stage=effective_ledger["package"]["current_stage"],
        ),
        "print.md": render_view(
            effective_ledger,
            as_of,
            "一页打印速查",
            "打印前请在线复核核验日期；本页仅保留有限覆盖行动。",
            css_class="guide-print-view",
            stage=(
                effective_ledger["package"]["current_stage"]
                if "release" in effective_ledger
                else None
            ),
        ),
    }
    if "operations" in ledger:
        views["operations.md"] = operations_markdown(ledger["operations"])
    if "release" in ledger:
        views["schematic.md"] = schematic_markdown(effective_ledger, as_of)
        views["qr.md"] = qr_targets_markdown(effective_ledger, as_of)
        views["release.md"] = release_markdown(
            ledger["release"],
            publication_ready(effective_ledger, as_of),
        )
    output.mkdir(parents=True, exist_ok=True)
    for filename, content in views.items():
        (output / filename).write_text(content, encoding="utf-8")
    for target in ledger.get("release", {}).get("qr_targets", []):
        if all(
            item_id in {item["id"] for item in patient_items(effective_ledger, as_of)}
            for item_id in target["dependent_item_ids"]
        ):
            subprocess.run(
                [
                    "node",
                    str(Path(__file__).with_name("write_qr_svg.js")),
                    target["url"],
                    str(output / f"{target['id']}.svg"),
                ],
                check=True,
                capture_output=True,
                text=True,
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        ledger = json.loads(args.source.read_text(encoding="utf-8"))
        build(ledger, args.output, args.as_of)
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(f"guide package build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
