# OpenMetadata 参考评估

> ⚠️ **状态：历史预研文档（2026-08-23），非当前集成方案**
>
> 两点已过期：
>
> 1. **评估口径过期**：本文按「物料主数据申请、审批、编码、去重、金标数据」的旧范围评估 OpenMetadata 的替代性。按 `docs/spec-data-governance.md` v1.4 §1.4，本平台现在**只做存量数据治理与数据质量管理**，申请/审批/金标/分发均已移交上游业务系统，这些对比维度不再适用。
> 2. **代码引用失效**：文中引用的 `backend/app/api/applications.py` 已删除；OpenMetadata 集成代码本身（`services/openmetadata_sync.py`、`OM_ENABLED` / `OPENMETADATA_HOST` / `OPENMETADATA_TOKEN` 配置）也已从代码库移除，当前无任何 OM 调用路径。
>
> 保留价值仅剩：开放元数据标准、血缘与数据质量观测的**外部参考资料**。若要重新评估集成，需按 v1.4 范围重做，不要直接沿用本文结论。

> 评估日期：2026-08-23
> 项目：RalphLoop MDM Governance
> 结论性质：架构参考与技术预研结论，不等同于上线选型批准

## 一句话结论

OpenMetadata 值得参考，但只适合作为本项目的外部元数据目录、开放元数据标准、血缘与数据质量观测参考；不适合作为物料主数据申请、审批、编码、去重或 金标数据 的替代系统。

建议采用“RalphLoop 负责业务主数据治理闭环，OpenMetadata 负责元数据上下文与数据资产发现”的边界。是否实际部署，应先做小规模 PoC，而不是直接把当前同步代码投入生产。

## 项目现状核对

- 项目的核心领域模型是物料申请、三级分类、属性模板、编码规则、审批、金标数据、BTP 发布和审计日志，见 `backend/app/models.py`。
- 发布接口的顺序是创建 金标数据、调用 BTP Mock、调用 `OpenMetadataSync.sync_material()`、记录质量测试结果，见 `backend/app/api/applications.py`。
- 当前 `sync_material()` 只做健康检查、等待 0.3 秒并生成 `RalphLoop.Material.<material_code>` 形式的 FQN，没有调用 OpenMetadata 的实体创建或更新 API，见 `backend/app/services/openmetadata_sync.py`。
- 当前 `run_quality_tests()` 是在 RalphLoop 进程内对物料编码、名称长度和分类 ID 做本地布尔判断，并非通过 OpenMetadata 执行或回传真实质量测试，见 `backend/app/services/openmetadata_sync.py`。
- 元数据治理页面中的 catalog、lineage 和 quality_tests 主要由 RalphLoop 数据库及审计日志拼装；OpenMetadata 节点目前是外部系统标识，不代表已经同步了真实实体和真实血缘，见 `backend/app/api/metadata_governance.py`。
- 项目依赖中没有 OpenMetadata SDK 或 ingestion 依赖，只有通用 `requests`；这进一步说明当前接入是 HTTP 健康检查/模拟适配层，而不是完成的生产集成，见 `backend/requirements.txt`。

## 为什么值得参考

### 1. 元数据边界比当前项目更完整

OpenMetadata 官方文档将其定位为统一的数据发现、血缘和治理平台，覆盖表、仪表板、流水线、主题、模型等资产，以及查询使用、血缘、数据画像和质量测试。这个范围适合用来反思本项目的“元数据治理”是否只展示了 金标数据，而没有建立数据资产、来源、责任人、术语和消费关系。

官方资料：

- https://docs.open-metadata.org/latest/
- https://docs.open-metadata.org/latest/connectors/ingestion

### 2. Schema-first、API-first 的设计值得借鉴

OpenMetadata 官方标准以 JSON Schema 定义实体和类型，并以 REST API 暴露资源。官方 API 文档明确说明实体资源使用集合 URI、实例 URI、camelCase 字段，并且未知字段不会被静默丢弃。对本项目而言，最有价值的参考不是照搬实体表，而是建立稳定的元数据契约、版本化和扩展属性规则。

官方资料：

- https://docs.open-metadata.org/latest/main-concepts/metadata-standard
- https://docs.open-metadata.org/latest/main-concepts/metadata-standard/apis

### 3. 血缘、质量和治理能力能补足未来方向

OpenMetadata 的官方数据质量文档覆盖质量测试、画像、告警、事件管理和异常检测；治理文档覆盖 Glossary、Classification、Domains/Data Products、角色与策略。它可以帮助本项目把“质量校验”和“治理”从一次申请时的同步判断，扩展为可持续观测、责任分派和影响分析。

官方资料：

- https://docs.open-metadata.org/latest/how-to-guides/data-quality-observability
- https://docs.open-metadata.org/latest/how-to-guides/data-governance

### 4. SAP 相关能力可以参考，但不能过度解读

官方 SAP HANA 连接器页面列出 Metadata、Profiler、Data Quality、Lineage 等能力，同时明确要求 SYS、`_SYS_BIC`、`_SYS_REPO` 等权限。官方 SAP ERP 连接器页面则显示其当前重点是通过 CDS Views/OData/REST 暴露并采集 Metadata，并将 Data Profiler、Data Quality、Lineage 等列为不可用能力。

这说明 OpenMetadata 对 SAP 生态的适配是“按连接器和具体对象逐项验证”，不能简单地说“支持 SAP，所以能覆盖物料主数据治理”。

官方资料：

- https://docs.open-metadata.org/latest/connectors/database/sap-hana
- https://docs.open-metadata.org/latest/connectors/database/sap-erp

## 为什么不能直接替代本项目

| 能力 | RalphLoop 当前职责 | OpenMetadata 更擅长的职责 | 判断 |
|---|---|---|---|
| 物料申请与草稿 | 有 | 无明确替代定位 | 保留在 RalphLoop |
| 三级分类与属性模板 | 有 | 可提供标签、分类、术语参考 | RalphLoop 为权威 |
| 重复预检 | 有 | 不是其核心主数据匹配流程 | 保留在 RalphLoop |
| 编码规则与流水号 | 有 | 不适合作为 ERP 物料编码引擎 | 保留在 RalphLoop |
| 管理员/部门审批 | 有 | 有治理协作，但不是本项目审批流程替代 | 保留在 RalphLoop |
| 金标数据 生命周期 | 有 | 可接收或关联资产元数据 | RalphLoop 为权威 |
| 元数据目录、搜索、发现 | 当前为简化视图 | 核心强项 | 值得集成或参考 |
| 技术血缘 | 当前为业务流程边 | 核心强项 | 值得参考，需重新定义数据边界 |
| 数据质量观测 | 当前为同步时本地规则 | 支持持续测试、画像、告警和观测 | 可补强，但不能假称当前已接入 |
| 业务术语、标签、责任人 | 当前较弱 | 核心治理能力之一 | 值得参考 |
| 生产级权限、升级、运行 | 本项目较轻量 | 需要 Docker/Compose、存储、搜索和 ingestion 运行组件 | 需评估运维成本 |

## 主要风险

1. **概念错位风险**：OpenMetadata 的典型资产是数据平台中的表、列、仪表板、流水线等；物料主数据本身可以作为自定义元数据或业务资产关联，但申请审批、主数据匹配和 ERP 生效仍需由专门系统负责。
2. **当前“同步成功”是模拟成功**：开启 `OM_ENABLED` 后，项目只验证 `/v1/health-check`，随后返回本地生成的 FQN。当前状态字段 `om_synced=true` 不能作为真实 OpenMetadata 实体存在的证据。
3. **质量结果归属风险**：项目把本地校验结果标记为 OpenMetadata 质量测试，容易造成用户误判。接入前必须区分“RalphLoop 业务规则结果”和“OpenMetadata 资产质量测试结果”。
4. **同步一致性风险**：发布流程是同步串行调用，失败重试、幂等、超时、死信、补偿和外部日志闭环尚未形成。OpenMetadata 连接不可用时，是否阻断 金标数据 发布也没有明确业务策略。
5. **安全与运维成本**：官方本地 Docker 文档要求至少 6 GiB 内存和 4 vCPU，并包含服务端、数据库、搜索和 ingestion 等组件。Windows 环境还依赖 WSL2 与 Docker Desktop。生产部署需要单独评估资源、备份、升级、网络隔离、凭据管理和权限。
6. **版本与连接器差异风险**：官方连接器页面同时标识 PROD/BETA；SAP ERP 与 SAP HANA 的能力清单差异明显。必须锁定 OpenMetadata 版本、目标 SAP 产品、接口方式和所需元数据粒度后再做结论。
7. **厂商商业化边界风险**：官方站点同时提供 OpenMetadata OSS 与 Collate 托管/商业服务，并有功能对比入口。需要在采购或长期运行前单独核查 OSS 许可、商业功能边界、支持模式和升级路径。

官方部署资料：

- https://docs.open-metadata.org/latest/quick-start/local-docker-deployment
- https://github.com/open-metadata/OpenMetadata
- https://open-metadata.org/

## 建议的参考方式

### 第一阶段：只参考模型和界面，不引入运行时依赖

参考 OpenMetadata 的实体、关系、Glossary、Classification、Lineage、Quality Test、Versioning 和 API 组织方式，先在 RalphLoop 内完善自己的元数据契约。不要因为页面上出现 OpenMetadata 节点，就把它当成真实同步完成。

### 第二阶段：做窄范围 PoC

建议选一条真实链路：一个物料域、一个 SAP HANA 或 SAP ERP 数据源、少量 金标数据s，验证以下问题：

- 物料 金标数据 在 OpenMetadata 中应映射成什么实体，还是仅作为业务资产/自定义实体关联；
- FQN、唯一键、更新、删除/失效、版本与回滚如何定义；
- 分类、属性模板、业务术语、责任人和敏感性标签如何映射；
- 申请系统、RalphLoop 数据库、SAP/BTP、OpenMetadata 之间的血缘粒度是什么；
- OpenMetadata 质量测试与 RalphLoop 申请校验如何分层，结果如何回传且不混淆；
- 连接失败时采用异步重试、补偿队列还是允许业务发布继续；
- SAP 接口权限、网络隔离和数据脱敏是否满足要求。

### 第三阶段：只有在 PoC 通过后再决定集成深度

推荐的目标边界是：

- RalphLoop：物料主数据业务流程、规则、审批、金标数据 和 ERP 生效状态的权威系统；
- OpenMetadata：技术/业务元数据目录、跨系统搜索、术语与分类协作、血缘、观测和面向 AI 的上下文层；
- 集成层：独立的、可重试且幂等的同步适配器，不能把 HTTP 健康检查当作同步完成。

## 最终判断

- **作为参考框架：值得，优先级高。** 尤其值得参考元数据标准、实体关系、目录/搜索、血缘、质量观测、术语与治理工作台。
- **作为本项目的直接底座：目前不建议直接决定。** 当前项目的核心问题是主数据业务治理，不是缺一个通用数据目录；而且现有 OpenMetadata 接入仍是模拟层。
- **作为生产外部组件：有条件值得。** 前提是 SAP/数据源适配、实体映射、权限、运行资源、失败补偿和 OSS/商业边界都通过 PoC 与架构评审。

在没有完成上述 PoC 前，不应对外宣称“本项目已完成 OpenMetadata 集成”或“OpenMetadata 已执行物料质量测试”。
