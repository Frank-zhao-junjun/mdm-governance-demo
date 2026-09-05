# SPEC: AI 增强型数据治理 Demo（六要素正式版）

| 版本 | 阶段 | 关联 |
|------|------|------|
| v1.0 | Draft | 蓝图 v3（2026-08-25-ai-native-dg-demo-design.md）→ 战术化 |

> 本文档由 v3 蓝图自审产出：补 Success Metrics / User Stories / Acceptance Criteria 三大缺口，集中 Non-Goals，保留 Constraints。设计与决策依据见蓝图 v3。

## Problem Statement

- 现状：RalphLoop 已有物料申请、校验、重复识别（ILIKE）、编码生成、审批流、金标数据、BTP 分发，但治理靠人翻表，决策无证据链、无问责留痕。
- 对标 SAP MDG（DQM + Consolidation + Key Mapping + Replication），需要证明"确定性治理 + AI 建议增强"路线在核心环节有可演示的代差优势。
- 价值主张：**AI 提升人的判断效率，不替代人的治理责任。AI 也会错，系统的价值是让 AI 的错误可见、可拦、可追。**
- 用途：双目标，先内后外——对内立项论证（拿预算），对外售前 POC。载体为扩展现有 RalphLoop 平台（演示完即产品雏形）。

## Success Metrics（可量化验收）

| ID | 指标 | 目标值 | 验证方式 |
|----|------|--------|----------|
| S1 | 演示全流程时长 | ≤ 15 分钟（开场→增量线→裁决→冲突插曲→收尾） | 脚本走查计时 |
| S2 | 现场验证环节陌生数据闭环 | 5-10 条客户数据，0 条静默漏过（每条都有建议/裁决/工单承接） | 现场跑 + 工单台账核对 |
| S3 | 裁决卡片三件套齐全率 | 100%（证据链 + 风险标注 + 替代选项） | 抽查任意待办卡片 |
| S4 | 归并执行端点安全 | 未批准请求 100% 被拒（4xx） | API 测试 |
| S5 | B 类样例拦截 | 10.9 vs 8.8 同规格螺栓，L1 规则覆盖 LLM 建议，结论"不建议合并" | 演示走查 |
| S6 | 存量扫描性能 | 10,000 条金标 ≤ 5 分钟产出归并/整改工单 | 计时 |
| S7 | 问责可答 | 任意裁决可回答"当时依据什么批的"（证据快照 + trace_id + 模型版本） | 问责查询走查 |

## User Stories

- **US1（Owner）**：作为物料域业务 Owner，我能在 Copilot 工作台带着证据链裁决归并/整改建议，批准/驳回/改判全部留痕，以便 30 分钟做出有据可查的治理决策。
- **US2（Steward）**：作为数据管家，我能收到指派给我的质量/归并工单并闭环整改，以便存量+增量问题不静默堆积。
- **US3（审批链）**：作为审批链成员，我能看到跨事业部争议工单的升级路径并会签，以便权责冲突有正式裁决机制。
- **US4（演示讲解人）**：我能用治理驾驶舱开场 2 分钟展示全局态势（质量分/重复率/待办/Agent 活动流），以便建立治理全局观。
- **US5（售前顾问）**：我能用客户真实数据现场跑一遍流程（含未知缺陷的承接），以便展示"每个缺陷都被闭环处理"而非"发现率 100%"。

## Acceptance Criteria（可勾选）

- [ ] **AC-1** 增量批次 10 条提交后，标准校验 Agent 对每条输出"符合/不符 + 修正建议 + 证据"，且不改库（只读）
- [ ] **AC-2** 质量检核生成工单并指派 Steward；工单状态机 `draft→pending→approved/rejected→executing→done/failed` 全通，failed 可恢复
- [ ] **AC-3** 归并 Agent 产出候选簇 + 证据链 + 证据分级 L1/L2/L3，推荐但不合并
- [ ] **AC-4** 裁决卡片三件套齐全；高风险操作（归并执行/单位换算/属性修正）要求审批意见或二次确认
- [ ] **AC-5** 跨事业部争议样例走升级审批链 + 双方 Owner 会签 + 决策留痕
- [ ] **AC-6** 标准过时提示触发标准修订流程（而非只当校验工具）
- [ ] **AC-7** 工单超时自动升级：3 天→部门负责人，7 天→治理委员会
- [ ] **AC-8** B 类样例拦截：10.9 vs 8.8 同规格螺栓 → L1 规则覆盖 LLM 建议，明确"不建议合并"
- [ ] **AC-9** 归并执行端点对未批准请求返回 4xx；金标记录乐观锁 version 冲突处理正确
- [ ] **AC-10** 驾驶舱展示质量分/重复率/待办/Agent 活动流；批准后指标实时变化
- [ ] **AC-11** `agent_trace` 记录 trace_id、模型版本、输入摘要、证据引用、裁决快照；问责查询可答
- [ ] **AC-12** 现场验证：5-10 条陌生数据跑通"检核→建议→裁决→工单闭环"，0 静默漏过
- [ ] **AC-13** LLM 网关：超时 15s、重试 2 次、熔断降级 mock、token 成本上限告警

## Non-Goals（本期不做）

- 不做 AI 自动写库/自动归并/自动分发（决策 #10，任何写库一律人工确认）
- 不以 LLM 置信度分数作为任何分级依据（决策 #11，只用证据类型分级 L1/L2/L3）
- 不做多租户/分布式（demo 规模：单机/单租户/10 条每天）
- 不预埋 C 类缺陷、不假装能识别历史乱象（走人审 + 工单闭环 + 规则持续补充）
- 不做 LangGraph 等框架迁移（demo 验收后对照检查清单再评估，见蓝图 4.4）
- 不覆盖 BOM/供应商/客户/设备/组织域（物料域旗舰做深做透）

## Constraints

- **复用不动**：`audit_service`、审批流骨架、金标数据、BTP 分发、`duplicate_detector`（升级为规则通道）
- **表结构**：只加新表（`quality_ticket`/`merge_ticket`/`key_mapping`/`agent_trace`/`governance_owner`/`approval_evidence`），不改现有表结构语义
- **证据分级 L1/L2/L3 为唯一信任机制**：L1 规则命中（可一键采纳）/ L2 统计推断（带依据样本）/ L3 语义推断（永远标注"需人工确认"）
- **编排纪律**：所有 Agent 继承统一基类（错误处理/重试策略/trace 上报/日志格式）；失败模式清单前置（超时/幂等冲突/部分失败/上下文超限/LLM 不可用）
- **可靠性**：幂等键 `request_id`；金标 `version` 乐观锁；不做自动回滚（回滚本身是决策）
- **LLM 网关**：默认 mock 模式，真实通道可切换（DeepSeek API，环境变量注入）；超时 15s / 重试 2 / 熔断降级 mock
- **技术栈**：后端 FastAPI + SQLAlchemy 2.0 + Pydantic v2（uv 管理）；前端 React 19 + TypeScript + recharts（pnpm 管理）；禁止生成 package-lock.json
- **安全**：所有用户输入校验；敏感数据（Token/Key）禁止入日志；数据库参数化查询
- **文档链**：`规划迭代.md（战略）→ 本 SPEC（战术）→ TC.md（测试）→ tasks.md（跟踪）`

## Open Questions

1. LLM 真实通道默认用 DeepSeek API（与 Hermes 同源），还是其他供应商？（默认：DeepSeek，`LLM_MODE=mock|deepseek` 切换）
2. demo 种子数据生成放 `scripts/seed_demo_data.py`，用固定随机种子保证可复现？（默认：是）
3. 权责冲突故事线的工厂 A/B 与 Owner 姓名是否用真实企业代号？（默认：虚构代号，如 FA/ FB、张/李 Owner）

## 六大实现域（HOW 脚手架，详见 plan.md）

- Objective：按本 SPEC 六要素 + 蓝图 4.5 技术改动点落地
- Commands：`uv run pytest` / `pnpm build` / `pnpm dev` / `uvicorn app.main:app`
- Structure：`app/skills/`（6 Skill 纯函数）、`app/agents/`（3 Agent + Orchestrator）、`app/core/llm_gateway.py`、`scripts/seed_demo_data.py`
- Testing：Skill 层单测（纯函数）+ Agent 层集成测试 + API 测试，挂 TC.md
- Boundaries：任何写库走人工确认；LLM 输出永远带证据级别；凭证走环境变量
