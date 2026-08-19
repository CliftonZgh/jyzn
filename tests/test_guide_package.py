import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_COMMAND = ROOT / "scripts" / "build_guide_package.py"


def valid_package() -> dict:
    return {
        "package": {
            "name": "安心示例院区门诊指南",
            "is_example": True,
            "campus_item_id": "campus-01",
            "scope_item_id": "scope-01",
            "safety_item_id": "safety-01",
            "fallback_item_id": "fallback-01",
            "current_stage": "到院",
            "active_conditions": ["普通门诊", "日间"],
        },
        "items": [
            {
                "id": "campus-01",
                "name": "安心示例医院·中心院区",
                "type": "campus",
                "conditions": ["普通门诊"],
                "source": "虚构示例资料",
                "evidence": "示例院区身份记录",
                "status": "verified",
                "verified_on": "2026-08-01",
                "expires_on": "2026-11-01",
                "maintainer": "示例维护者",
                "reviewer": "示例复核者",
                "dependencies": [],
                "patient_text": "安心示例医院·中心院区（虚构）",
            },
            {
                "id": "scope-01", "name": "指南覆盖范围", "type": "scope",
                "conditions": ["普通门诊"], "source": "虚构示例资料",
                "evidence": "示例覆盖范围审批记录", "status": "verified",
                "verified_on": "2026-08-01", "expires_on": "2026-11-01",
                "maintainer": "示例维护者", "reviewer": "示例复核者",
                "dependencies": ["campus-01"],
                "patient_text": "普通门诊：示例入口至示例导诊台",
            },
            {
                "id": "safety-01", "name": "安全优先说明", "type": "safety_notice",
                "conditions": ["普通门诊"], "source": "虚构示例资料",
                "evidence": "示例安全规则审批记录", "status": "verified",
                "verified_on": "2026-08-01", "expires_on": "2026-11-01",
                "maintainer": "示例维护者", "reviewer": "示例复核者",
                "dependencies": ["campus-01"],
                "patient_text": "预约单、医嘱、当天院内指引和工作人员指示优先于本指南。",
            },
            {
                "id": "fallback-01", "name": "现场确认兜底", "type": "fallback",
                "conditions": ["普通门诊"], "source": "虚构示例资料",
                "evidence": "示例安全规则审批记录", "status": "verified",
                "verified_on": "2026-08-01", "expires_on": "2026-11-01",
                "maintainer": "示例维护者", "reviewer": "示例复核者",
                "dependencies": ["campus-01"],
                "patient_text": "停止前进，查看预约单并在现场询问工作人员。",
            },
            {
                "id": "service-01", "name": "普通门诊导诊", "type": "service",
                "conditions": ["普通门诊", "日间"], "source": "虚构示例资料",
                "evidence": "示例服务定义", "status": "verified",
                "verified_on": "2026-08-01", "expires_on": "2026-09-01",
                "maintainer": "示例维护者", "reviewer": "示例复核者",
                "dependencies": ["campus-01"], "stage": "报到",
                "patient_text": "协助确认普通门诊报到位置。",
            },
            {
                "id": "anchor-01",
                "name": "门诊入口 A",
                "type": "arrival_anchor",
                "conditions": ["普通门诊", "日间"],
                "source": "虚构现场走测",
                "evidence": "示例入口照片与走测记录",
                "status": "verified",
                "verified_on": "2026-08-01",
                "expires_on": "2026-09-01",
                "maintainer": "示例维护者",
                "reviewer": "示例复核者",
                "dependencies": ["campus-01"],
                "stage": "到院",
                "patient_text": "在标有“门诊入口 A”的虚构入口确认院区。",
                "next_action": "进入后寻找蓝色示例导诊标志。",
            },
            {
                "id": "route-01",
                "name": "入口 A 至导诊台",
                "type": "route_segment",
                "conditions": ["普通门诊", "日间"],
                "source": "虚构现场走测",
                "evidence": "示例连续路线记录",
                "status": "verified",
                "verified_on": "2026-08-01",
                "expires_on": "2026-09-01",
                "maintainer": "示例维护者",
                "reviewer": "示例复核者",
                "dependencies": ["anchor-01"],
                "stage": "报到",
                "start_landmark": "门诊入口 A",
                "action": "直行至蓝色示例导诊标志",
                "along_landmarks": ["入口总索引"],
                "end_landmark": "蓝色示例导诊标志",
                "route_mode": "普通步行路线",
                "patient_text": "从入口 A 直行至蓝色示例导诊标志。",
                "next_action": "在示例导诊台出示预约单并确认报到地点。",
            },
            {
                "id": "desk-01",
                "name": "示例导诊服务点",
                "type": "service_point",
                "conditions": ["普通门诊", "日间"],
                "source": "虚构现场走测",
                "evidence": "示例服务点记录",
                "status": "partial",
                "verified_on": "2026-08-01",
                "expires_on": "2026-09-01",
                "maintainer": "示例维护者",
                "reviewer": "示例复核者",
                "dependencies": ["route-01"],
                "stage": "报到",
                "service_id": "service-01",
                "campus": "安心示例医院·中心院区",
                "building": "示例门诊楼",
                "floor": "待确认",
                "zone": "待确认",
                "confirmed_fields": [
                    "name", "stage", "conditions", "patient_text", "next_action"
                ],
                "patient_text": "示例导诊台可协助确认普通门诊报到位置。",
                "next_action": "向工作人员说明预约单上的正式服务名称。",
                "unconfirmed_note": "楼层待补充",
            },
        ],
    }


class GuidePackageCommandTests(unittest.TestCase):
    def run_build(self, data: dict) -> tuple[subprocess.CompletedProcess[str], Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        directory = Path(temp_dir.name)
        source = directory / "package.json"
        output = directory / "output"
        source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable, str(BUILD_COMMAND),
                "--source", str(source), "--output", str(output),
                "--as-of", "2026-08-05",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        return result, output

    def test_generates_three_patient_views_from_one_ledger(self) -> None:
        result, output = self.run_build(valid_package())

        self.assertEqual(result.returncode, 0, result.stderr)
        expected = {"index.md", "quick.md", "print.md"}
        self.assertEqual({path.name for path in output.glob("*.md")}, expected)
        for filename in expected:
            rendered = (output / filename).read_text(encoding="utf-8")
            self.assertIn("非真实患者指引", rendered)
            self.assertIn("安心示例医院·中心院区（虚构）", rendered)
            self.assertIn("普通门诊：示例入口至示例导诊台", rendered)
            self.assertIn("最近核验：2026-08-01", rendered)
            self.assertIn("预约单、医嘱、当天院内指引和工作人员指示优先", rendered)
            self.assertIn("事实编号：", rendered)

    def test_all_views_filter_statuses_and_degrade_broken_dependencies(self) -> None:
        package = valid_package()
        next(item for item in package["items"] if item["id"] == "anchor-01")["status"] = "expired"
        hidden_statuses = ("pending", "disputed", "withdrawn")
        for index, status in enumerate(hidden_statuses):
            item = dict(package["items"][0])
            item.update(
                id=f"hidden-{index}",
                name=f"不应显示-{status}",
                status=status,
                patient_text=f"危险推荐-{status}",
            )
            package["items"].append(item)

        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        for path in output.glob("*.md"):
            rendered = path.read_text(encoding="utf-8")
            self.assertNotIn("在标有“门诊入口 A”", rendered)
            self.assertNotIn("从入口 A 直行", rendered)
            self.assertNotIn("示例导诊台可协助", rendered)
            self.assertNotIn("危险推荐", rendered)
            self.assertIn("路线或服务信息暂不可用", rendered)
            self.assertIn("停止前进，查看预约单并在现场询问工作人员", rendered)

    def test_partial_item_only_exposes_confirmed_fields(self) -> None:
        result, output = self.run_build(valid_package())

        self.assertEqual(result.returncode, 0, result.stderr)
        for filename in ("index.md", "print.md"):
            path = output / filename
            rendered = path.read_text(encoding="utf-8")
            self.assertIn("示例导诊台可协助确认", rendered)
            self.assertIn("向工作人员说明预约单上的正式服务名称", rendered)
            self.assertNotIn("楼层待补充", rendered)

    def test_strict_build_rejects_missing_identity_safety_or_item_fields(self) -> None:
        cases = (
            ("campus_item_id", ("package", "campus_item_id")),
            ("safety_item_id", ("package", "safety_item_id")),
            ("reviewer", ("items", 0, "reviewer")),
        )
        for expected_field, path in cases:
            with self.subTest(field=expected_field):
                package = valid_package()
                target = package
                for key in path[:-1]:
                    target = target[key]
                del target[path[-1]]

                result, output = self.run_build(package)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_field, result.stderr)
                self.assertFalse(output.exists())

    def test_strict_build_rejects_nonfunctional_or_oversized_package(self) -> None:
        package = valid_package()
        package["items"] = package["items"][:4]
        result, _ = self.run_build(package)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("arrival_anchor", result.stderr)

        package = valid_package()
        for item in package["items"]:
            if item["type"] in {"arrival_anchor", "route_segment", "service_point"}:
                item["status"] = "pending"
        result, _ = self.run_build(package)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("arrival_anchor", result.stderr)

        package = valid_package()
        route = next(item for item in package["items"] if item["id"] == "route-01")
        route["patient_text"] = "很长的打印内容" * 700
        result, _ = self.run_build(package)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("print view exceeds one-page budget", result.stderr)

    def test_expiry_and_conditions_control_all_views(self) -> None:
        package = valid_package()
        route = next(item for item in package["items"] if item["id"] == "route-01")
        route["expires_on"] = "2026-08-04"

        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        for path in output.glob("*.md"):
            rendered = path.read_text(encoding="utf-8")
            self.assertNotIn("从入口 A 直行", rendered)
            self.assertIn("路线或服务信息暂不可用", rendered)

        package = valid_package()
        package["package"]["active_conditions"] = ["普通门诊"]
        result, output = self.run_build(package)
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in output.glob("*.md"):
            self.assertNotIn(
                "在标有“门诊入口 A”",
                path.read_text(encoding="utf-8"),
            )

    def test_quick_view_only_contains_current_stage_and_required_condition(self) -> None:
        result, output = self.run_build(valid_package())

        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "quick.md").read_text(encoding="utf-8")
        self.assertIn("当前阶段：** 到院", rendered)
        self.assertIn("必要条件：** 普通门诊、日间", rendered)
        self.assertIn("在标有“门诊入口 A”", rendered)
        self.assertNotIn("从入口 A 直行", rendered)

    def test_ticket02_arrival_plans_are_ranked_and_driver_safe(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "quick.md").read_text(encoding="utf-8")
        headings = [
            "### 1. 公共交通到院",
            "### 2. 即停即走下客",
            "### 3. 驾车并预约停车",
            "### 4. 停车满位分流",
        ]
        positions = [rendered.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("不适用于独自到院、无法独立下车或需要司机持续陪护者", rendered)
        self.assertIn("余位、预约、收费、道路管制和当天入口状态不在本页静态承诺", rendered)
        self.assertIn("驾驶员不要滚动阅读或操作实时查询", rendered)

    def test_ticket02_route_and_service_point_keep_fact_boundaries(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "index.md").read_text(encoding="utf-8")
        self.assertIn("**起点标志：** 示例门诊入口 A 标牌", rendered)
        self.assertIn("**沿途标志：** 入口内侧示例总索引", rendered)
        self.assertIn("**路线类型：** 普通步行路线（不与其他路线互相推断）", rendered)
        self.assertIn("普通门诊导诊：示例导诊服务点", rendered)
        self.assertIn("安心示例医院·中心院区 · 示例门诊楼 · 待确认 · 待确认", rendered)

        route = next(item for item in package["items"] if item["id"] == "route-segment-01")
        route["status"] = "disputed"
        result, output = self.run_build(package)
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "index.md").read_text(encoding="utf-8")
        self.assertNotIn("从蓝色圆形标志左转", rendered)
        self.assertNotIn("示例导诊服务点可协助", rendered)
        self.assertIn("上游事实未达到可发布状态", rendered)

    def test_ticket03_renders_shared_journey_and_only_explicitly_selected_branch(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "index.md").read_text(encoding="utf-8")
        journey_actions = [
            "核对院区、日期、时段和预约单上的正式服务名称",
            "从已核验方案中选择适合本次情况的到院方式",
            "在预约单对应的报到点完成报到并候诊",
            "按预约单上的完整检查项目名称打开检查卡",
            "按本次结算结果完成缴费、取药或查看报告领取安排",
            "按医嘱返回医生处；无需返回时再离院",
        ]
        positions = [rendered.index(action) for action in journey_actions]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("当前分支：** 妇科门诊", rendered)
        self.assertIn(
            "用户依据：** 预约单、医嘱或院方正式服务名称手动选择",
            rendered,
        )
        self.assertIn("妇科门诊完成检查后", rendered)
        self.assertNotIn("产科门诊报到后", rendered)
        self.assertNotIn("儿科门诊报到后", rendered)
        self.assertIn("不根据年龄、性别、症状或健康数据自动推断", rendered)
        self.assertIn("本次显示不会保存患者身份、预约内容或检查结果", rendered)
        quick = (output / "quick.md").read_text(encoding="utf-8")
        self.assertNotIn("妇科门诊完成检查后", quick)

        branch = next(
            item for item in package["items"] if item["id"] == "journey-branch-gyn-01"
        )
        branch["status"] = "partial"
        branch["confirmed_fields"] = [
            "name", "stage", "conditions", "patient_text"
        ]
        result, output = self.run_build(package)
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "index.md").read_text(encoding="utf-8")
        self.assertIn("分支资料暂不可用，继续使用共享核心旅程", rendered)
        self.assertIn("查看预约单、联系检查科室或询问工作人员", rendered)

    def test_ticket03_examination_card_separates_evidence_and_safety_boundaries(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "index.md").read_text(encoding="utf-8")
        self.assertIn("检查大类仅用于查找", rendered)
        self.assertIn("进入卡片前核对完整检查项目名称", rendered)
        self.assertIn("完整检查项目名称：** 示例经腹部妇科超声检查", rendered)
        self.assertIn("## 出发前", rendered)
        self.assertIn("## 到院后", rendered)
        self.assertIn("## 完成后", rendered)
        self.assertIn("### 本次或本院安排", rendered)
        self.assertIn("### 通用安全提醒", rendered)
        self.assertIn("### 尚待确认", rendered)
        self.assertIn("饮水量和憋尿程度须以本次预约单为准", rendered)
        self.assertIn("不指导停药、剂量调整、镇静、增强或造影风险处置", rendered)
        self.assertIn("不解读检查报告", rendered)

        card = next(item for item in package["items"] if item["type"] == "examination_card")
        card["hospital_arrangements"]["before_departure"] = [{
            "text": "来源 A 要求空腹，来源 B 允许进食。",
            "supported_by": "conflicting_sources",
        }]
        result, _ = self.run_build(package)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported or conflicting arrangement", result.stderr)

        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        package["package"]["selected_exam_item_id"] = "missing-exam"
        result, _ = self.run_build(package)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("selected_exam_item_id", result.stderr)

        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        card = next(item for item in package["items"] if item["type"] == "examination_card")
        card["status"] = "disputed"
        result, output = self.run_build(package)
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "index.md").read_text(encoding="utf-8")
        self.assertIn("所选检查卡资料暂不可用", rendered)
        self.assertIn("查看预约单并联系检查科室", rendered)

    def test_ticket04_generates_actionable_collection_workflow(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )

        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "operations.md").read_text(encoding="utf-8")
        self.assertIn("## 逐项资料缺口", rendered)
        self.assertIn("责任人：** 示例现场采集者", rendered)
        self.assertIn("明确不采集：** 患者身份、病历、预约内容和检查结果", rendered)
        for target in (
            "公共交通出口",
            "下客点",
            "院内停车人行出口",
            "备用停车场",
            "门诊入口",
            "通用服务点",
            "独立无障碍路线",
        ):
            self.assertIn(target, rendered)
        for evidence_kind in ("官方资料", "电话或工作人员确认", "现场标识照片", "路线走测"):
            self.assertIn(evidence_kind, rendered)
        self.assertIn("起点行动节点：** 示例门诊入口 A", rendered)
        self.assertIn("采集日期时间：** 2026-08-01 09:30 +08:00", rendered)
        self.assertIn("照片隐私检查：** 不含患者、人脸、证件、屏幕或车牌", rendered)

    def test_ticket04_enforces_review_cycles_and_safe_correction_flow(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )

        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (output / "operations.md").read_text(encoding="utf-8")
        self.assertIn("30 天", rendered)
        self.assertIn("90 天", rendered)
        self.assertIn("180 天", rendered)
        self.assertIn("公告", rendered)
        self.assertIn("改造", rendered)
        self.assertIn("来源冲突", rendered)
        self.assertIn("患者端只保留现场确认动作", rendered)
        self.assertIn("用户反馈只创建待核验线索，不直接修改正文", rendered)
        self.assertIn("安全级问题立即隐藏信息项及全部派生内容", rendered)
        for field in ("变更前", "变更后", "操作者", "时间", "原因", "证据", "复核结果", "受影响内容"):
            self.assertIn(field, rendered)

        broken = json.loads(json.dumps(package))
        broken["operations"]["review_cycles"].pop("high_risk_days")
        result, output = self.run_build(broken)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("high_risk_days", result.stderr)
        self.assertFalse(output.exists())

        swapped = json.loads(json.dumps(package))
        swapped["operations"]["review_cycles"]["high_risk_days"] = 90
        swapped["operations"]["review_cycles"]["route_days"] = 30
        result, _ = self.run_build(swapped)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("high_risk_days must be 30", result.stderr)

    def test_ticket04_events_enforce_quarantine_and_emergency_propagation(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        package["operations"]["events"] = [{
            "id": "event-conflict-01",
            "type": "source_conflict",
            "affected_item_ids": ["route-segment-01"],
            "owner": "示例复核负责人",
            "occurred_at": "2026-08-05T10:00:00+08:00",
            "next_action": "隔离路线并重测",
        }]

        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        for filename in ("index.md", "quick.md", "print.md"):
            rendered = (output / filename).read_text(encoding="utf-8")
            self.assertNotIn("从蓝色圆形标志左转", rendered)
            self.assertNotIn("示例导诊服务点可协助", rendered)
            self.assertIn("询问工作人员", rendered)

        package["operations"]["events"][0]["type"] = "safety"
        result, output = self.run_build(package)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "从蓝色圆形标志左转",
            (output / "index.md").read_text(encoding="utf-8"),
        )

    def test_ticket04_enforces_promotion_feedback_and_audit_records(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        package["operations"]["promotion_reviews"].pop("route-segment-01")
        result, _ = self.run_build(package)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("promotion review", result.stderr)

        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        package["operations"]["feedback_clues"][0]["patient_name"] = "不应收集"
        result, _ = self.run_build(package)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden feedback field", result.stderr)

        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        package["operations"]["audit_records"][0].pop("affected_routes")
        result, _ = self.run_build(package)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("affected_routes", result.stderr)

    def test_ticket05_derives_schematic_qr_and_dated_print_view(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )

        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        schematic = (output / "schematic.md").read_text(encoding="utf-8")
        self.assertIn("限定起点：** 示例门诊入口 A 标牌", schematic)
        self.assertIn("限定终点：** 蓝色圆形标志", schematic)
        self.assertIn("覆盖区域：** 示例门诊入口 A 至蓝色圆形标志", schematic)
        self.assertIn("路线断点：** 蓝色圆形标志之后不在本图覆盖范围", schematic)
        self.assertIn("文字等价说明", schematic)
        qr_targets = (output / "qr.md").read_text(encoding="utf-8")
        self.assertIn("目标名称：** 示例院区手机完整指南", qr_targets)
        self.assertIn("适用院区：** 安心示例医院·中心院区（虚构）", qr_targets)
        self.assertIn("短链接：** https://medical-guide.pages.dev/g/example", qr_targets)
        self.assertIn("扫码失败：** 手动输入短链接", qr_targets)
        self.assertNotIn("patient_name", qr_targets)
        qr_svg = (output / "qr-guide-example.svg").read_text(encoding="utf-8")
        self.assertIn("<svg", qr_svg)
        self.assertIn("<path", qr_svg)
        printed = (output / "print.md").read_text(encoding="utf-8")
        self.assertIn("生成日期：** 2026-08-05", printed)
        self.assertIn("资料核验日期：** 2026-08-01", printed)
        self.assertIn("过期提示：** 超过资料有效期或现场不一致时停止使用", printed)
        self.assertIn("在线复核：** https://medical-guide.pages.dev/g/example", printed)
        self.assertIn("官方兜底：** 查看预约单并询问院内工作人员", printed)

    def test_ticket05_all_derived_patient_outputs_degrade_together(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        package["operations"]["events"] = [{
            "id": "event-safety-05",
            "type": "safety",
            "affected_item_ids": ["route-segment-01"],
            "owner": "示例发布负责人",
            "occurred_at": "2026-08-05T10:00:00+08:00",
            "next_action": "紧急下架并重测",
        }]

        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        for filename in ("index.md", "quick.md", "print.md", "schematic.md", "qr.md"):
            rendered = (output / filename).read_text(encoding="utf-8")
            self.assertNotIn("从蓝色圆形标志左转", rendered)
        self.assertIn("局部示意图暂不可用", (output / "schematic.md").read_text(encoding="utf-8"))
        self.assertIn("目标已紧急下架", (output / "qr.md").read_text(encoding="utf-8"))
        self.assertFalse((output / "qr-guide-example.svg").exists())

        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )
        package["operations"]["events"] = [{
            "id": "event-announcement-05",
            "type": "announcement",
            "affected_item_ids": ["route-segment-01"],
            "owner": "示例发布负责人",
            "occurred_at": "2026-08-05T11:00:00+08:00",
            "next_action": "公告触发重新核验",
        }]
        result, output = self.run_build(package)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "局部示意图暂不可用",
            (output / "schematic.md").read_text(encoding="utf-8"),
        )

    def test_ticket05_enforces_two_release_gates_and_privacy(self) -> None:
        package = json.loads(
            (ROOT / "content" / "example-guide-package.json").read_text(encoding="utf-8")
        )

        result, output = self.run_build(package)

        self.assertEqual(result.returncode, 0, result.stderr)
        release = (output / "release.md").read_text(encoding="utf-8")
        self.assertIn("规范交付就绪：** 通过", release)
        self.assertIn("指南发布就绪：** 通过（仅限虚构示例）", release)
        self.assertIn("5 名未参与编辑的代表性测试者", release)
        for task in ("公共交通到院", "停车满位切换", "寻找服务点", "核对检查项目", "报告领取或离院"):
            self.assertIn(task, release)
        for phase in ("编辑草稿", "证据与风险复核", "内部预览", "小范围现场试运行", "严重问题修正", "正式公开"):
            self.assertIn(phase, release)
        self.assertIn("维护责任", release)
        self.assertIn("紧急下架及恢复责任", release)

        broken = json.loads(json.dumps(package))
        broken["release"]["representative_tests"]["tester_count"] = 4
        result, output = self.run_build(broken)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least 5 representative testers", result.stderr)
        self.assertFalse(output.exists())

        private = json.loads(json.dumps(package))
        private["release"]["qr_targets"][0]["url"] += "?appointment=secret"
        result, _ = self.run_build(private)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden private data", result.stderr)

        disconnected = json.loads(json.dumps(package))
        disconnected_route = next(
            item for item in disconnected["items"] if item["id"] == "route-segment-02"
        )
        disconnected_route["start_landmark"] = "不连续起点"
        result, _ = self.run_build(disconnected)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("end-to-end route", result.stderr)


if __name__ == "__main__":
    unittest.main()
