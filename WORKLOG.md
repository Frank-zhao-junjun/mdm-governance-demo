# WORKLOG — 存量数据治理实施记录

> 基线文档：`docs/spec-data-governance.md` v1.4（定稿实施基线，v1.4 起承认 AI 辅助治理层为正式范围）
> 执行方式：主 agent 串行持有 `models.py` / `crud.py` / `schemas.py` / `init_db.py` / `main.py` / `src/App.tsx` / `src/components/Layout.tsx`；子 agent 在同目录、不重叠文件集上并行。
> 每条目记录：做了什么 → 验证证据 → 遗留/决策。

---

## 2026-09-02

### SAP 知识库缺口补足评测

**做了什么**
- 根据 `Cases_知识库匹配评测_20260902.xlsx` 的 14 条缺口，新增 SAP 知识库补充包：`D:/03--SAP知识库/knowledge/_supplements/cases-knowledge-gap-supplement-20260902.md`。
- 补充包覆盖 Integration Suite Access Policies、PO→CPI 迁移、CPI/Cloud Identity Services 证书轮换、SF/IAS/EC Payroll、S/4HANA Public 中国汇票、IP Filter/SSRF、Adobe Forms 等主题，并区分已核实、推导、合同口径和待补采内容。
- 生成评测工作簿副本：`C:/Users/admin/Downloads/Cases_知识库匹配评测_20260902_知识库补足.xlsx`，仅更新“知识库匹配情况”列，未覆盖原始文件。

**验证证据**
- `xlsx_reader.py --json`：输出工作簿仍为 `Sheet1`、14 行、4 列，原问题和产品列保留。
- ZIP 完整性检查：`ZIP_TEST: PASS`。
- 本地官方证据核实：Access Policies 文档明确 package/artifact 级隔离；Cloud Identity Services 文档明确证书到期不可延长、支持提前轮换和 Automatic Regeneration。
- SAP Community 目标 URL 当前浏览器显示 `Page not found`，HTTP 抓取返回 403；补充包已明确标注未核实，未复制未验证正文。

**遗留/决策**
- Adobe Forms Service 实施级配置、IAS 开发 tenant 具体迁移 FAQ、SAP 公有云许可计费口径仍需后续从可访问官方来源、客户租户或合同资料补采。

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

### Phase 2.2 / 2.3：质量检测 API + 前端

**做了什么**
- `services/quality_runner.py`：批次编排（取规则 → 调 `entity_accessor` + `quality_engine` → 写 `QualityCheckBatch`/`QualityCheckResult`）。单次运行实体上限 `MAX_ENTITIES = 5_000`。
- `services/rule_derivation.py`：种子期从数据标准自动派生检测规则（`derive_rule_rows`），material 派生 15 条。
- `api/quality_checks.py`：`GET /rules`、`POST /run`、`GET /batches`、`GET /results`、`GET /report`，注册进 `main.py`。
- 前端 `src/pages/QualityChecks.tsx` + `QualityReport.tsx`，路由 `/quality/checks`、`/quality/checks/report`。

**踩到并修掉的错**
- 5,000 实体上限原先按「表内总量」判断，与 SPEC「单次运行上限」口径不符 → 改为按 `count_entities(db, entity_type, ids)` 的**命中数**判断（`quality_runner.run_batch`），超限抛 `EntityLimitExceeded` → API 400。

**验收要点（实测）**
- 结果表只存失败项：`GET /results` 的 `total` == 批次 `failed`（实测 6 == 6）。
- 无数据源字段跳过且有记录：material 运行 `skipped = 22`（MARC.WERKS 等 `NO_SOURCE_FIELDS`）。
- 计数口径：`quality_engine` 中 `passed = total_checks - failed`，`skipped_checks` 单独计数，因此线上契约是 **`total_checked == passed + failed`**，`skipped` 是额外跳过而非其中一部分（实测 308 = 302 + 6，另跳过 22）。

### Phase 3.1 / 3.2：疑似错误 API + 前端

**做了什么**
- `services/suspected_error_runner.py`：重检去重，按 §2.7 白名单键 `(entity_id, matched_entity_id, error_type)` 落 `created / refreshed / skipped_false_positive / auto_closed` 四计数。
- `api/suspected_errors.py`：`POST /detect`、`GET /`（按 status / error_type 过滤）、`POST /{id}/resolve`（状态机校验；`resolved_by` 只取 JWT，请求体不可伪造）。
- 前端 `src/pages/SuspectedErrors.tsx`，路由 `/quality/suspected`。

**验收要点（实测）**
- 检测出真重复：造同名供应商对 → `created = 3`；立即重跑 → `created = 0`（不产生重复 pending）。
- 状态流转 pending → confirmed，`resolved_by == "admin001"`；已处理项离开 pending 列表、可按 confirmed 过滤到。

### Phase 4.1：存量数据 CSV 导入

**做了什么**
- `services/csv_importer.py`：`MAX_ROWS = 5_000`；扩展名 + MIME 双重校验（拒绝 `.html`/`.svg`/伪装成 `.csv` 的可执行 MIME）；空文件、缺表头、缺必需列均 400；逐行错误明细报告，坏行不影响合法行；同编码重导入走 upsert 计 `updated`。
- `api/data_import.py`：`POST /api/data-import/{entity_type}`，写 `DATA_IMPORT` 审计。

**范围说明**
- 本系统是存量数据的**唯一写入口**（SPEC §1.4：上游系统负责创建与分发，本系统通过导入接收）。Phase 4 在 SPEC 中只列了接口，**没有导入 UI**，当前也确实没有。

### 端到端验收：`e2e_test.py` 重写

**发现的问题**
- 根目录 `e2e_test.py` 仍是旧申请/审批/金标链路的用例，打的端点已全部删除；且有两处 `⏭️ … PASSED += 1` 的「跳过即通过」在虚增计数。SPEC §7 Phase 0 第 4 条明确要求「更新 init_db、**e2e 脚本**与前端导航」，这一条此前没做。

**做了什么**
- 全量重写为 56 条断言，按 SPEC 五个 Phase 的 `**验收**：` 行组织：TS-00 认证 / TS-01 数据标准 / TS-02 质量检测 / TS-03 CSV 导入 / TS-04 疑似错误。
- TS-03 刻意排在 TS-04 之前：导入一对带运行时间戳的同名供应商，让「检测出真重复」成为可重复的确定性断言，而不是依赖上一次运行可能已改动的种子状态。
- 所有非断言观测改走 `note()`，不计入 PASSED；汇总单独报「另记 N 条不计入判定的观测说明」。

**首次实跑修掉的 3 个脚本自身缺陷（都不是应用缺陷）**
1. `test()` 里 `headers or auth("admin001")`：`headers={}` 是 falsy，被静默换成 admin token，TC-002「无 token → 401」永远不可能失败 → 改为 `headers is None` 判断。
2. `SPEC_RULE_TYPES` 写成裸名 `null/format/...`；`models.RuleType` 的取值带 `_check` 后缀 → 改为 `null_check` 等五值（且刻意无 `custom_check`：可配置 SQL 即注入口子）。
3. TC-024 断言 `total_checked == passed + failed + skipped`，与 `quality_engine` 的计数口径不符 → 改为 `total_checked == passed + failed`。
4. 另：TC-019 原期望「改身份字段 → 422」是错的。`DataStandardUpdate` 未声明身份键，Pydantic v2 默认忽略额外字段，真实契约是 **200 且原值不变**（`tests/test_data_standards_api.py:129-139` 为准）；只有请求体**仅剩**身份键时才是 400。已改写并补 TC-019b。

**验证证据**
- 进程内起 uvicorn（scratch SQLite，端口 8011）实跑：**56 通过 / 0 失败 / 总计 56**，另记 5 条观测说明。临时 harness 与 scratch DB 跑完即删。
- 后端全量：`ENV=test SQLALCHEMY_DATABASE_URL="sqlite:///:memory:" python -m pytest -q` → **310 passed**。
- 前端三门：`npx tsc --noEmit` exit 0；`pnpm lint` exit 0；`pnpm build` exit 0（2747 modules，主 chunk 888.11 kB / gzip 263.30 kB，仅有「chunk 超过 500 kB」的体积提示）。

**未能验收的项（如实记录）**
- ~~**Phase 0「代码库无申请/审批/金标/分发残留引用」= 未达成。**~~ —— 这是按 **SPEC v1.3** 旧判据下的结论，当时证据见下节「待用户决策」。**已被 v1.4 取代**：判据改写为「无**业务**申请/审批/金标/分发链路残留引用」，copilot/governance 的治理裁决与归并建议属 §1.4.1 正式范围，Phase 0 据此判绿（见「当前阶段状态」表）。
- 5,000 上限无法经 HTTP 触发：默认种子只有 22/20/20 条，塞 5001 个假 id 会先命中 `NoMatchingEntities` → 400，走不到上限分支。该分支由 `backend/tests/` 直接对 `quality_runner` 断言覆盖。
- 「写操作有审计记录」与「Mock 数据入库」两条没有 HTTP 观测面（无审计查询端点、无存量记录列表端点），只能靠 pytest 断言。
- `/quality/suspected` 前端页面从未在浏览器里实际操作过，只有 `tsc`/`lint`/`build` 三门通过。

### T1-T8：RalphLoop AI 增强型治理 Demo 全量构建

**做了什么**（逐条记录见 `D:\AI\.shared\WORKLOG.md` 2026-09-02 各条，此处为汇总）
- T1 新表模型：quality_ticket / merge_ticket / key_mapping / agent_trace / governance_owner / approval_evidence 六表 + TicketStatus / EscalationLevel 枚举。
- T2 LLM 网关 `core/llm_gateway.py`：mock（默认）/ DeepSeek 双模式，15s 超时、连续两次失败熔断 15s、自动降级 deterministic mock。
- T3 确定性 Skill 层 `app/skills/`：naming / attribute / unit / quality_rule / duplicate_match / merge_executor，统一 EvidenceItem / SkillSuggestion / SkillResult 契约，全部无副作用。
- T4 Agent 编排层 `app/agents/`：StandardAgent / QualityAgent / DedupAgent + 编排器（request_id 幂等、进程内锁、SLA 3 天 dept_head / 7 天 committee）。
- T5 可复现种子 `scripts/seed_demo_data.py`：默认 10,000 条 material_records、8 个重复候选簇，`--reset` 仅清 demo 数据。
- T6 Copilot/治理 API：`/api/copilot`、`/api/governance`、`/api/owners`、`/api/evidence` 四路由；merge-execute 仅返回 ready，不改写 material_records。
- T7 前端裁决与驾驶舱：/copilot、/governance、/agents、/disputes 四页 + 导航。
- T8 端到端验收 `tests/test_demo_e2e.py` + `docs/demo-script.md`；播种 10,000 条并按 5,000 一批分两次检测（`test_demo_e2e.py:119-140` 断言 `len(all_ids)==10_000`、每批 `total_entities==5_000`、合计 `scanned==10_000`）。**注意：实体上限并未提升，仍是 5,000**（三处常量 `entity_accessor.MAX_ENTITIES` / `duplicate_detector.MAX_ENTITIES_PER_RUN` / `csv_importer.MAX_ROWS` 一致，SPEC v1.4 §5.2 + Phase 2 验收 + 风险表三处均写 5000），10,000 只是播种量，靠分批绕过单次上限。

**验证证据**
- commit `4862b7d`（T1-T8 全量构建）+ `b673209`（Phase 3 疑似错误 + Phase 4.1 CSV 导入），均已 push origin main。
- 后端全量 310 passed；前端 lint / tsc / build 三门绿。

### 文档同步：README / AGENTS 更新至 v2.0.0 现状

**做了什么**
- `README.md` 全面重写：页面（9 旧 → 10 新）、后端分层（8 router / 8 service / 6 Skill / 4 Agent）、14 张表、310 用例、环境变量去 OM/BTP 补 DEEPSEEK_API_KEY，删除已移除的金标数据/BTP/OM 链路描述。
- `AGENTS.md` 全面重写：目录结构、安全约束（归并门禁/审批快照/Skill 无副作用/编排幂等）、长期约束（**5,000** 实体上限，并补 ⚠️ 提示 `seed_demo_data.py` 默认播 10,000 条会超过该上限）、已知问题（旧 MDM 模块按 SPEC §1.4 已移除，knowledge-graph 图谱滞后）。
- `backend/.env.example`：移除无代码读取的 OM_*，补 ENV / MDM_SECRET_KEY / DEEPSEEK_API_KEY。

**验证证据**
- 所有数字对照实际代码核实（10 页面 / 8 router / 14 表 / 310 用例 collect + 全量通过）。
- 后端 `pytest` 310/310 通过（13.8s）。
- 未 commit，git 变更待 Frank 确认。

### 决策落地：SPEC 升 v1.4 承认 AI 辅助治理层

**背景**：下节「待用户决策」记录的范围冲突（T1-T8 AI 层 vs SPEC §1.4 边界 + Phase 0 验收判据）由 Frank 拍板：**保留在 main，走 SPEC 修订路线，取消分支隔离动议**。

**做了什么**
- `docs/spec-data-governance.md` v1.3 → v1.4：
  - 新增 §1.4.1「AI 辅助治理层」五条定位：Agent 只出建议；Skill 确定性无副作用；归并仅返回 ready 不改写存量记录；Copilot 审批 = 治理工单裁决而非业务审批；LLM 可熔断降级。
  - Phase 0 验收判据改写：「无申请/审批/金标/分发残留引用」→「无**业务**申请/审批/金标/分发链路残留引用」（治理裁决层不在限制内）。
  - §11 版本历史补 v1.4 行。
- 下节「待用户决策」随之关闭（保留原文备查）。

**验证证据**
- SPEC 三处改动（§1.4.1 / Phase 0 判据 / §11）均已落盘；`grep` 复核全文无其他处引用旧判据口径。
- 本次为纯文档变更，代码未动，`pytest` 无需重跑（上一轮 310/310 绿）。

---

## 当前阶段状态

SPEC 无独立验收章节，判据取自 §7 各阶段内联的 `**验收**：` 行。下表「依据」列为实测证据，非推断。

| 任务 | 状态 | 依据 |
|------|------|------|
| Phase 0 申请链路移除 | **完成** | `pytest` 310 绿；`tsc`/`lint`/`build` exit 0；SPEC v1.4 起验收判据改为「无**业务**链路残留」，copilot/governance 治理裁决端点属 §1.4.1 正式范围 |
| Phase 1.1 存量存储 + Mock 种子 | **完成** | 跑一次 `init_db.init_db()` 实测：物料 **22**、供应商 **20**、客户 **20**（`partner_records` 合计 40）；`PartnerRecord` 判别列是 `entity_type` |
| Phase 1.2 数据标准 + 附录种子 | **完成** | 实测 `data_standards` **29** 条（material 9 / supplier 13 / customer 7），并由 `rule_derivation.derive_rule_rows` 派生出 15 条物料规则、覆盖五种类型 |
| Phase 1.3 标准 CRUD + 权限 + 审计 | **完成** | e2e TC-010…TC-022+TC-019b 全绿（201/409/403×3/200/400×2/204/404/422） |
| Phase 1.4 前端标准管理页 | **完成** | `src/pages/DataStandards.tsx` 挂在 `/quality/standards`，三门绿 |
| Phase 2.1 三表 + 字段访问层 | **完成** | `models.py` §2.4–2.6 三表；`entity_accessor.py`（`NO_SOURCE_FIELDS[MATERIAL]` = WERKS/EKGRP/DISMM/LGORT/SPRAS） |
| Phase 2.2 规则引擎 + run/results/report API | **完成** | `app/api/quality_checks.py` 已注册；e2e 实测批次检查 308 项 = 通过 302 + 失败 6，跳过 22；`results.total == failed`（6==6），即结果表只存失败项 |
| Phase 2.3 前端检测页 + 报告图 | **完成** | `src/pages/QualityChecks.tsx`（`/quality/checks`）+ `QualityReport.tsx`（`/quality/checks/report`） |
| Phase 3.1 疑似错误检测 + API | **完成** | `app/api/suspected_errors.py`；e2e 实测首检 `created=3 / refreshed=0 / skipped_false_positive=0 / auto_closed=0`，重跑 `created=0`；resolve 后 `resolved_by == "admin001"`（只取自 JWT） |
| Phase 3.2 前端疑似错误页 | **完成** | `src/pages/SuspectedErrors.tsx` 挂在 `/quality/suspected`；**未在浏览器实际操作过** |
| Phase 4.1 CSV 导入 | **完成（仅 API）** | `app/api/data_import.py` + `services/csv_importer.py`；e2e TC-035…TC-044 十条全绿（重复导入走 upsert 计 `updated`、逐行错误明细、`evil.html` 400、`.csv` 配 `image/svg+xml` 400、空文件 400、缺列 400、422、user 403、实体隔离）。SPEC Phase 4 只列了接口，未要求导入 UI |
| 端到端验收 | **完成** | 重写后的 `e2e_test.py` 实际跑通（进程内 uvicorn + 全新播种 SQLite）：**56 通过 / 0 失败 / 总计 56**，另 5 条不计入判定的观测说明 |

## 待用户决策（范围冲突，不自行删除）—— 已关闭（2026-09-02 Frank 拍板）

**结论：保留在 main，SPEC 升 v1.4 承认扩展范围（新增 §1.4.1），取消 `demo/ai-layer` 分支隔离动议。** 以下为当时的冲突分析原文，留档备查：

代码库里有一批 SPEC 之外的演示代码，测试全绿，但与 SPEC §1.4（v1.3 版）服务边界直接冲突，并且是 Phase 0 验收项「代码库无申请/审批/金标/分发残留引用」（旧判据）**未达成**的直接原因：

1. **6 张非 SPEC 表**（`models.py` 共 14 张，SPEC 只定义 8 张）：`quality_ticket`、`merge_ticket`、`key_mapping`、`agent_trace`、`governance_owner`、`approval_evidence`，docstring 直接引用 TC-AIG-002/003/011、TC-MAP-001。
2. **4 个非 SPEC 路由模块**：`api/copilot.py`、`api/governance.py`、`api/owners.py`、`api/evidence.py`（`main.py:56-63` 共注册 8 个 router）。仍在线的审批/归并端点：`copilot.py:62/73/84` 的 `POST /api/copilot/{ticket_type}/{ticket_id}/approve|reject|overturn`，`governance.py:39` 的 `POST /api/governance/merge-execute`。
3. **金标字样**：`models.py:258/259/283/311/315/341/356` 的金标/审批列，`skills/merge_executor.py:26` 的「归并至少需要两条金标记录」。
4. **`app/skills/`（8 个模块）+ `app/core/llm_gateway.py`**：SPEC 全文没有 LLM / Skill / Agent 任何字样。
5. **4 个非 SPEC 前端页面**：`Copilot.tsx`、`GovernanceDashboard.tsx`、`AgentActivity.tsx`、`DisputeView.tsx`（占 `src/pages/` 10 个页面中的 4 个，`src/App.tsx` 12 条路由中的 4 条）。
6. 对应测试约 6 个文件：`test_models_new_tables.py`、`test_governance_skills.py`、`test_llm_gateway.py`、`test_agents.py`、`test_api_copilot.py`、`test_demo_e2e.py`。

处置建议：**移到 `demo/ai-layer` 分支隔离，而不是删除**——这批代码是可运行的演示资产，直接删掉不可逆；隔离后 `main` 才能真正满足 Phase 0 验收。保留在 `main` 的话，则需在 SPEC 补一节承认扩展范围，并把 Phase 0 那条验收判据改写。在得到指示前不动这批代码。

## 剩余项

1. ~~「待用户决策」的处置口径~~ —— **已关闭**（2026-09-02 Frank 拍板：保留 + SPEC v1.4，Phase 0 验收判据已改写，Phase 0 判绿）。
2. `/quality/suspected`、`/quality/checks`、`/quality/checks/report` 三个新页面尚未在浏览器里人工走一遍（目前只有 `tsc`/`lint`/`build` 三门）。
3. 「写操作有审计记录」「Mock 数据入库」两条判据没有 HTTP 观测面（无审计查询端点、无存量记录列表端点），只由 pytest 覆盖。若要变成 e2e 可验，需要补只读的 `GET /api/audit-logs` 与存量列表端点——但这属于扩范围，先不动。

## 常用命令

```bash
# 后端全量测试
cd "D:/AI/14 - 数据治理/backend" && ENV=test SQLALCHEMY_DATABASE_URL="sqlite:///:memory:" python -m pytest -q
# 前端
pnpm lint && npx tsc --noEmit && pnpm build
```
