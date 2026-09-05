# 物料 / 供应商 / 客户字段治理闭环 — 设计文档

> 日期：2026-09-05
> 状态：已与用户对齐并实现，通过全量验收（后端 388 passed、前端 lint/tsc/build 绿、live 库闭环走查通过）
> 基线：承接 2026-09-03 元数据管理设计（字段登记册为单一权威源）。本设计新增**存量记录字段级修正写口**与**治理状态装配**，使「标准 → 登记 → 检测 → 修复 → 复检」闭环闭合。AGENTS.md 安全约束已追加「记录修正门禁」行，与既有的「归并门禁禁止直接改写 material_records」并列为豁免范围。
> 范围决策（用户拍板）：**允许改码**（MATNR/LIFNR/KUNNR 修复真实改写冗余列 material_code / partner_code，带 pattern + 唯一性护栏）；**不改 schema、不加表不加列、不改种子数据**（现有 14 条脏记录够演示）；闭环形态 = 元数据治理状态列 + 检测页行内修正 + 深链。

## 1. 背景与目标

探索证实的三个缺口：

1. **无状态呈现**：字段链路按值贯穿可用（metadata_field → standard → rule → result 全部以 SAP field_name 关联），但字段登记册没有治理状态列——治理成果无法在「对象视图」上呈现。
2. **修复写口缺失**：`material_records` 零写入口、partner 仅 CSV upsert（且要求整体赋新 dict）；疑似错误 resolve 只改状态不改数据。检测出的失败无法处置，闭环断在「检出」。
3. **结果无状态列**：QualityCheckResult 只存失败、重跑不清旧行——「修复」的证据天然来自**最新批次该字段失败数归零**（历史批次留档，趋势可查）。

**目标**：以三大主数据实体字段为对象走通「标准 → 登记 → 检测 → 修复 → 复检」闭环，可在 /metadata、/quality/checks、/quality/standards 三个页面间深链演示。

## 2. 闭环语义与修复落点（关键设计决策）

### 2.1 记录身份与字段定位

- 记录身份 = uuid 主键（永不改变）；修复对象是**治理字段（SAP 字段名）**，不是数据库列。
- 字段名须命中该实体 `data_standards`（ilike 大小写不敏感匹配，防 camelCase——Ariba SMVendorID 等）；规范化名以 `standard.field_name` 为准回显。
- 落点由 `entity_accessor.describe_source` 裁决，修复端点与质量检测**同源裁决**，杜绝「修了 A 处、检了 B 处」的脱节：

| 裁决 | 落点 | 字段示例 | 写方式 |
|---|---|---|---|
| column | 冗余列 | MATNR→material_code、LIFNR/KUNNR/PARTNER→partner_code、MAKTX/NAME1→*_name | `setattr` |
| attributes | attributes JSON 键 | MEINS、MTART、CITY1、ZTERM… | **整体赋新 dict**（SQLAlchemy 不追踪就地修改） |
| none（无数据源） | — | WERKS/EKGRP 等 NO_SOURCE 字段 | 拒绝修复（400 带 reason） |

### 2.2 冗余列策略与上游同步边界

编码字段（MATNR/LIFNR/KUNNR）在登记仓存冗余列，本端修复只改登记仓；SAP/Ariba 上游的修正属外部变更流程（不在本平台能力内）。声明边界：

- 修复写冗余列后，**CSV 再导入含旧码的历史文件会重建新行**（upsert 以冗余列值匹配，旧码已不存在 → 当新记录插入）。demo 数据是「导入一次后在线治理」的存量视图，演示剧本不重复导入。
- 唯一性：material_code 全局唯一（`uq_material_code`）；partner_code 唯一域为 `(entity_type, partner_code)`（`uq_entity_partner_code`）——supplier 与 customer 允许共用同一编号，供应商与客户修复互不冲突。

## 3. 修复端点契约

```
POST /api/records/{entity_type}/{record_id}/fix
Authorization: Bearer <JWT>   # require_admin：admin / data_admin 可写
{ "field_name": "MATNR", "value": "M10234" }
# value 省略或 null/空串 = 清除该字段键（attributes 键删除 / 列置空）
```

成功（200）：

```json
{ "record_id": "…", "entity_type": "material", "field_name": "MATNR",
  "old_value": "M1234", "new_value": "M10234", "updated_at": "…" }
```

错误矩阵（错误码 → HTTP + 中文 detail）：

| 场景 | HTTP | 示例 |
|---|---|---|
| 记录不存在 / entity_type 非法 | 404 | 「记录不存在」 |
| 字段未纳入该实体数据标准 | 400 | 「MATNR 未纳入数据标准，拒绝修复」 |
| 字段无数据源（NO_SOURCE） | 400 | 「工厂（WERKS）在登记仓无数据源，无法修复」 |
| 必填字段清空 | 400 | 「基本计量单位（MEINS）为必填字段，不能清空」 |
| pattern 预校验不过 | 400 | 「物料编码（MATNR）格式校验失败：…（标准 ^M\d{5}$）」 |
| NOT NULL 身份列清空 | 400 | 非空列禁止置空 |
| 编码唯一冲突（预查 + IntegrityError 兜底） | 409 | 「物料编码（MATNR）新值『M10234』已被其他记录占用」 |

服务层（`record_fixer.fix_record_field`）**不写审计**；API 层成功后才落 `AuditService.log(step_name=record_field_update, details={record_id, entity_type, field_name, old_value, new_value})`（沿用 quality_run 两段式）。pattern 预校验与质量引擎同源：`quality_engine.compile_pattern()` + `compiled.search()`，`re.error` 时跳过（与引擎降级为 rule_errors 对齐）。

## 4. 治理统计装配（/api/metadata/fields）

列表与 PUT 响应装配四元组（口径与「最新批次」严格一致）：

| 字段 | 口径 |
|---|---|
| quality_rule_count | rule→standard→metadata_field_id 一次 JOIN 聚合（0 = 未纳入规则治理） |
| latest_batch_id | 本页 distinct 实体类型各取最新批次 1 次 |
| latest_batch_failed | 最新批次按 result.field_name GROUP BY（**键 = SAP field_name**） |
| latest_checked_at | 最新批次 started_at |

实现于 `metadata_service.enrich_field_governance(db, fields)`，列表一次调用完成（登记册 86 行 × 3 实体 = 3 次批次查询 + 1 次 GROUP BY，无 N+1）。GET /results 同步支持 `field_name` 过滤参数（字段深链数据源）。

## 5. 前端形态与演示路径

| 页面 | 改动 |
|---|---|
| /metadata 字段清单 | 「标准数」后加「治理规则数 / 治理状态」两列；状态四态：灰「未纳入治理」、蓝「未检测」、绿「已达标」、红「n 待修复」（Link → `/quality/checks?entity_type&field_name&batch_id`）；标准数徽标改 Link → `/quality/standards?entity_type&field_name`。页面内部导航仍 state-based（不加 URL 语义） |
| /quality/checks | 结果筛选条加「字段」Select（选项 = 当前实体规则字段去重）；URL 预选 `?field_name=&batch_id=` 一次生效；结果表操作列「修正」（writable 可见）→ FixFieldDialog（现值/问题/新值输入/「清空该键」仅非必填字段；400/409 就地展示，成功 toast「已修正，请重跑检测验证」**不自动重跑**）；空态区分「该字段已无失败记录」 |
| /quality/standards | useSearchParams 一次性预选实体 + 搜索框注入字段名（不订阅 URL；各实体标准 ≤13 条 < 每页 20，预选实体后单页可容，就地过滤必命中） |

**演示剧本**（live 库，`backend/mdm_governance.db`；`python init_db.py` 可重置）：
`/metadata` 字段清单看「待修复」红徽标 → 点击深链 `/quality/checks` 自动选中实体/字段/最新批次 → 「开始检测」生成新批次 → 失败行「修正」→ 重跑 → 该字段归零显示「已达标」空态 → 回 /metadata 徽标转绿；/quality/checks/report 通过率随修复上升。

## 6. 建议修复值表（首轮实测失败分布 6/7/4 = 17 行）

2026-09-05 live 首轮批次实测（重置种子库后复现；修复值均为既有编号序列中的空号/值域内合理值，仅演示参考，不硬编码测试）：

| 实体 | 字段 | 脏值 | 记录 | 建议修复值 | 说明 |
|---|---|---|---|---|---|
| material | MATNR | M1234 | M1234 | **M10234** | 格式错 ^M\d{5}$（已应用验证闭环） |
| material | MATNR | MAT-00020 | MAT-00020 | **M10235** | 格式错 |
| material | MEINS | SET | M10014 | KG | 值域外，取序列内业务合理值 |
| material | MEINS | （空） | M10020 | KG | 必填空 |
| material | MTART | XXX | M10019 | ROH | 值域外 |
| material | NTGEW | -0.01 | M10020 | 0.01 | 低于下限 0.0 |
| supplier | LIFNR | 12345 | 12345 | **1000000021** | 编码格式错（10 位数字） |
| supplier | LIFNR | SUP-00017 | SUP-00017 | **1000000017** | 编码格式错 |
| supplier | CITY1 | （空） | 12345 | 杭州市 | 必填空 |
| supplier | LAND1 | XX | 1000000019 | CN | 值域外 |
| supplier | POST_CODE1 | 31000 | 12345 | 310000 | 格式错 ^\d{6}$ |
| supplier | ZTERM | （空） | 1000000019 | 0010 | 必填空（ZTERM 非必填标准时为可选清空演示项） |
| supplier | ZTERM | （空） | 1000000020 | 0001 | 必填空 |
| customer | KUNNR | CUS-0017 | CUS-0017 | **2000000017** | 编码格式错 |
| customer | COUNTRY | （空） | 2000000018 | CN | 必填空 |
| customer | POST_CODE1 | 3100 | 2000000019 | 310000 | 格式错 ^\d{6}$ |
| customer | ZTERM | （空） | 2000000020 | 0001 | 必填空 |

修复顺序建议：先修编码（409 冲突面最小、演示效果最直观），再修必填空与值域；每次修复后重跑，观察最新批次该字段失败归零、报告通过率上升。

## 7. 验收证据（2026-09-05）

- 后端全量：`python -m pytest -q` = **388 passed**（基线 310 + 78 新增：record_fix API 25 例含 e2e「修复→重跑→最新批次该字段 0 且旧批次留档」、field_name 过滤、治理装配口径）
- 前端：`pnpm lint` 0 error、`npx tsc --noEmit` 0 error、`pnpm build` 通过
- live 库走查：三实体 run 6/7/4；/metadata 装配口径抽查 MATNR=(3 规则, 2 失败) 与 SQL 直查一致；field_name 过滤全命中；M1234→M10234 修复 200 + audit 落库；重跑后新批次 MATNR 仅剩 MAT-00020（修复归零 + 历史留档双证）；重复编码 409 且库不变

## 8. 已知限制

- **命名类疑似错误不进本闭环**：疑似错误模块（duplicate/naming）resolve 仍只改状态，属归并工作流范畴。
- **无数据源字段不可修复**：MARC 组织级字段（WERKS 等）登记仓无落点，检测记跳过、修复拒绝——属「需回源系统治理」的显式边界。
- **历史失败行不清除**：修正后旧批次行仍在（留档）；判定一律以最新批次为准，页面空态/徽标均与最新批次口径一致。
- **attributes JSON 无 schema 强约束**：修复写 attributes 依赖 data_standard 登记护栏（类型/值域/格式预校验），未来可引入 attributes 模板校验（attribute_templates 表已存在，未启用）。
