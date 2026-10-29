import io

from openpyxl import Workbook

from tests.conftest import auth


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_login_rejects_wrong_password(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@ivi-test.com", "password": "wrong-pass"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_role(client, admin_token):
    r = client.get("/api/v1/auth/me", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_viewer_cannot_write(client, viewer_token):
    """只读访客：演示账号能看不能改，这条是权限模型的核心断言。"""
    assert client.get("/api/v1/cases", headers=auth(viewer_token)).status_code == 200
    r = client.post(
        "/api/v1/modules",
        headers=auth(viewer_token),
        json={"code": "XXX", "name": "不该建出来"},
    )
    assert r.status_code == 403


def test_module_and_case_crud(client, admin_token):
    mods = client.get("/api/v1/modules", headers=auth(admin_token)).json()
    voice = next(m for m in mods if m["code"] == "VOICE")

    payload = {
        "code": "VOICE-900",
        "title": "新建用例：唤醒后立刻说取消",
        "module_id": voice["id"],
        "priority": "P1",
        "case_type": "function",
        "precondition": "语音助手已激活",
        "steps": [{"no": 1, "action": "说“你好小牛”", "expected": "进入聆听态"}],
        "expected": "可取消当前会话",
        "tags": ["边界"],
        "status": "active",
    }
    created = client.post("/api/v1/cases", headers=auth(admin_token), json=payload)
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    dup = client.post("/api/v1/cases", headers=auth(admin_token), json=payload)
    assert dup.status_code == 409

    patched = client.patch(
        f"/api/v1/cases/{case_id}", headers=auth(admin_token), json={"priority": "P0"}
    )
    assert patched.json()["priority"] == "P0"

    deprecated = client.delete(f"/api/v1/cases/{case_id}", headers=auth(admin_token))
    assert deprecated.json()["status"] == "deprecated"


def test_excel_import(client, admin_token):
    wb = Workbook()
    ws = wb.active
    ws.title = "用例"
    ws.append(
        [
            "用例编号", "用例标题", "模块编码", "优先级", "用例类型", "前置条件",
            "步骤1", "预期1", "步骤2", "预期2", "步骤3", "预期3",
            "预期结果", "标签", "状态", "备注",
        ]
    )
    ws.append(
        [
            "NAVI-900", "导入用例：导航中切换语音包", "NAVI", "P2", "function", "导航进行中",
            "进入设置切换语音包", "语音包切换生效", "继续导航", "播报使用新语音包", "", "",
            "播报音色与新语音包一致", "导入,验证", "active", "",
        ]
    )
    ws.append(["BAD-901", "模块编码不存在", "NOPE", "P2", "function", "", "", "", "", "", "", "", "", "", "active", ""])
    buf = io.BytesIO()
    wb.save(buf)

    r = client.post(
        "/api/v1/cases/import",
        headers=auth(admin_token),
        files={
            "file": (
                "cases.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1
    assert body["errors"][0]["row"] == 3

    found = client.get("/api/v1/cases", headers=auth(admin_token), params={"q": "NAVI-900"}).json()
    assert found["total"] == 1
    assert len(found["items"][0]["steps"]) == 2


def test_template_download(client, admin_token):
    r = client.get("/api/v1/cases/template", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # xlsx 就是 zip


def test_plan_execution_flow(client, admin_token, qa_token):
    cases = client.get("/api/v1/cases", headers=auth(admin_token), params={"size": 5}).json()["items"]
    plan = client.post(
        "/api/v1/plans",
        headers=auth(admin_token),
        json={
            "code": "R-TEST-001",
            "name": "单测批次",
            "fw_version": "9.9.9.9",
            "device_model": "D21x",
            "device_sn": "SN-TEST",
            "case_ids": [c["id"] for c in cases],
        },
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]
    assert plan.json()["stats"]["total"] == 5
    assert plan.json()["stats"]["not_run"] == 5

    target = cases[0]
    r = client.put(
        f"/api/v1/plans/{plan_id}/executions",
        headers=auth(qa_token),
        json={
            "case_id": target["id"],
            "status": "fail",
            "duration_s": 120,
            "actual_result": "点击无响应",
            "error_signature": (
                "java.lang.NullPointerException: asrText is null at "
                "AsrEngine.onResult(AsrEngine.java:137) 2026-10-29 12:00:00"
            ),
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["cluster_key"], "失败时必须算出聚类键"

    detail = client.get(f"/api/v1/plans/{plan_id}", headers=auth(admin_token)).json()
    assert detail["stats"]["failed"] == 1
    assert detail["stats"]["exec_rate"] == 20.0
    assert detail["status"] == "running"

    rows = client.get(f"/api/v1/plans/{plan_id}/executions", headers=auth(admin_token)).json()
    assert rows[0]["case_code"]


def test_seeded_regression_compare(client, admin_token):
    plans = client.get("/api/v1/plans", headers=auth(admin_token), params={"size": 50}).json()["items"]
    by_code = {p["code"]: p["id"] for p in plans}
    r = client.get(
        "/api/v1/reports/compare",
        headers=auth(admin_token),
        params={"base_plan_id": by_code["R2026.10-W1"], "target_plan_id": by_code["R2026.10-W3"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    codes = {c["case_code"] for c in body["new_fail"]}
    assert "NAVI-002" in codes
    assert {c["case_code"] for c in body["fixed"]} >= {"CLUSTER-003"}


def test_failure_clustering_merges_same_root_cause(client, admin_token):
    plans = client.get("/api/v1/plans", headers=auth(admin_token), params={"size": 50}).json()["items"]
    plan_id = next(p["id"] for p in plans if p["code"] == "R2026.10-W3")
    clusters = client.get("/api/v1/reports/clusters", headers=auth(admin_token), params={"plan_id": plan_id}).json()
    assert clusters, "应该有失败簇"
    top = clusters[0]
    assert top["count"] >= 2, "同一根因的多条失败必须聚成一簇"
    assert len(top["case_codes"]) == top["count"]


def test_dashboard_shape(client, admin_token):
    r = client.get("/api/v1/reports/dashboard", headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["total"] > 0
    assert body["by_module"] and body["by_priority"]
    assert body["trend"]


def test_automation_ingest_requires_token(client, admin_token):
    plan = client.get("/api/v1/plans", headers=auth(admin_token), params={"size": 50}).json()["items"][0]
    payload = {
        "plan_code": plan["code"],
        "script_name": "appium_smoke.py",
        "device_sn": "SN-TEST",
        "started_at": "2026-10-29T10:00:00Z",
        "results": [{"case_code": "POI-001", "status": "pass", "duration_s": 60}],
    }
    bad = client.post("/api/v1/automation/runs", json=payload, headers={"X-Automation-Token": "nope"})
    assert bad.status_code == 401

    ok = client.post("/api/v1/automation/runs", json=payload, headers={"X-Automation-Token": "test-token"})
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["accepted"] == 1

    runs = client.get("/api/v1/automation/runs", headers=auth(admin_token)).json()
    assert runs[0]["passed"] == 1


def test_automation_unknown_case_reported(client, admin_token):
    plan = client.get("/api/v1/plans", headers=auth(admin_token), params={"size": 50}).json()["items"][0]
    r = client.post(
        "/api/v1/automation/runs",
        headers={"X-Automation-Token": "test-token"},
        json={
            "plan_code": plan["code"],
            "script_name": "appium_smoke.py",
            "started_at": "2026-10-29T11:00:00Z",
            "results": [{"case_code": "NO-SUCH-001", "status": "fail"}],
        },
    )
    assert r.json()["unknown_cases"] == ["NO-SUCH-001"]


def test_stability_metrics(client, admin_token):
    runs = client.get("/api/v1/stability/runs", headers=auth(admin_token)).json()
    assert len(runs) >= 2
    worst = next(r for r in runs if r["fw_version"] == "1.3.0.0")
    best = next(r for r in runs if r["fw_version"] == "1.2.1.0")
    assert worst["metrics"]["mtbf_hours"] < best["metrics"]["mtbf_hours"], "1.3.0.0 的 MTBF 应更差"
    assert 0 <= worst["metrics"]["recovery_rate"] <= 100
    assert worst["by_type"]


def test_ai_generate_falls_back_without_key(client, admin_token):
    mods = client.get("/api/v1/modules", headers=auth(admin_token)).json()
    poi = next(m for m in mods if m["code"] == "POI")
    r = client.post(
        "/api/v1/ai/generate",
        headers=auth(admin_token),
        json={"module_id": poi["id"], "requirement": "弱网下搜索停车场应给出明确提示并可重试", "count": 3},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["fallback"] is True
    assert len(body["cases"]) == 3
    for case in body["cases"]:
        assert case["steps"] and case["title"]


def test_ai_draft_accept_creates_cases(client, admin_token):
    drafts = client.get("/api/v1/ai/drafts", headers=auth(admin_token)).json()
    draft = drafts[0]
    r = client.post(
        f"/api/v1/ai/drafts/{draft['id']}/accept",
        headers=auth(admin_token),
        json={"indices": [0, 1]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2
    assert all(code.startswith(("POI-", "VOICE-")) for code in body["case_codes"])

    again = client.post(f"/api/v1/ai/drafts/{draft['id']}/accept", headers=auth(admin_token), json={"indices": []})
    assert again.status_code == 400
