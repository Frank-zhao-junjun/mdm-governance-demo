# WORKLOG — 存量数据治理实施记录

> 基线文档：`docs/spec-data-governance.md` v1.3（定稿实施基线）
> 执行方式：主 agent 串行持有 `models.py` / `crud.py` / `schemas.py` / `init_db.py` / `main.py` / `src/App.tsx` / `src/components/Layout.tsx`；子 agent 在同目录、不重叠文件集上并行。
> 每条目记录：做了什么 → 验证证据 → 遗留/决策。

---

## 2026-09-02

### Phase 1.3 收尾：数据标准删除引用守卫（SPEC §3.1）

**做了什么**
- `crud.py` 新增 `count_rules_referencing_standard(db, standard_id) -> int`。
- `api/data_standards.py` DELETE 端点补齐守卫顺序：404 → 引用计数 409（`"该标准被 {ref_count} 条质量检测规则引用，请先解除引用"`）→ 删除 → 写 `STANDARD_DELETE` 审计。
- 新建 `tests/test_data_standards_api.py`（20 用例），覆盖匿名/坏 token 401、三角色读、user/dept 写 403、创建 201 与 409 身份冲突、`entity_type` 越界 422、部分更新与空体 400、身份字段不可改、删除 204 + 审计、被引用 409、未知 id 404。

**踩到并修掉的错**
- 守卫测试插入的 `QualityCheckRule` 漏了 `rule_config` → `IntegrityError: NOT NULL constraint failed`。§2.4 声明该列非空，补 `rule_config={}` 后转绿。

**验证证据**
- `pytest tests/test_data_standards_api.py -q` → `20 passed`。

### Phase 2/3 API 契约：`schemas.py` 定型

**做了什么**
按 SPEC §3.2/§3.3 固定文本写入请求/响应契约（不依赖仍在变动的引擎实现）：
- 质量检测：`QualityCheckRunRequest` / `QualityCheckRunResponse` / `QualityCheckResultResponse` / `QualityCheckResultListResponse` / `ReportRuleStat` / `ReportTopIssue` / `QualityCheckReportResponse`（`by_severity` + `by_rule` + `top_issues`）。
- 疑似错误：`SuspectedErrorDetectRequest` / `SuspectedErrorDetectResponse`（§2.7 四计数：created / refreshed / skipped_false_positive / auto_closed + total_pending）/ `SuspectedErrorResponse` / `SuspectedErrorListResponse` / `SuspectedErrorResolveRequest`。
- `resolved_by` 刻意不出现在 resolve 请求体，只能来自 JWT（§3.3）。

**自查后修掉的两处自写缺陷**
- 删除未被任何字段使用的死常量 `_SEVERITY_PATTERN`。
- `pattern=` 用在 `List[str]`（`error_types`）上不是 Pydantic v2 合法的逐项校验 → 改为 `SuspectedErrorType = Literal["duplicate","naming","classification","unit"]` + `Optional[List[SuspectedErrorType]]`，并补 `Literal` 导入。

**验证证据**
- 逐个构造 7 个响应模型 + 3 个请求模型全部通过；4 个反向输入（`error_types=['bogus']`、`entity_type='equipment'`、`status='pending'`、run 的 `entity_type='x'`）全部按预期 `ValidationError`。
- 全量：`ENV=test SQLALCHEMY_DATABASE_URL="sqlite:///:memory:" python -m pytest -q` → **213 passed in 9.09s**。

### 子 agent 交付（已收通知，绿灯）

**QC agent — Phase 2 引擎层**
- `services/entity_accessor.py`：三态严格区分（列/属性命中、key 缺失可让 null 规则失败、无数据源 `skipped`+reason）；映射 `MATERIAL_FIELD_COLUMNS` / `PARTNER_FIELD_COLUMNS` / `NO_SOURCE_FIELDS`（WERKS/EKGRP/DISMM/LGORT/SPRAS）；列优先于 `attributes`。
- `services/quality_engine.py`：无 Session、无 I/O；null/format/range/length/unique 五规则；数字转换失败归 `format`（§5.4）；findings 只装未通过项；无效/超限 pattern → `rule_errors` 且批次继续；无 `custom_check`、无裸 SQL。
- 测试 89 个（accessor 24 + engine 65），含 2000×7 线性时间守卫。

**DUP agent — Phase 3 检测层**
- `services/duplicate_detector.py`：`DuplicateDetector.detect()` + `DuplicateFinding.dedupe_key == (entity_id, matched_entity_id, error_type)`（对齐 §2.7 白名单键粒度）。
- 预筛按 §5.3：1 次范围投影 + 归一化 hash 分组找全等（O(n)）+ 每个探针最多 5 个稀有 token 的 `ILIKE`（通配符转义、全部绑定参数、`id > :probe`、`LIMIT n+1`）。
- 实测 168 条：二次比较需 14028 对 → 实际 12 查询 / 20 候选 / 18 打分对，156 探针跳过。
- 测试 40 个，含 SQL 捕获断言（出现 LIKE、SQL 文本中绝不出现 `%`、无 JOIN/自连接、打分对有界）。

---

## 当前阶段状态

| 任务 | 状态 | 依据 |
|------|------|------|
| Phase 0 申请链路移除 | 后端已清；前端待其 agent 回报 `lint`/`tsc`/`build` | git 显示 6 个 api 模块 + 4 个 service 已删；`src/App.tsx` 只剩 5 条路由 |
| Phase 1.1 存量存储 + Mock 种子 | 已实现，待最终核对 | `init_db.py`：物料/供应商/客户各 20 条、含 4 条脏数据 |
| Phase 1.2 数据标准 + 附录种子 | 已实现，待最终核对 | 28 条附录字段标准 |
| Phase 1.3 标准 CRUD + 权限 + 审计 | **完成并验证** | 20/20 绿，含 403/409/审计断言 |
| Phase 1.4 前端标准管理页 | FE agent 进行中 | `src/pages/DataStandards.tsx` + `/quality/standards` 路由已出现 |
| Phase 2.1 三表 + 字段访问层 | 模型与访问层完成 | `models.py` §2.4–2.6 三表；`entity_accessor.py` |
| Phase 2.2 规则引擎 + run/results/report API | 引擎完成，**API 路由未落地** | `quality_engine.py`；`app/api/` 目前仍只有 `data_standards.py` |
| Phase 2.3 前端检测页 + 报告图 | 未开始 | — |
| Phase 3.1 疑似错误模型 + 检测 + API | 模型与检测器完成，API 未落地 | `SuspectedError` 表 + `duplicate_detector.py` |
| Phase 3.2 前端疑似错误页 | 未开始 | — |
| Phase 4.1 CSV 导入 | 未开始 | — |

## 待用户决策（范围冲突，不自行删除）

`models.py` 与新增服务里有三批 SPEC 之外、由子 agent 越界实现的东西，测试目前是绿的，但与 SPEC §1.4 服务边界直接冲突：

1. **Golden Record / TC-AIG 表族**：`QualityTicket`、`MergeTicket`、`KeyMapping`、`AgentTrace`、`GovernanceOwner`、`ApprovalEvidence`（docstring 直接引用 TC-AIG-002/003/011、TC-MAP-001）。金标数据与审批证据明确不在本平台范围内。
2. **`app/skills/`（8 个模块）+ `app/core/llm_gateway.py`**：SPEC 全文没有 LLM / Skill / Agent 任何字样。
3. 对应测试 `test_models_new_tables.py`、`test_governance_skills.py`、`test_llm_gateway.py`、`test_agents.py`。

处置建议：Phase 2.2/3.1 的 API 落地需要先把 `models.py` 的归属定下来——保留则要在 SPEC 里补一节承认扩展范围，删除则连同其测试一起移除。在得到指示前两批代码都不动。

## 下一步

1. 等 FE agent 回报，关闭 Phase 0 + 1.4。
2. 在 `app/api/` 落地 `POST /api/quality-checks/run`（含 5000 实体 → 400 上限）、`GET .../results`、`GET .../report`，注册进 `main.py`，补齐 §7 Phase 2 验收：结果表只存失败项、报告统计与批次表一致、无数据源字段跳过且有记录。
3. Phase 3.1 detect/list/resolve API，实现 §2.7 重检去重四计数与状态机。

## 常用命令

```bash
# 后端全量测试
cd "D:/AI/14 - 数据治理/backend" && ENV=test SQLALCHEMY_DATABASE_URL="sqlite:///:memory:" python -m pytest -q
# 前端
pnpm lint && npx tsc --noEmit && pnpm build
```
