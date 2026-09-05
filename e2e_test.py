#!/usr/bin/env python3
"""存量数据治理 — E2E 端到端验收脚本（对齐 docs/spec-data-governance.md v1.3 §7 验收清单）

前置条件
    1. 后端已在 :8000 运行： cd backend && python -m uvicorn app.main:app --port 8000
    2. 数据库已初始化：     cd backend && python init_db.py

用法
    python e2e_test.py                                   # 默认 http://localhost:8000
    E2E_BASE_URL=http://127.0.0.1:8000 python e2e_test.py

覆盖范围（SPEC §7 各 Phase 的 **验收** 条目中可经 HTTP 观测的部分）
    Phase 1  三实体标准可增删改查；user/dept 角色写操作 403
    Phase 2  规则类型限于 SPEC 五种；结果表只存失败项；报告统计与批次一致；
             无数据源字段跳过且有记录；实体数越界返回 400
    Phase 3  检测出真重复；重跑不产生重复 pending；状态流转；越权 403
    Phase 4  CSV 导入成功；格式错误行返回明细报告；非 CSV / 越权被拒

不覆盖（无 HTTP 观测面，由 backend/tests/ 的 pytest 覆盖）
    - 审计记录写入（Phase 1/3 验收）：审计表无查询端点
    - 「Mock 数据入库」：存量记录无列表端点
    - 5,000 实体上限的实际触发：需要 >5,000 条存量，默认种子只有 22/20/20 条

副作用
    脚本会写入开发库：新建并删除 1 条数据标准、产生质量检测批次、导入 3 行供应商。
    供应商名称带本次运行标记，重复执行安全。
"""
import json
import os
import sys
import time

import requests

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 30

PASSED = 0
FAILED = 0
NOTES = []

# 本次运行标记：让导入的供应商名称唯一，从而「首次检测必然 created >= 1」可被断言
RUN_TAG = time.strftime("%m%d%H%M%S")
PARTNER_A = "9" + str(int(time.time()) % 10**9).zfill(9)
PARTNER_B = str(int(PARTNER_A) + 1)
DUP_NAME = f"端到端验收重复供应商 {RUN_TAG}"

TOKENS = {}


# --------------------------------------------------------------------------
# 基础设施
# --------------------------------------------------------------------------

def section(title):
    print(f"\n【{title}】")


def note(text):
    """记录一条不计入通过/失败的事实（绝不冒充通过）。"""
    NOTES.append(text)
    print(f"  ℹ️  {text}")


def login(user_id, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"user_id": user_id, "password": password},
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        print(f"  ❌ 登录失败 {user_id}: HTTP {r.status_code} {r.text[:200]}")
        print("\n后端未运行或未初始化？请先执行：")
        print("  cd backend && python init_db.py")
        print("  cd backend && python -m uvicorn app.main:app --port 8000")
        sys.exit(2)
    TOKENS[user_id] = r.json()["access_token"]
    print(f"  ✅ 已登录 {user_id}（{r.json()['user']['role']}）")


def auth(user_id):
    return {"Authorization": f"Bearer {TOKENS[user_id]}"}


def test(name, method, endpoint, *, expect=200, json_body=None,
         headers=None, files=None, data=None, check=None):
    """执行一次断言。check 收到已解析的 JSON，返回 False 即判失败。"""
    global PASSED, FAILED
    url = f"{BASE_URL}{endpoint}"
    # headers=None → 默认带 admin token；headers={} → 明确表示不带任何头（TC-002 依赖此区别）
    kwargs = {"timeout": TIMEOUT,
              "headers": auth("admin001") if headers is None else headers}
    if json_body is not None:
        kwargs["json"] = json_body
    if files is not None:
        kwargs["files"] = files
    if data is not None:
        kwargs["data"] = data

    try:
        r = requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        FAILED += 1
        print(f"  ❌ {name} — 连接失败: {exc}")
        return None

    ok = r.status_code == expect
    payload = None
    if ok and r.text:
        try:
            payload = r.json()
        except ValueError:
            payload = None
    if ok and check is not None and payload is not None:
        try:
            ok = bool(check(payload))
        except Exception as exc:  # check 自身写错不应伪装成被测系统的问题
            ok = False
            print(f"     check 异常: {type(exc).__name__}: {exc}")

    if ok:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name} — 期望 HTTP {expect}，实得 {r.status_code}: {r.text[:300]}")
    return payload


# --------------------------------------------------------------------------

print("=" * 72)
print("存量数据治理 — E2E 端到端验收")
print(f"目标服务: {BASE_URL}   运行标记: {RUN_TAG}")
print("=" * 72)

section("TS-00 认证与权限基线")
login("admin001", "adminpass001")   # admin      — 全部写操作
login("data001", "datapass001")     # data_admin — 全部写操作
login("user001", "password001")     # applicant  — 只读
login("dept001", "deptpass001")     # dept_approver — 只读

test("TC-000 服务根路径可达", "GET", "/", headers={},
     check=lambda d: "version" in d)
test("TC-001 /api/auth/me 返回当前用户", "GET", "/api/auth/me",
     check=lambda d: d.get("id") == "admin001" and d.get("role") == "admin")
test("TC-002 无 token 访问受保护端点 → 401", "GET", "/api/data-standards",
     headers={}, expect=401)
test("TC-003 伪造 token → 401", "GET", "/api/data-standards",
     headers={"Authorization": "Bearer not-a-real-token"}, expect=401)

# ===== Phase 1：数据标准管理 =====
section("TS-01 数据标准管理（Phase 1 验收）")

test("TC-010 三实体标准均可读取", "GET", "/api/data-standards?limit=500",
     check=lambda d: d["total"] > 0 and len(d["items"]) > 0)

for entity in ("material", "supplier", "customer"):
    test(f"TC-011 标准列表可按实体过滤：{entity}", "GET",
         f"/api/data-standards?entity_type={entity}&limit=500",
         check=lambda d, e=entity: d["total"] > 0
         and all(i["entity_type"] == e for i in d["items"]))

test("TC-012 非法 entity_type → 422", "GET",
     "/api/data-standards?entity_type=equipment", expect=422)

NEW_STANDARD = {
    "entity_type": "supplier",
    "sap_table": "LFA1",
    "field_name": f"ZE2E_{RUN_TAG}",
    "field_label": "端到端验收临时字段",
    "data_type": "string",
    "max_length": 20,
    "required": False,
    "unique": False,
    "standard_source": "internal",
    "description": "由 e2e_test.py 创建，本脚本内删除",
}

created = test("TC-013 admin 创建标准 → 201", "POST", "/api/data-standards",
               json_body=NEW_STANDARD, expect=201,
               check=lambda d: d["field_name"] == NEW_STANDARD["field_name"] and bool(d["id"]))

test("TC-014 同（实体, SAP表, 字段）重复创建 → 409", "POST", "/api/data-standards",
     json_body=NEW_STANDARD, expect=409)

test("TC-015 user 角色创建 → 403", "POST", "/api/data-standards",
     json_body={**NEW_STANDARD, "field_name": f"ZE2E_{RUN_TAG}_U"},
     headers=auth("user001"), expect=403)

test("TC-016 dept 角色创建 → 403", "POST", "/api/data-standards",
     json_body={**NEW_STANDARD, "field_name": f"ZE2E_{RUN_TAG}_D"},
     headers=auth("dept001"), expect=403)

test("TC-017 user 角色删除 → 403", "DELETE",
     f"/api/data-standards/{created['id'] if created else 'x'}",
     headers=auth("user001"), expect=403)

if created:
    test("TC-018 data_admin 部分更新 → 200", "PUT",
         f"/api/data-standards/{created['id']}",
         json_body={"field_label": "端到端验收临时字段（已改名）", "max_length": 40},
         headers=auth("data001"),
         check=lambda d: d["field_label"].endswith("（已改名）") and d["max_length"] == 40)

    # DataStandardUpdate 未声明身份键，Pydantic v2 默认忽略额外字段：
    # 身份键被静默丢弃（200，原值不变），只有当请求体仅剩身份键时才是 400。
    test("TC-019 身份字段被忽略且保持原值 → 200", "PUT",
         f"/api/data-standards/{created['id']}",
         json_body={"entity_type": "material", "sap_table": "MARA", "field_name": "HACKED",
                    "field_label": "端到端验收临时字段（已改名）"},
         check=lambda d: d["entity_type"] == "supplier"
         and d["sap_table"] == "LFA1"
         and d["field_name"] == NEW_STANDARD["field_name"])

    test("TC-019b 仅含身份字段的更新体 → 400", "PUT",
         f"/api/data-standards/{created['id']}",
         json_body={"entity_type": "material"}, expect=400)

    test("TC-020 空更新体 → 400", "PUT",
         f"/api/data-standards/{created['id']}", json_body={}, expect=400)

    test("TC-021 删除标准 → 204", "DELETE",
         f"/api/data-standards/{created['id']}", expect=204)

test("TC-022 删除不存在的标准 → 404", "DELETE",
     "/api/data-standards/00000000-0000-0000-0000-000000000000", expect=404)

# ===== Phase 2：数据质量检测 =====
section("TS-02 数据质量检测（Phase 2 验收）")

# models.RuleType 的取值带 _check 后缀；SPEC §2.4 的五种规则即这五个枚举，
# 且刻意没有 custom_check（可配置 SQL 即注入口子）。
SPEC_RULE_TYPES = {"null_check", "format_check", "range_check", "length_check", "unique_check"}

rules = test("TC-023 规则列表可读且类型限于 SPEC 五种", "GET",
             "/api/quality-checks/rules?entity_type=material&limit=500",
             check=lambda d: d["total"] > 0
             and set(i["rule_type"] for i in d["items"]) <= SPEC_RULE_TYPES)
if rules:
    note(f"material 规则 {rules['total']} 条，覆盖类型: "
         f"{sorted(set(i['rule_type'] for i in rules['items']))}")

# quality_engine 中 passed = total_checks - failed，skipped_checks 单独计数，
# 因此 total_checked == passed + failed，skipped 是「额外跳过」而非其中一部分。
run = test("TC-024 admin 执行物料质量检测 → 200", "POST", "/api/quality-checks/run",
           json_body={"entity_type": "material"},
           check=lambda d: bool(d.get("batch_id"))
           and d["total_checked"] == d["passed"] + d["failed"]
           and d["total_checked"] > 0
           and d["skipped"] >= 0)

if run:
    note(f"批次 {run['batch_id'][:8]}… 检查 {run['total_checked']} 项："
         f"通过 {run['passed']} / 失败 {run['failed']} / 跳过 {run['skipped']}")

    # 验收：无数据源字段跳过且有记录（种子里 MARC.WERKS 必填但无存量数据源）
    test("TC-025 无数据源字段被跳过且有记录（skipped > 0）", "POST",
         "/api/quality-checks/run", json_body={"entity_type": "material"},
         check=lambda d: d["skipped"] > 0)

    test("TC-026 批次列表包含刚执行的批次", "GET",
         "/api/quality-checks/batches?entity_type=material&limit=50",
         check=lambda d: any(i["id"] == run["batch_id"] for i in d["items"]))

    # 验收：结果表只存失败项
    results = test("TC-027 结果明细条数 == 批次失败数（只存失败项）", "GET",
                   f"/api/quality-checks/results?entity_type=material"
                   f"&batch_id={run['batch_id']}&limit=500",
                   check=lambda d: d["total"] == run["failed"])
    if results and results["items"]:
        test("TC-028 结果行字段完整且严重程度合法", "GET",
             f"/api/quality-checks/results?entity_type=material"
             f"&batch_id={run['batch_id']}&limit=500",
             check=lambda d: all(
                 i["batch_id"] == run["batch_id"]
                 and i["severity"] in ("error", "warning", "info")
                 and bool(i["rule_id"]) and bool(i["entity_id"])
                 for i in d["items"]))

    # 验收：报告统计与批次表一致
    test("TC-029 报告统计与批次一致", "GET",
         f"/api/quality-checks/report?entity_type=material&batch_id={run['batch_id']}",
         check=lambda d: d["batch_id"] == run["batch_id"]
         and d["total_checks"] == run["total_checked"]
         and d["passed"] == run["passed"]
         and d["failed"] == run["failed"]
         and sum(d["by_severity"].values()) == run["failed"]
         and set(d["by_severity"]) == {"error", "warning", "info"}
         and sum(s["failed"] for s in d["by_rule"]) == run["failed"])

    test("TC-030 报告含 by_rule 与 top_issues 结构", "GET",
         f"/api/quality-checks/report?entity_type=material&batch_id={run['batch_id']}",
         check=lambda d: len(d["by_rule"]) > 0
         and all({"rule_id", "rule_name", "total", "failed", "pass_rate"} <= set(s)
                 for s in d["by_rule"])
         and all({"field_name", "issue_count", "issue_type", "message"} <= set(t)
                 for t in d["top_issues"]))

test("TC-031 不存在的批次报告 → 404", "GET",
     "/api/quality-checks/report?entity_type=material"
     "&batch_id=00000000-0000-0000-0000-000000000000", expect=404)

test("TC-032 user 角色执行检测 → 403", "POST", "/api/quality-checks/run",
     json_body={"entity_type": "material"}, headers=auth("user001"), expect=403)

test("TC-033 指定 entity_ids 全部未命中 → 400", "POST", "/api/quality-checks/run",
     json_body={"entity_type": "material",
                "entity_ids": [f"NO-SUCH-{i}" for i in range(10)]}, expect=400)

test("TC-034 非法 entity_type 执行检测 → 422", "POST", "/api/quality-checks/run",
     json_body={"entity_type": "equipment"}, expect=422)

note("5,000 实体上限需要 >5,000 条存量才能经 HTTP 触发；默认种子为 22/20/20 条。"
     "该上限由 backend/tests/ 直接对 quality_runner 断言（EntityLimitExceeded → 400）。")

# ===== Phase 4：CSV 导入 =====
# 排在疑似错误之前：本脚本用导入造出一对同名供应商，让 Phase 3 的
# 「检测出真重复」成为可断言的确定性结果，而不依赖种子库的既有状态。
section("TS-03 存量数据 CSV 导入（Phase 4 验收）")

GOOD_CSV = (
    "partner_code,partner_name,CITY1,ZTERM\n"
    f"{PARTNER_A},{DUP_NAME},上海,0010\n"
    f"{PARTNER_B},{DUP_NAME},上海,0020\n"
)

imp = test("TC-035 导入供应商 CSV → 200 且全部创建", "POST", "/api/data-import/partners",
           files={"file": (f"suppliers_{RUN_TAG}.csv", GOOD_CSV.encode("utf-8"), "text/csv")},
           data={"entity_type": "supplier"},
           check=lambda d: d["total_rows"] == 2 and d["created"] == 2
           and d["updated"] == 0 and d["failed"] == 0 and d["errors"] == [])

test("TC-036 重复导入同编码 → upsert 计为 updated", "POST", "/api/data-import/partners",
     files={"file": (f"suppliers_{RUN_TAG}.csv", GOOD_CSV.encode("utf-8"), "text/csv")},
     data={"entity_type": "supplier"},
     check=lambda d: d["created"] == 0 and d["updated"] == 2 and d["failed"] == 0)

BAD_CSV = (
    "partner_code,partner_name,CITY1\n"
    f"9{RUN_TAG}01,验收合格供应商甲,苏州\n"
    ",缺少编码的供应商,杭州\n"
    f"9{RUN_TAG}02,{'超' * 300},南京\n"
)

test("TC-037 格式错误行返回明细报告且不影响合法行", "POST", "/api/data-import/partners",
     files={"file": (f"mixed_{RUN_TAG}.csv", BAD_CSV.encode("utf-8"), "text/csv")},
     data={"entity_type": "supplier"},
     check=lambda d: d["total_rows"] == 3 and d["created"] == 1 and d["failed"] == 2
     and d["created"] + d["updated"] + d["failed"] == d["total_rows"]
     and len(d["errors"]) >= 2
     and all({"row", "field", "message"} <= set(e) for e in d["errors"])
     and all(isinstance(e["row"], int) and e["row"] >= 1 for e in d["errors"]))

test("TC-038 非 CSV 扩展名 → 400", "POST", "/api/data-import/partners",
     files={"file": ("evil.html", b"<script>alert(1)</script>", "text/html")},
     data={"entity_type": "supplier"}, expect=400)

test("TC-039 伪装成 .csv 的可执行 MIME → 400", "POST", "/api/data-import/partners",
     files={"file": ("x.csv", b"<svg onload=alert(1)>", "image/svg+xml")},
     data={"entity_type": "supplier"}, expect=400)

test("TC-040 空文件 → 400", "POST", "/api/data-import/partners",
     files={"file": ("empty.csv", b"", "text/csv")},
     data={"entity_type": "supplier"}, expect=400)

test("TC-041 缺少必需列 → 400", "POST", "/api/data-import/partners",
     files={"file": ("nocol.csv", "city,name\n上海,甲\n".encode("utf-8"), "text/csv")},
     data={"entity_type": "supplier"}, expect=400)

test("TC-042 非法 entity_type → 422", "POST", "/api/data-import/partners",
     files={"file": ("s.csv", GOOD_CSV.encode("utf-8"), "text/csv")},
     data={"entity_type": "equipment"}, expect=422)

test("TC-043 user 角色导入 → 403", "POST", "/api/data-import/partners",
     files={"file": ("s.csv", GOOD_CSV.encode("utf-8"), "text/csv")},
     data={"entity_type": "supplier"}, headers=auth("user001"), expect=403)

test("TC-044 导入 customer 不与 supplier 串档", "POST", "/api/data-import/partners",
     files={"file": (f"customers_{RUN_TAG}.csv",
                     f"partner_code,partner_name,CITY1\n{PARTNER_A},验收客户甲,北京\n"
                     .encode("utf-8"), "text/csv")},
     data={"entity_type": "customer"},
     check=lambda d: d["entity_type"] == "customer" and d["created"] == 1)

# ===== Phase 3：疑似错误检测 =====
section("TS-04 疑似错误检测与处理（Phase 3 验收）")

det = test("TC-045 admin 执行供应商疑似错误检测 → 200", "POST",
           "/api/suspected-errors/detect", json_body={"entity_type": "supplier"},
           check=lambda d: {"created", "refreshed", "skipped_false_positive",
                            "auto_closed", "total_pending"} <= set(d)
           and all(isinstance(d[k], int) for k in
                   ("created", "refreshed", "skipped_false_positive",
                    "auto_closed", "total_pending")))
if det:
    note(f"检测计数 created={det['created']} refreshed={det['refreshed']} "
         f"skipped_false_positive={det['skipped_false_positive']} "
         f"auto_closed={det['auto_closed']} total_pending={det['total_pending']}")

# 验收：检测出真重复（TC-035 刚导入的同名供应商对必然产生新工单）
test("TC-046 检测出 TS-03 造出的真重复（created >= 1）", "POST",
     "/api/suspected-errors/detect", json_body={"entity_type": "supplier"},
     check=lambda d: d["created"] + d["refreshed"] >= 1)

# 验收：重跑不产生重复 pending
test("TC-047 立即重跑不产生新的重复 pending（created == 0）", "POST",
     "/api/suspected-errors/detect", json_body={"entity_type": "supplier"},
     check=lambda d: d["created"] == 0)

test("TC-048 只检测指定类型 naming", "POST", "/api/suspected-errors/detect",
     json_body={"entity_type": "supplier", "error_types": ["naming"]},
     check=lambda d: isinstance(d["total_pending"], int))

test("TC-049 非法 error_types → 422", "POST", "/api/suspected-errors/detect",
     json_body={"entity_type": "supplier", "error_types": ["bogus"]}, expect=422)

test("TC-050 user 角色执行检测 → 403", "POST", "/api/suspected-errors/detect",
     json_body={"entity_type": "supplier"}, headers=auth("user001"), expect=403)

pending = test("TC-051 pending 列表可读且状态一致", "GET",
               "/api/suspected-errors/?entity_type=supplier&status=pending&limit=500",
               check=lambda d: all(i["status"] == "pending" for i in d["items"]))

target = None
if pending:
    for item in pending["items"]:
        blob = json.dumps(item, ensure_ascii=False, default=str)
        if RUN_TAG in blob or DUP_NAME in blob:
            target = item
            break
    note(f"pending 共 {pending['total']} 条；"
         f"{'已定位本次运行造出的重复对' if target else '未定位到本次运行的重复对（跳过处理断言）'}")

if target:
    test("TC-052 处理为 confirmed → 状态流转且 resolved_by 来自 JWT", "POST",
         f"/api/suspected-errors/{target['id']}/resolve",
         json_body={"status": "confirmed", "resolution_note": f"端到端验收 {RUN_TAG}"},
         check=lambda d: d["id"] == target["id"] and d["status"] == "confirmed"
         and d["resolved_by"] == "admin001" and d["resolved_at"] is not None)

    test("TC-053 已处理项不再出现在 pending 列表", "GET",
         "/api/suspected-errors/?entity_type=supplier&status=pending&limit=500",
         check=lambda d: all(i["id"] != target["id"] for i in d["items"]))

    test("TC-054 可按 confirmed 状态过滤到该项", "GET",
         "/api/suspected-errors/?entity_type=supplier&status=confirmed&limit=500",
         check=lambda d: any(i["id"] == target["id"] for i in d["items"]))

    test("TC-055 请求体不能伪造 resolved_by", "POST",
         f"/api/suspected-errors/{target['id']}/resolve",
         json_body={"status": "false_positive", "resolved_by": "user001"},
         check=lambda d: d["resolved_by"] == "admin001")

test("TC-056 非法目标状态 → 422", "POST",
     "/api/suspected-errors/00000000-0000-0000-0000-000000000000/resolve",
     json_body={"status": "pending"}, expect=422)

test("TC-057 处理不存在的疑似错误 → 404", "POST",
     "/api/suspected-errors/00000000-0000-0000-0000-000000000000/resolve",
     json_body={"status": "confirmed"}, expect=404)

test("TC-058 user 角色处理 → 403", "POST",
     "/api/suspected-errors/00000000-0000-0000-0000-000000000000/resolve",
     json_body={"status": "confirmed"}, headers=auth("user001"), expect=403)

# ===== 汇总 =====
print("\n" + "=" * 72)
print(f"测试结果: {PASSED} 通过, {FAILED} 失败, 总计 {PASSED + FAILED}")
if NOTES:
    print(f"另记 {len(NOTES)} 条不计入判定的观测说明")
print("=" * 72)

if FAILED:
    sys.exit(1)
print("✅ 所有 E2E 验收项通过")
sys.exit(0)
