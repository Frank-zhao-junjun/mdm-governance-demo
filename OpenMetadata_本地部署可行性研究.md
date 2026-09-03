# OpenMetadata 本地部署可行性研究

日期：2026-05-06

## 结论

OpenMetadata 可以在本地部署。官方提供两类 Docker 路线：

1. **本地快速体验 / PoC**：使用官方 Release 中的 `docker-compose.yml` 或 `docker-compose-postgres.yml`，一次性启动 OpenMetadata Server、数据库、Elasticsearch 和 Ingestion/Airflow。
2. **较接近生产的 Docker 部署**：使用 `docker-compose-openmetadata.yml`，OpenMetadata Server 单独运行，数据库、搜索引擎、编排服务使用外部或独立部署组件。

对当前这台 Windows 机器的检查结果是：**暂时不能直接启动 OpenMetadata**，因为当前环境未检测到 Docker 命令，WSL2 虽然默认版本为 2，但没有安装任何 Linux 发行版。

## 官方要求摘要

OpenMetadata 本地 Docker 快速部署要求：

- Docker 20.10.0 或更高版本。
- Docker Compose v2.1.1 或更高版本；生产 Docker 部署文档中要求 v2.2.3 或更高。
- Docker 至少分配 **6 GiB 内存** 和 **4 vCPU**。
- Windows 推荐路径：WSL2 + Ubuntu + Docker Desktop。
- 默认 OpenMetadata UI 地址：`http://localhost:8585`。
- 默认 OpenMetadata 管理员账号：`admin@open-metadata.org` / `admin`。
- 默认 Airflow 地址：`http://localhost:8080`，账号：`admin` / `admin`。

## 当前机器环境检查

已检查：

- `docker`：未在 PATH 中检测到。
- `docker-compose`：未在 PATH 中检测到。
- `docker compose`：不可用，因为 `docker` 命令不存在。
- `wsl --status`：默认版本为 2。
- `wsl --list --verbose`：没有已安装的 Linux 发行版。

因此，当前机器需要先安装 Docker Desktop 和 WSL Linux 发行版，之后才能部署。

## 推荐部署路线

### 路线 A：本地 PoC / 演示环境

适合目的：验证 OpenMetadata 功能、做物料主数据治理 PoC、演示元数据采集、血缘、术语表、数据资产目录等能力。

建议组件：

- OpenMetadata Server
- PostgreSQL 或 MySQL
- Elasticsearch
- OpenMetadata Ingestion / Airflow

推荐选择：优先使用 PostgreSQL 版 Compose 文件，便于后续和企业常见开源栈衔接。

执行思路：

```powershell
mkdir openmetadata-docker
cd openmetadata-docker
curl.exe -L -o docker-compose-postgres.yml https://github.com/open-metadata/OpenMetadata/releases/download/1.12.6-release/docker-compose-postgres.yml
docker compose -f docker-compose-postgres.yml up --detach
```

启动后访问：

- OpenMetadata：`http://localhost:8585`
- Airflow：`http://localhost:8080`

停止服务：

```powershell
docker compose -f docker-compose-postgres.yml stop
```

清理容器但保留数据卷：

```powershell
docker compose -f docker-compose-postgres.yml down
```

清理容器并删除数据卷：

```powershell
docker compose -f docker-compose-postgres.yml down --volumes
```

注意：`--volumes` 会删除本地数据，只适合重置 PoC。

### 路线 B：生产化前验证环境

适合目的：验证企业内网部署、权限、数据库、搜索引擎、备份、监控、集成策略。

建议方式：

- OpenMetadata Server 使用官方 `docker-compose-openmetadata.yml`。
- 数据库使用外部 MySQL 或 PostgreSQL。
- 搜索引擎使用外部 Elasticsearch 或 OpenSearch。
- Ingestion 编排可使用官方 Airflow，也可对接已有 Airflow、Dagster、Prefect 或其他调度系统。

该路线配置项更多，但更接近真实企业部署，不建议作为第一次本地尝试。

## Windows 本机准备步骤

1. 安装 WSL2 Linux 发行版，例如 Ubuntu：

```powershell
wsl --install Ubuntu-22.04
```

如果系统提示需要重启，先重启。

2. 安装 Docker Desktop for Windows，并启用 WSL2 backend。

3. 在 Docker Desktop 中配置资源：

- Memory：至少 6 GiB，建议 8 GiB 或更高。
- CPUs：至少 4 vCPU。

4. 在 PowerShell 中验证：

```powershell
docker --version
docker compose version
wsl --list --verbose
```

5. 下载官方 Compose 文件并启动。

## 和制造业物料治理 PoC 的适配性

OpenMetadata 本地部署适合做制造业物料治理 PoC，尤其适合验证以下内容：

- 物料主数据资产目录：物料表、BOM、供应商、采购、库存、质量等数据资产登记。
- 元数据采集：从数据库、数据仓库、BI、API 或文件系统采集技术元数据。
- 业务术语表：建立物料、物料组、计量单位、规格型号、品牌、供应商编码等术语。
- 数据所有权：给数据资产分配 Owner、Reviewer、Domain、Team。
- 数据质量规则：配置字段完整性、唯一性、格式、枚举值、引用一致性等校验。
- 血缘分析：展示从 ERP/MES/PLM/SRM 到数仓、报表或 AI 应用的数据流向。
- 协作治理：支持资产评论、任务、标签、认证状态、文档说明。

但要注意：OpenMetadata 更偏“元数据治理 / 数据目录 / 数据质量 / 血缘 / 协作治理”，不是 MDM 主数据中台本身。若要做物料编码申请、审批、合并、Golden Record、编码规则自动生成等完整 MDM 流程，需要和业务系统、低代码流程、MDM 工具或自研服务集成。

## 风险与注意事项

- 本地 Docker 快速部署不适合直接生产使用。
- 初次拉取镜像可能较慢，需要稳定访问 Docker Hub / GitHub Release。
- Elasticsearch 会占用较多内存，Docker 资源不足时容易启动失败。
- Windows + WSL2 场景可能遇到卷权限问题，官方建议可在 WSL 中配置 `/etc/wsl.conf` 的 automount 选项。
- 默认账号密码只能用于本地 PoC，正式环境必须配置安全认证、密钥、HTTPS、备份和访问控制。
- 如果企业内网无法访问外部镜像仓库，需要提前准备私有镜像仓库或离线镜像包。

## 建议下一步

建议先按 PoC 路线做一个本地环境：Docker Desktop + WSL2 + PostgreSQL Compose。部署成功后，再导入一组制造业物料样例数据，验证术语表、数据资产目录、血缘、质量规则和治理协作流程。

如果目标是给客户或内部领导演示，可以把 OpenMetadata 与现有工作区里的物料治理资料结合，整理成一套“本地 PoC 演示脚本”。
