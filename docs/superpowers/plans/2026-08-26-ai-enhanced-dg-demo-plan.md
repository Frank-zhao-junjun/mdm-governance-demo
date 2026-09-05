# AI 增强型数据治理 Demo 实施计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
> **依据:** SPEC 2026-08-26-ai-enhanced-dg-demo-spec.md（六要素）+ 蓝图 v3（2026-08-25-ai-native-dg-demo-design.md 4.5 技术改动点）
> **测试挂钩:** TC.md F 区（TC-AIG-001 ~ TC-AIG-013）

**Goal:** 在 RalphLoop 平台上实现 AI 增强型数据治理 Demo——六个确定性 Skill + 三个 Agent + LLM 网关 + 六张新表 + Copilot 裁决工作台，证明"确定性治理 + AI 建议增强"路线，主线是"责任人带着证据裁决"。

**Architecture:** 确定性规则层（Skill 纯函数，证据分级 L1/L2/L3）承载正确底线；Agent 层编排只读检核/候选召回/工单生成，任何写库走人工确认；LLM 网关（mock 默认/DeepSeek 可切）只出建议与语义召回，永不自动执行。复用现有 `duplicate_detector`/`material_validator`/`audit_service`/审批流骨架/金标数据/BTP 分发，只加新表新包，不动现有表结构语义。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Pydantic v2（uv）/ React 19 + TypeScript + recharts（pnpm，已有依赖）/ httpx（LLM 网关，若未装 `uv add httpx`）。

---

## Global Constraints

- 所有新代码必须 TDD：先写失败测试（挂 TC-AIG-xxx），再实现，再重构。
- **任何写库（金标/归并/分发）一律人工确认**；自动仅限无副作用环节（只读检核、候选生成、提示）。
- 证据分级 L1/L2/L3 为唯一信任机制；禁止把 LLM 置信度分数写入任何业务字段。
- 所有 Agent 继承统一基类 `BaseAgent`（错误处理/重试/trace 上报/日志格式），禁止各自为政。
- 幂等键 `request_id` 贯穿所有工单/归并操作；金标记录用现有 `version` 字段乐观锁；不做自动回滚。
- LLM 网关默认 `LLM_MODE=mock`；切 `deepseek` 时 API key 走环境变量 `DEEPSEEK_API_KEY`，禁止硬编码/入日志。
- 新表六张：`quality_ticket` / `merge_ticket` / `key_mapping` / `agent_trace` / `governance_owner` / `approval_evidence`，不改现有表。
- 后端 API 路由前缀保持 `/api`；错误消息中文；凭证走环境变量。
- 前端包管理器 pnpm（禁止 package-lock.json）；后端 uv 管理。
- 每个任务一次 commit；最终必须通过 `uv run pytest` 与 `pnpm build`。

---

### Task 1: 新表模型（六张表）

**Objective:** 在 `app/models.py` 追加六张新表，字段满足工单/归并/问责/权责链路。

**Files:**
- Modify: `backend/app/models.py`（追加，不改现有类）
- Test: `backend/tests/test_models_new_tables.py`

**表设计（SQLAlchemy 2.0 风格，与现有文件保持一致）：**

| 表 | 关键字段 |
|----|----------|
| `quality_ticket` | id, request_id(幂等,index), application_id, golden_record_id, rule_key, severity, issue_type, description, status, assignee_owner_id, sla_due_at, escalated_level, evidence_json, trace_id |
| `merge_ticket` | id, request_id, candidate_golden_ids(JSON), suggested_golden_id, evidence_json, status, factory_agreements_json, escalated_level, decided_by, decision_opinion, decided_at, trace_id |
| `key_mapping` | id, golden_record_id, source_system, source_code, mapping_type, created_at（unique(source_system, source_code)） |
| `agent_trace` | id, trace_id, agent_name, model_version, input_summary, evidence_refs_json, decision_snapshot_json, created_at |
| `governance_owner` | id, role(owner/steward/approver), name, department, domain, email, is_active |
| `approval_evidence` | id, ticket_type, ticket_id, approver_id, action, opinion, snapshot_json(当时证据), created_at |

- [ ] **Step 1: 写失败测试** `test_models_new_tables.py`：断言六张表可创建、`key_mapping` 唯一约束生效、枚举/状态默认值正确。
- [ ] **Step 2: 运行确认 RED**：`uv run pytest tests/test_models_new_tables.py -v` → FAIL（表不存在）。
- [ ] **Step 3: 实现** 在 `models.py` 追加六类；新状态枚举：TicketStatus(draft/pending/approved/rejected/executing/done/failed)、EscalationLevel(none/dept_head/committee)。
- [ ] **Step 4: 验证 GREEN**：pytest 通过；`uv run python -c "from app.models import QualityTicket, MergeTicket"` 可导入。
- [ ] **Step 5: Commit** `feat(models): add governance demo tables (quality/merge/key_mapping/agent_trace/owner/approval_evidence)`

**模型分级:** Fast/cheap | **TC 挂钩:** TC-AIG-002（状态机）、TC-AIG-009（乐观锁）

---

### Task 2: LLM 网关 `app/core/llm_gateway.py`

**Objective:** 模型网关：mock/DeepSeek 切换、超时 15s、重试 2、熔断降级 mock、token 成本告警、trace 透传。

**Files:**
- Create: `backend/app/core/llm_gateway.py`
- Test: `backend/tests/test_llm_gateway.py`

- [ ] **Step 1: 写失败测试** `test_llm_gateway.py`：mock 模式返回固定结构；deepseek 模式超时→熔断→降级 mock；连续 2 次失败断路器打开；`trace_id` 透传。
- [ ] **Step 2: RED**：`uv run pytest tests/test_llm_gateway.py -v` → FAIL（模块不存在）。
- [ ] **Step 3: 实现**

```python
class LLMGateway:
    def __init__(self, mode: str = "mock", api_key: str | None = None):
        self.mode = mode  # "mock" | "deepseek"
        self._failures = 0
        self._open = False  # circuit breaker

    def complete(self, prompt: str, trace_id: str) -> dict:
        """返回 {"content": str, "model": str, "usage": {...}}；熔断时降级 mock。"""
        # deepseek: POST https://api.deepseek.com/chat/completions (httpx, timeout=15)
        # 超时/异常 → failures+=1；>=2 → _open=True 15s 冷却；期间直接 mock
        # mock: 返回配置好的固定建议文本（由调用方按场景注入）
        # token 成本: usage 累计，超阈值打印告警（日志，不进业务字段）
```

- [ ] **Step 4: GREEN** + **Step 5: Commit** `feat(core): add LLM gateway with mock/deepseek switch, circuit breaker`

**模型分级:** Mid-tier | **TC 挂钩:** TC-AIG-013

---

### Task 3: Skill 层 `app/skills/`（六 Skill，纯函数）

**Objective:** 六个纯函数 Skill，统一接口 `(input, standard) -> {status, suggestions[], conflicts[]}`，每条建议带 `evidence_level: L1|L2|L3` 与 `source`。可独立单测，不依赖 DB/LLM。

**Files:**
- Create: `backend/app/skills/__init__.py`, `naming.py`, `attribute.py`, `unit.py`, `quality_rule.py`, `duplicate_match.py`, `merge_executor.py`, `common.py`（证据/建议数据类）
- Test: `backend/tests/test_skills_naming.py`, `test_skills_unit.py`, `test_skills_duplicate_match.py` 等

**统一返回结构（common.py）：**
```python
class EvidenceItem(BaseModel):
    level: Literal["L1", "L2", "L3"]   # L1 规则命中 / L2 统计推断 / L3 语义推断
    source: str                          # 证据来源（字典/映射表/样本记录/LLM）
    detail: str

class SkillSuggestion(BaseModel):
    field: str
    suggestion: str
    evidence: EvidenceItem
    auto_fixable: bool = False           # 仅 L1 且无歧义时 True；仍不自动写库

class SkillResult(BaseModel):
    status: Literal["pass", "warn", "block", "suggest"]
    suggestions: list[SkillSuggestion]
    conflicts: list[dict]                # 如 {"type": "strength_conflict", "level": "L1", "message": "不建议合并"}
```

| Skill | 职责 | L1 来源 | L2 来源 | L3 来源 | 关键用例 |
|-------|------|---------|---------|---------|----------|
| `naming` | 命名规范校验 | 分类字典/命名正则 | — | 同义变体提示（LLM 或词形） | TC-AIG-001/006 |
| `attribute` | 属性模板完整性 | 模板必填项 | 同分类众数推断（带样本） | — | TC-AIG-001 |
| `unit` | 单位与换算系数 | 换算映射表 | — | 单位别名召回 | TC-AIG-001/B类换算 |
| `quality_rule` | 质量规则引擎封装 | `governance_rules` 表规则执行 | — | — | TC-AIG-002 |
| `duplicate_match` | 候选簇+证据链 | 复用 `DuplicateDetector.check` + 强度冲突检测（10.9 vs 8.8 → 覆盖 LLM 建议） | 描述相似度统计 | LLM 语义相似召回 | TC-AIG-003/008 |
| `merge_executor` | 归并执行（只接受 approved） | 预检：金标冲突/分发在途 | — | — | TC-AIG-009 |

- [ ] **Step 1-2: 每 Skill 先写失败测试**（挂对应 TC），再实现，最后 GREEN。
- [ ] **Step 3: 强度冲突检测（TC-AIG-008 核心）** 在 `duplicate_match.py`：解析两记录强度等级值域（8.8/10.9/12.9），同规格不同强度 → 返回 `conflicts` 覆盖建议，明确"不建议合并"。
- [ ] **Step 4: Commit**（可拆 2-3 次：common+前三个、duplicate_match+merge_executor、测试收尾）

**模型分级:** Mid-tier（duplicate_match 最复杂）| **TC 挂钩:** TC-AIG-001/002/003/006/008/009

---

### Task 4: Agent 层 `app/agents/`

**Objective:** 统一基类 `BaseAgent` + 三个 Agent + Orchestrator，纪律约束（4.4）。

**Files:**
- Create: `backend/app/agents/__init__.py`, `base.py`, `standard_agent.py`, `quality_agent.py`, `dedup_agent.py`, `orchestrator.py`
- Test: `backend/tests/test_agents.py`, `test_orchestrator.py`

**BaseAgent（base.py）：**
```python
class BaseAgent(ABC):
    name: str = "base"
    def __init__(self, db: Session, llm: LLMGateway):
        self.db = db; self.llm = llm; self.trace_id = uuid4().hex

    def run(self, payload: dict) -> dict:
        """模板方法：trace 开始 → _execute → 结果 + trace 落库（agent_trace）→ 异常统一处理（重试/降级/标记 failed）"""
        ...
    @abstractmethod
    def _execute(self, payload: dict) -> dict: ...
```

| Agent | 行为 | 产出 |
|-------|------|------|
| `StandardAgent` | 只读标准校验（naming+attribute+unit） | 每条"符合/不符+建议+证据级别"，**不改库** |
| `QualityAgent` | 跑 quality_rule，问题分级阻断/警告/提示 | 生成 `quality_ticket`（指派 Steward、SLA=3天） |
| `DedupAgent` | duplicate_match 候选簇 + 证据链 | 生成 `merge_ticket`（推荐不合并） |
| `Orchestrator` | 编排增量线/存量线；幂等（request_id 去重）；增量/存量操作串行化；SLA 升级检查（3天→dept_head, 7天→committee） | 工单流转 + `agent_trace` |

- [ ] **Step 1: 写失败测试**：StandardAgent 不改库（TC-AIG-001）；QualityAgent 生成工单+指派+SLA（TC-AIG-002/007）；DedupAgent 不自动合并（TC-AIG-003）；Orchestrator 幂等去重 + 串行化 + SLA 升级。
- [ ] **Step 2: RED** → **Step 3: 实现**（base → 三 Agent → Orchestrator 依赖顺序）→ **Step 4: GREEN** → **Step 5: Commit**

**模型分级:** Mid-tier→Most capable（Orchestrator）| **TC 挂钩:** TC-AIG-001/002/003/007/011

---

### Task 5: 种子数据脚本 `scripts/seed_demo_data.py`

**Objective:** 可复现 demo 数据：10,000 条金标（紧固件+轴承，固定随机种子）+ A 类缺陷（重复簇 8-10 组/残缺 2-3%）+ B 类预埋（10.9 vs 8.8、换算系数、镀锌vs电镀锌、简繁混写）+ 权责冲突场景数据（工厂 FA/FB、Owner 虚构姓名）+ 标准字典与换算映射表。

**Files:**
- Create: `backend/scripts/seed_demo_data.py`（或 `scripts/` 与现有工具一致）
- Test: `backend/tests/test_seed_demo_data.py`（断言：条数、重复簇数量、B 类样例存在、幂等可重跑）

- [ ] **Step 1-4: TDD 循环**；`uv run python scripts/seed_demo_data.py --reset` 可反复重跑，不产生重复数据（request_id/唯一键幂等）。
- [ ] **Step 5: Commit** `feat(scripts): add reproducible demo seed data (10k golden + A/B class defects + dispute scenario)`

**模型分级:** Fast/cheap | **TC 挂钩:** TC-AIG-003/005/008（数据前提）

---

### Task 6: API 层

**Objective:** `/api/copilot/*`、`/api/governance/*`、`/api/owners/*`、`/api/evidence/*`，执行端点强制校验"已批准"状态。

**Files:**
- Create: `backend/app/api/copilot.py`, `governance.py`, `owners.py`, `evidence.py`
- Modify: `backend/app/main.py`（注册 router）
- Test: `backend/tests/test_api_copilot.py`, `test_api_governance.py`

| 路由 | 功能 | 安全要求 |
|------|------|----------|
| `GET /api/copilot/todos` | 待办列表（Owner/Steward 视角过滤） | 需登录 |
| `POST /api/copilot/{ticket_type}/{ticket_id}/approve` | 批准：必传 `opinion`（高风险必填）+ 二次确认字段 | 写 `approval_evidence` 快照 |
| `POST /api/copilot/{ticket_type}/{ticket_id}/reject` / `overturn` | 驳回/改判，留痕 | 同上 |
| `GET /api/copilot/accountability?ticket_id=` | 问责查询：证据快照+trace_id+模型版本+审批记录 | — |
| `GET /api/governance/report` | 质量报告（质量分/重复率/待办） | — |
| `GET /api/governance/clusters` | 重复簇列表 | — |
| `POST /api/governance/merge-execute` | 归并执行 | **校验 ticket.status==approved**，否则 4xx；乐观锁 version |
| `GET/POST /api/owners/*` | 责任人指派（owner/steward/approver CRUD） | 管理操作 |
| `GET /api/evidence/{ticket_type}/{ticket_id}` | 证据链查询 | — |

- [ ] **Step 1-2: RED**（每路由先测：未批准执行归并→4xx TC-AIG-009；无意见批准→4xx TC-AIG-004；问责返回快照 TC-AIG-011）
- [ ] **Step 3: 实现**（依赖 Task 1-4）→ **Step 4: GREEN** → **Step 5: Commit**

**模型分级:** Mid-tier | **TC 挂钩:** TC-AIG-004/009/010/011

---

### Task 7: 前端（Copilot 工作台 + 驾驶舱 + 活动流 + 权责冲突视图）

**Objective:** 四个新页面/视图，复用现有 Layout/shadcn/ui；驾驶舱用 recharts（依赖已有）。

**Files:**
- Create: `src/pages/Copilot.tsx`（裁决工作台：三件套卡片+高风险二次确认+审批链/升级路径）、`src/pages/GovernanceDashboard.tsx`（recharts：质量分/重复率/待办/Agent 活动流）、`src/pages/AgentActivity.tsx`（trace 时间线）、`src/pages/DisputeView.tsx`（权责冲突/会签）
- Modify: `src/App.tsx`（路由注册）
- Test: `src/__tests__/`（vitest，若有现成模式；至少 `pnpm build` + tsc 通过）

**关键交互（防死 UI）：**
- Copilot 卡片：证据链/风险标注/替代选项三件套必渲染；批准按钮对高风险项弹二次确认（输入意见），POST 后才显示成功；无 API 不渲染假成功。
- 驾驶舱：挂载时 GET /api/governance/report + /api/copilot/todos + /api/evidence 轮询/手动刷新；批准操作后指标刷新。
- 活动流：GET agent_trace 渲染时间线。

- [ ] **Step 1: 先建路由+空页（tsc 过）** → **Step 2: 逐页接 API**（每按钮对应真实 fetch，不渲染死 UI）→ **Step 3: `pnpm build` + `pnpm exec tsc -b --noEmit` 通过** → **Step 4: Commit**（可拆 2-3 次）

**模型分级:** Mid-tier | **TC 挂钩:** TC-AIG-004/010/011（前端联动验证）

---

### Task 8: 端到端验证 + 演示剧本走查

**Objective:** 全链路联调：seed → 增量批次 → 标准校验 → 质量工单 → 归并候选 → Copilot 裁决（含权责冲突插曲）→ 金标入库 → 驾驶舱变化；B 类样例演示拦截；现场验证环节（5-10 条陌生数据）走查。

**Files:**
- Create: `backend/tests/test_demo_e2e.py`（test client 走全流程，断言 0 静默漏过）
- Update: 演示剧本（`docs/` 下新增 `demo-script.md`，含计时与话术，对齐蓝图 4.1）

- [ ] **Step 1: 写 E2E 测试**：10 条增量批次 → 所有缺陷都有承接（建议/工单/裁决），断言各 TC-AIG 关键点。
- [ ] **Step 2: 回归**：`uv run pytest tests/ -v` 全绿 + `pnpm build` 通过。
- [ ] **Step 3: 按 SPEC S1-S7 逐项核对**（演示时长/三件套/拦截/问责/存量扫描性能）。
- [ ] **Step 4: Commit** + 更新 WORKLOG。

**模型分级:** Most capable | **TC 挂钩:** TC-AIG-012（手动走查）+ 全部回归

---

## 实施顺序与依赖

```
Task 1 (表) → Task 2 (LLM 网关) ─┐
                                 ├→ Task 4 (Agent) → Task 6 (API) → Task 7 (前端) → Task 8 (E2E)
Task 3 (Skill) ── Task 5 (种子) ─┘
```

Task 1/2/3 可并行（独立）；Task 5 依赖 1/3；Task 4 依赖 1/2/3；Task 6 依赖 4；Task 7 依赖 6；Task 8 依赖全部。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| DeepSeek 网关真实调用不稳定（演示现场） | 默认 mock，演示前固定场景用 mock 保底；真实切换仅 PoC 环节 |
| 10,000 条种子生成慢/占空间 | 固定随机种子程序化生成，单脚本 ≤2 分钟；`--reset` 幂等 |
| 前端新页面破坏现有构建 | 每任务过 `pnpm build` + tsc；复用现有 shadcn/ui 组件 |
| 演示现场客户数据触发未知缺陷 | 现场验证环节本身设计为"未知缺陷走人审+工单闭环"，不追求识别率 |
| 存量线+增量线并发写金标 | Orchestrator 串行化 + 乐观锁 version（TC-AIG-009 覆盖） |
