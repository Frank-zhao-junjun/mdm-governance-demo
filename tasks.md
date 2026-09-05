# tasks.md — AI 增强型数据治理 Demo（跟踪）

> ⚠️ **状态：T1-T8 已全部完成并合入 main（commit `4862b7d`），本表转为历史跟踪表**
>
> - **引用失效**：下表「依据」的 `SPEC 2026-08-26-ai-enhanced-dg-demo-spec.md` 与 `plan.md 2026-08-26-ai-enhanced-dg-demo-plan.md` **在本仓库中不存在**（`find` 全库无匹配）。T1-T8 的正式范围依据现为 `docs/spec-data-governance.md` **v1.4 §1.4.1「AI 辅助治理层」**（2026-09-02 由 Frank 拍板补入，承认 agents / skills / llm_gateway 与 copilot / governance / owners / evidence 四路由为正式范围）。
> - **TC 挂钩**：表中 `AIG-*` / `MAP-*` 编号出自 `TC.md`，该文件已单独标注为**非当前验收基线**（旧范围 backlog）。
> - **当前验收基线**：SPEC v1.4 §7 各阶段内联的 `**验收**：` 判据，由根目录 `e2e_test.py`（56 项断言）与 `backend/tests/`（310 个用例）覆盖。进度与实测证据见 `WORKLOG.md`。

> 依据: SPEC 2026-08-26-ai-enhanced-dg-demo-spec.md + plan.md 2026-08-26-ai-enhanced-dg-demo-plan.md
> 状态标记: ✅ 完成 / ⏳ 进行中 / 🔮 待开始

| # | 任务 | 依赖 | TC 挂钩 | 状态 |
|---|------|------|---------|------|
| T1 | 新表模型（六张表: quality_ticket/merge_ticket/key_mapping/agent_trace/governance_owner/approval_evidence） | — | AIG-002/009 | ✅ |
| T2 | LLM 网关 app/core/llm_gateway.py（mock/deepseek 切换、熔断降级、token 告警） | — | AIG-013 | ✅ |
| T3 | Skill 层 app/skills/（naming/attribute/unit/quality_rule/duplicate_match/merge_executor，证据分级 L1/L2/L3） | — | AIG-001/002/003/006/008/009 | ✅ |
| T4 | Agent 层 app/agents/（BaseAgent + Standard/Quality/Dedup + Orchestrator，幂等/SLA 升级/串行化） | T1,T2,T3 | AIG-001/002/003/007/011 | ✅ |
| T5 | 种子数据 scripts/seed_demo_data.py（10k 金标 + A/B 类缺陷 + 权责冲突场景，固定随机种子） | T1,T3 | AIG-003/005/008 | ✅ |
| T6 | API 层（/api/copilot/* /api/governance/* /api/owners/* /api/evidence/*，执行端校验已批准） | T4 | AIG-004/009/010/011 | ✅ |
| T7 | 前端（Copilot 裁决工作台/治理驾驶舱/Agent 活动流/权责冲突视图） | T6 | AIG-004/010/011 | ✅ |
| T8 | 端到端验证 + 演示剧本走查（test_demo_e2e.py + demo-script.md，SPEC S1-S7 核对） | T5,T6,T7 | AIG-012 + 全回归 | ✅ |

## 文档链状态

| 文档 | 路径 | 状态 |
|------|------|------|
| 战略 | 制造业基础数据治理迭代规划.md | ✅ 已有 |
| 蓝图 | docs/superpowers/specs/2026-08-25-ai-native-dg-demo-design.md | ✅ v3 定稿 |
| 战术 SPEC | docs/superpowers/specs/2026-08-26-ai-enhanced-dg-demo-spec.md | ✅ v1.0 自审产出 |
| 测试 | TC.md（F 区 TC-AIG-001~013） | ✅ 已补 |
| 实施计划 | docs/superpowers/plans/2026-08-26-ai-enhanced-dg-demo-plan.md | ✅ 已出 |
| 跟踪 | tasks.md（本文件） | ✅ 已建 |
