# TC.md - Manufacturing MDM Governance Test Cases (TDD Backlog)

## 1. Scope

This test case set is for next-iteration governance goals:
- Data consistency across systems
- "One material, multiple codes" resolution
- Critical field completeness gate
- Cross-system code mapping unification
- Incremental data standardization by default

---

## 2. TDD Workflow (Mandatory)

For each story/bug:
1. **RED**: write failing test first.
2. **GREEN**: implement minimum code to pass.
3. **REFACTOR**: optimize while all tests remain green.

Definition of Done per case:
- Test added first and observed failing.
- Implementation passes target test.
- Related suite passes (unit/integration/API).

---

## 3. Test Pyramid Target

- **Unit ~70%**: rules, validators, mapping logic, dedup scoring
- **Integration ~20%**: DB + CRUD + services
- **API/E2E ~10%**: end-to-end workflow and key governance gates

---

## 4. Test Cases (Initial Backlog)

## A. Master Identity & Deduplication

### TC-MID-001 (Unit)
**Title**: Exact same material name is detected as duplicate  
**Given** active golden record exists  
**When** candidate with same canonical name is submitted  
**Then** `is_duplicate=true`, confidence `=1.0`, linked golden id returned

### TC-MID-002 (Unit)
**Title**: Similar material names are flagged by configurable threshold  
**Given** existing materials with lexical overlap  
**When** similarity score >= threshold  
**Then** candidate marked as potential duplicate with ranked top-N list

### TC-MID-003 (Unit)
**Title**: Obsolete golden records are excluded from duplicate candidate set  
**Given** obsolete and active records with same name  
**When** dedup check runs  
**Then** obsolete records are ignored

### TC-MID-004 (Integration)
**Title**: Confirm-merge updates cross-system mapping consistently  
**Given** duplicate candidate pair confirmed by steward  
**When** merge action executes  
**Then** old system codes map to same `golden_material_id` and audit log is generated

### TC-MID-005 (API)
**Title**: Reject merge without required approval role  
**Given** non-authorized user  
**When** call merge endpoint  
**Then** 403 returned and no mapping mutation occurs

---

## B. Critical Field Completeness Gate

### TC-CFG-001 (Unit)
**Title**: Type-based required field template enforces mandatory fields  
**Given** material type template (e.g., RAW)  
**When** required field missing  
**Then** validator returns blocking error list

### TC-CFG-002 (Unit)
**Title**: Conditional mandatory rule is enforced  
**Given** condition "if source=import then supplier_code required"  
**When** condition true and field empty  
**Then** validation fails with rule id

### TC-CFG-003 (API)
**Title**: Submit draft blocked by completeness gate  
**Given** draft application missing key fields  
**When** submit endpoint called  
**Then** 400 with machine-readable validation errors

### TC-CFG-004 (API)
**Title**: Complete data passes gate and proceeds to approval  
**Given** all mandatory and conditional fields valid  
**When** submit endpoint called  
**Then** status transitions to `pending_admin`

### TC-CFG-005 (Integration)
**Title**: Gate result persisted for traceability  
**Given** validation executed  
**When** transaction commits  
**Then** gate result, rule version, and operator are auditable

---

## C. Cross-System Code Mapping Consistency

### TC-MAP-001 (Unit)
**Title**: Mapping uniqueness per source system  
**Given** same source system + source code exists  
**When** create another mapping  
**Then** uniqueness conflict error

### TC-MAP-002 (Integration)
**Title**: One golden id can bind multiple source system codes  
**Given** ERP/MES/WMS codes for same material  
**When** mapping records inserted  
**Then** all resolve to one `golden_material_id`

### TC-MAP-003 (API)
**Title**: Mapping query returns canonical view  
**Given** mapping records exist  
**When** query by any source code  
**Then** API returns golden profile + all linked system codes

### TC-MAP-004 (Integration)
**Title**: Mapping update is atomic under concurrency  
**Given** concurrent requests for same source code  
**When** both attempt bind  
**Then** only one succeeds, no split-brain mapping

---

## D. Incremental Standardization (Future New Data)

### TC-INC-001 (Unit)
**Title**: New record defaults to standardization pipeline  
**Given** new material request  
**When** created  
**Then** lifecycle state starts at `validation_pending`

### TC-INC-002 (API)
**Title**: Non-standard code format rejected at ingress  
**Given** code violates naming/segment rule  
**When** create request  
**Then** 400 with normalized error code

### TC-INC-003 (Integration)
**Title**: Approved record auto-publishes mapping event  
**Given** approval completed  
**When** publish job runs  
**Then** downstream sync event emitted with version and checksum

---

## E. Semantic Consistency for BI/AI

### TC-SEM-001 (Unit)
**Title**: Metric term resolves to canonical definition  
**Given** synonym terms (e.g., "准时率", "到货准时率")  
**When** semantic resolver called  
**Then** returns canonical metric id + formula version

### TC-SEM-002 (API)
**Title**: Query with ambiguous term requires disambiguation  
**Given** term matches multiple business definitions  
**When** ask semantic endpoint  
**Then** response includes disambiguation options, no guessed answer

### TC-SEM-003 (Integration)
**Title**: AI answer guardrail must cite governance evidence  
**Given** question over KPI  
**When** guardrail enabled  
**Then** answer payload contains term definition source + rule references

---

## F. AI-Enhanced Governance Demo (SPEC 2026-08-26)

### TC-AIG-001 (Unit/API)
**Title**: Standard check agent is read-only, outputs evidence-graded advice  
**Given** incremental batch of 10 new material applications (with naming/unit/attribute defects)  
**When** standard-check pipeline runs  
**Then** each item returns "符合/不符 + 修正建议 + 证据 + L1/L2/L3 分级" AND golden records are unchanged

### TC-AIG-002 (Integration)
**Title**: Quality ticket state machine covers full lifecycle  
**Given** quality gate flags issues with severity  
**When** tickets created and acted upon  
**Then** transitions `draft→pending→approved/rejected→executing→done/failed` all pass, and failed tickets are recoverable (re-run idempotent via `request_id`)

### TC-AIG-003 (Integration)
**Title**: Merge agent produces candidate clusters with evidence chain, never auto-merges  
**Given** golden records with duplicate clusters (same-name-diff-code / unit variants / close descriptions)  
**When** dedup agent runs  
**Then** candidate clusters returned with evidence + L1/L2/L3 grades, and no merge is executed automatically

### TC-AIG-004 (API)
**Title**: Copilot verdict card enforces triple evidence and high-risk confirmation  
**Given** Owner opens a pending verdict card  
**When** attempting to approve a high-risk action (merge execute / unit conversion / attribute fix)  
**Then** card contains evidence chain + risk label + alternatives, and approval requires typed opinion or second confirmation; approve/reject/overturn all leave audit trail

### TC-AIG-005 (Integration)
**Title**: Cross-division merge dispute escalates through approval chain with co-sign  
**Given** merge suggestion touching factory A (agree) and factory B (oppose)  
**When** dispute raised  
**Then** ticket escalates to approval chain, both Owners co-sign, decision is persisted with full trace

### TC-AIG-006 (Integration)
**Title**: Stale standard triggers revision workflow, not just validation warning  
**Given** naming validation fails against a standard not revised since 2024  
**When** agent flags the failure  
**Then** system surfaces "标准过时" and opens standard-revision flow

### TC-AIG-007 (Integration)
**Title**: Ticket SLA auto-escalates on timeout  
**Given** remediation ticket open  
**When** 3 days pass without action  
**Then** escalates to department head; at 7 days escalates to governance committee (no silent pile-up)

### TC-AIG-008 (Unit/API)
**Title**: L1 rule overrides LLM suggestion on strength-grade conflict (10.9 vs 8.8 bolt)  
**Given** two same-spec bolts with strength 10.9 and 8.8, LLM suggests merging  
**When** dedup agent evaluates  
**Then** L1 rule detects strength conflict and overrides LLM: explicit "不建议合并"

### TC-AIG-009 (API)
**Title**: Merge execution endpoint rejects unapproved requests; optimistic lock works  
**Given** merge ticket not yet approved  
**When** execution endpoint called  
**Then** 4xx returned, no golden record mutation; concurrent version-conflicting updates fail cleanly

### TC-AIG-010 (API)
**Title**: Governance dashboard reflects real-time metrics after approval  
**Given** dashboard showing quality score / duplicate rate / todos / agent activity  
**When** an approval completes and golden record is written  
**Then** metrics update without manual refresh

### TC-AIG-011 (API)
**Title**: Accountability query answers "what evidence was this approved on"  
**Given** any approved verdict  
**When** accountability query called  
**Then** returns evidence snapshot (what approver saw), trace_id, model version, input summary, evidence refs

### TC-AIG-012 (Manual walkthrough)
**Title**: Live validation with 5-10 unfamiliar customer records closes every defect  
**Given** customer-supplied data run through the pipeline on-site  
**When** pipeline completes  
**Then** every defect is either suggested, adjudicated, or tracked in a ticket — zero silent misses (success = closed-loop, not 100% detection)

### TC-AIG-013 (Integration)
**Title**: LLM gateway degrades to mock on timeout/failure  
**Given** LLM mode=mock|deepseek switch  
**When** LLM call exceeds 15s timeout or fails twice  
**Then** circuit breaker trips, degraded to mock response, token cost warning logged, pipeline continues

---

## 5. Regression Suite (Must Keep Green)

- Existing auth tests (`test_auth.py`)
- Core API workflow tests (`test_api.py`)
- CRUD integrity tests (`test_crud.py`)
- Duplicate detector tests (`test_duplicate_detector.py`)
- Validator and code-generator tests

---

## 6. Recommended Execution Order (TDD-friendly)

1. TC-CFG-001 -> TC-CFG-004 (completeness gate first)
2. TC-MID-001 -> TC-MID-004 (dedup + merge flow)
3. TC-MAP-001 -> TC-MAP-004 (mapping consistency)
4. TC-INC-001 -> TC-INC-003 (incremental default standardization)
5. TC-SEM-001 -> TC-SEM-003 (BI/AI semantic layer)
6. TC-AIG-001 -> TC-AIG-013 (AI-enhanced governance demo, order per plan.md)

---

## 7. Naming Convention

Format: `TC-{DOMAIN}-{NUMBER}`  
Domains: `MID`, `CFG`, `MAP`, `INC`, `SEM`, `AIG`

Example pytest name:
- `test_tc_cfg_003_submit_blocked_when_required_fields_missing`

---

## 8. Acceptance Gate for This TC Backlog

- Each TC is implementable as automated test.
- Each TC has clear pass/fail condition.
- Critical business risks ("one material multiple codes", missing key fields, cross-system inconsistency) are covered.
- Backlog is ordered to support RED -> GREEN incremental delivery.
