# RalphLoop MDM Governance - 代码 QA Review 报告

**审查日期**: 2026-05-06
**审查范围**: 后端 (FastAPI + SQLAlchemy) + 前端 (React + TypeScript)
**审查维度**: 架构 / 安全 / 代码质量 / 功能符合度 / 性能 / 可维护性
**严重级别定义**: 🔴 Critical (必须修复) / 🟠 Major (强烈建议修复) / 🟡 Minor (建议优化) / 🟢 Info (参考)

---

## 一、架构层审查

### 1.1 整体架构评估 ✅ 良好

| 维度 | 评估 | 说明 |
|------|------|------|
| 三层解耦 | ✅ | API → Service → CRUD → Model，层次清晰 |
| 职责分离 | ✅ | 校验、查重、编码、审计各自独立服务 |
| 状态机 | ✅ | ApplicationStatus 枚举定义完整，状态流转有校验 |
| 审计追踪 | ✅ | 每步骤生成唯一 step_id (SQ-XXXX-S1)，符合需求 |

### 1.2 架构问题

#### 🟠 Major: 数据库连接硬编码，无法切换 PostgreSQL

**位置**: `backend/app/core/database.py:7`

```python
# 当前代码
SQLALCHEMY_DATABASE_URL = "sqlite:///./mdm_governance.db"
```

**问题**: 
- 虽然 `.env` 配置了 `SQLALCHEMY_DATABASE_URL=postgresql://...`，但代码完全忽略了环境变量
- SQLite 的 `check_same_thread=False` 在生产环境有并发风险
- 注释说 "Switch to PostgreSQL in production"，但代码未实现切换机制

**建议修复**:
```python
from app.core.config import settings

# 使用配置中的 DATABASE_URL
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,  # 生产环境推荐
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
```

#### 🟡 Minor: 缺少数据库连接池配置

**位置**: `backend/app/core/database.py`

SQLite 无连接池限制，但切到 PostgreSQL 后需要配置 `pool_size`、`max_overflow`、`pool_recycle` 等参数。

---

## 二、安全审查

### 2.1 认证与授权 🔴 Critical

#### 🔴 Critical: 完全缺少用户认证

**位置**: `backend/app/api/applications.py:20`

```python
def get_current_user(request: Request):
    return {"id": "user001", "name": "张三", "department": "研发部", "role": "applicant"}
```

**风险**:
- 任何人都可以调用 API 提交申请、审批、发布
- `admin_approve` 和 `dept_approve` 使用 mock 用户，无真实身份验证
- 无法追踪真实操作人，审计日志失去意义

**影响**: 生产环境**绝对不可部署**

**建议修复路径**:
1. 短期: 添加 JWT Bearer Token 中间件 + 角色校验装饰器
2. 长期: 集成企业 SSO (LDAP/AD/OAuth2)

```python
# 示例修复
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    
def require_role(roles: list):
    def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker

# 使用
@router.post("/{app_id}/admin-approve")
def admin_approve(
    ...,
    user: dict = Depends(require_role(["admin", "data_admin"]))
):
    ...
```

#### 🟠 Major: CORS 开放所有来源

**位置**: `backend/app/main.py`

```python
allow_origins=["*"]  # 允许任意域名访问
```

**风险**: 生产环境中应限制为特定域名

### 2.2 数据安全 🟡 Minor

#### 🟡 Minor: 未使用参数化查询（潜在风险低）

**位置**: `backend/app/crud.py:generate_app_no`

```python
count = db.query(models.MaterialApplication).filter(
    models.MaterialApplication.app_no.like(f"{prefix}%")
).count()
```

虽然 SQLAlchemy ORM 会自动转义，但使用 `like()` 配合字符串拼接仍属于不良实践。不过 SQLite 注入风险在此场景下极低。

#### 🟢 Info: 密码/Token 未加密存储

**位置**: `.env`

```
OPENMETADATA_TOKEN=eyJraWQiOiJHYjM4OWEtOWY3Ni1nZGpzLWE5MmotMDI0MmJrOTQzNTYiLCJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

`.env` 文件本身需要文件系统权限保护。生产环境应使用 Vault/AWS Secrets Manager 等密钥管理服务。

### 2.3 输入验证

#### 🟡 Minor: 部分端点缺少输入校验

**位置**: `backend/app/api/applications.py:32`

```python
def list_applications(
    status: str = None,   # 未校验枚举值
    skip: int = 0,       # 未校验负数
    limit: int = 100,    # 未校验上限
    db: Session = Depends(get_db)
):
```

`status` 传入任意字符串不会报错，只是查询无结果。应使用 Pydantic 枚举校验。

---

## 三、代码质量审查

### 3.1 Python 代码规范

#### 🟡 Minor: `import re` 未使用

**位置**: `backend/app/services/material_validator.py:2`

```python
import re  # 导入了但代码中没有使用正则表达式
```

#### 🟡 Minor: `or_, func` 未使用

**位置**: `backend/app/services/duplicate_detector.py:4`

```python
from sqlalchemy import or_, func  # 导入了但未使用
```

#### 🟡 Minor: 命名不一致

**位置**: `backend/app/crud.py:14`

```python
def create_classification(db: Session, data: schemas.ClassificationCreate)
```

参数名 `data` 过于笼统。建议改为 `classification_data` 或 `payload`。

### 3.2 事务管理 🟠 Major

#### 🟠 Major: `increment_seq` 无事务隔离

**位置**: `backend/app/crud.py:134`

```python
def increment_seq(db: Session, rule_id: str) -> int:
    rule = get_code_rule(db, rule_id)
    if not rule:
        return 0
    rule.current_seq += 1
    db.commit()
    return rule.current_seq
```

**问题**: 高并发场景下，`increment_seq` 的 `SELECT → UPDATE` 非原子操作，会导致**重复编码**（两个请求同时读取同一 seq，各加1，结果相同）。

**修复方案**:
```python
from sqlalchemy import text

def increment_seq(db: Session, rule_id: str) -> int:
    # 使用数据库原子操作
    result = db.execute(
        text("UPDATE code_rules SET current_seq = current_seq + 1 WHERE id = :id RETURNING current_seq"),
        {"id": rule_id}
    )
    db.commit()
    return result.scalar()
```

或 SQLite 兼容版本:
```python
def increment_seq(db: Session, rule_id: str) -> int:
    db.execute(text("UPDATE code_rules SET current_seq = current_seq + 1 WHERE id = :id"), {"id": rule_id})
    db.commit()
    result = db.execute(text("SELECT current_seq FROM code_rules WHERE id = :id"), {"id": rule_id})
    return result.scalar()
```

#### 🟠 Major: `submit_application` 多步骤非原子提交

**位置**: `backend/app/api/applications.py:110`

```python
# Step 1: Validation
validator.validate(...)
# Step 2: Duplicate check
detector.check(...)
# Step 3: Code generation
generator.generate(...)
# 多次 db.commit() 穿插其中
```

**问题**: 如果校验通过后、编码生成前进程崩溃，数据库处于不一致状态（校验通过但没编码）。

**修复**: 将整个 submit 操作包裹在事务中:
```python
@router.post("/{app_id}/submit")
def submit_application(...):
    try:
        # ... 所有操作 ...
        db.commit()  # 只提交一次
    except Exception:
        db.rollback()
        raise
```

### 3.3 异常处理

#### 🟠 Major: `OpenMetadataSync._api_call` 吞异常

**位置**: `backend/app/services/openmetadata_sync.py:36`

```python
except requests.exceptions.RequestException as e:
    return {"success": False, "error": str(e)}
```

**问题**: 将异常转换为字典返回，调用方可能忽略错误继续执行。

**修复**: 显式抛出异常或返回结果对象:
```python
class SyncResult:
    success: bool
    error: Optional[str]
    data: Optional[dict]
```

#### 🟡 Minor: 多处使用裸 `alert()` 作为错误处理

**位置**: `frontend/src/pages/NewApplication.tsx:63`

```typescript
alert('草稿已保存');
```

**位置**: `frontend/src/pages/ApplicationDetail.tsx`

多处使用 `alert()` 和 `window.location.reload()`，用户体验差。

**建议**: 使用 Toast/Sonner 组件替代 alert。

---

## 四、功能符合度审查（vs PRD / 设计文档）

### 4.1 已实现 ✅

| PRD 需求 | 实现状态 | 验证 |
|---------|---------|------|
| 两级分类体系（大类+小类） | ✅ | `MaterialClassification` 模型，`level` 字段 |
| 分类属性模板（差异化字段） | ✅ | `AttributeTemplate` + `field_type` 支持 text/number/select/date |
| 编码规则引擎 | ✅ | `CodeGenerator` 支持 `{大类}/{小类}/{流水}` 模板 |
| 草稿 → 提交 → 校验 → 查重 | ✅ | `submit_application` 4 步骤 |
| 双审批（管理员+部门） | ✅ | `PENDING_ADMIN` → `PENDING_DEPT` 状态机 |
| Golden Record 创建 | ✅ | `create_golden_record` + 版本控制 |
| BTP 发布（Mock） | ✅ | `BTPMockService` + `btp_published` 标记 |
| OpenMetadata 同步接口 | ✅ | `OpenMetadataSync` 类（需配置 OM 后启用） |
| 全链路审计（step_id） | ✅ | `AuditService` 生成 `SQ-XXXX-S1` 格式 |
| 外部系统交互日志 | ⚠️ | 模型定义存在但 API 未暴露使用 |

### 4.2 未实现或偏差 🟠

#### 🟠 Major: 缺少 "撤销" 和 "修订" 功能

**PRD 要求**: `Material Revocation` (撤销) 和 `Material Revision` (修订)

**当前状态**: 状态机定义了 `REJECTED` 但没有 `REVOKE` 操作；版本控制字段 (`version`, `revision`) 存在但无修订 API。

**缺失 API**:
- `POST /api/applications/{id}/revoke` - 撤销已发布物料
- `POST /api/applications/{id}/revise` - 发起修订（创建新版本）
- `GET /api/golden-records/{id}/versions` - 查看版本历史

#### 🟠 Major: 编码规则未与 PRD 完全一致

**PRD 定义**:
```
{A}-{B}-{NNNNN}  → 大类(3位)+中类(2位)+流水(5位)
```

**当前实现**:
```python
# code_generator.py
replacements = {
    "{大类}": parent_code or "00",
    "{小类}": classification.code,  # 注意这里直接用小类 code，但 PRD 要求 3+2 位
    "{流水}": f"{seq:05d}",
}
```

**问题**: 
1. PRD 要求大类 3 位、中类 2 位，但种子数据 `code="01"` (2位)
2. 编码格式未强制校验 3+2+5 的长度
3. 无 "可选分隔符" 支持

#### 🟡 Minor: 属性模板缺少 `field_type="date"` 的前端渲染

**位置**: `frontend/src/pages/NewApplication.tsx`

前端只处理了 `select`、`number`、`text`，未处理 `date` 和 `boolean`。

#### 🟡 Minor: Dashboard 统计粒度不足

**PRD 要求**: 按部门/状态/时间段的统计

**当前实现**: 仅总数量统计，无分组/趋势分析。

---

## 五、性能审查

### 5.1 N+1 查询问题 🟠 Major

#### 🟠 Major: `DuplicateDetector.check()` 全表扫描

**位置**: `backend/app/services/duplicate_detector.py:30`

```python
gr_list = self.db.query(models.GoldenRecord).filter(
    models.GoldenRecord.status == models.GoldenRecordStatus.ACTIVE
).all()  # 加载所有 GR 到内存！
```

**问题**: 当 Golden Record 达到 10 万条时，每次提交都会加载全表到 Python 内存做字符串匹配。

**修复**: 使用数据库层面的相似度查询:
```python
# PostgreSQL 使用 trigram 相似度
from sqlalchemy import func, text

similar = self.db.query(models.GoldenRecord).filter(
    models.GoldenRecord.status == models.GoldenRecordStatus.ACTIVE,
    func.similarity(models.GoldenRecord.material_name, material_name) > 0.6
).order_by(func.similarity(models.GoldenRecord.material_name, material_name).desc()).limit(5).all()
```

或 SQLite 使用 `LIKE`:
```python
keyword = f"%{material_name[:5]}%"  # 取前5字符做前缀匹配
similar = self.db.query(models.GoldenRecord).filter(
    models.GoldenRecord.status == models.GoldenRecordStatus.ACTIVE,
    models.GoldenRecord.material_name.ilike(keyword)
).limit(10).all()
```

### 5.2 缺少分页

#### 🟡 Minor: `GoldenRecords.list()` 无分页

**位置**: `backend/app/api/golden_records.py`

```python
def list_golden_records(skip: int = 0, limit: int = 100, ...)
```

虽然接口定义了 `skip/limit`，但前端调用时未传递分页参数，默认只显示 100 条。

---

## 六、前端代码审查

### 6.1 TypeScript 类型安全

#### 🟡 Minor: 多处使用 `any` 类型

**位置**: `frontend/src/pages/Dashboard.tsx:11`

```typescript
const [stats, setStats] = useState<any>(null);
```

**位置**: `frontend/src/pages/NewApplication.tsx:20`

```typescript
const [classifications, setClassifications] = useState<any[]>([]);
```

**建议**: 定义统一的 API 响应类型:
```typescript
// src/types/api.ts
interface Application {
  id: string;
  app_no: string;
  material_name: string;
  status: 'draft' | 'pending_admin' | 'pending_dept' | 'approved' | 'rejected' | 'published';
  // ...
}
```

### 6.2 错误处理

#### 🟠 Major: API 错误未统一处理

**位置**: `frontend/src/pages/NewApplication.tsx:55`

```typescript
const res = await fetch('/api/applications/', { ... });
const data = await res.json();  // 如果 res.status !== 200，这里会解析错误 HTML
setAppId(data.id);  // 如果创建失败，data.id 为 undefined
```

**问题**: 未检查 `res.ok`，失败时仍尝试解析 JSON。

**修复**:
```typescript
const res = await fetch('/api/applications/', { ... });
if (!res.ok) {
  const err = await res.text();
  throw new Error(err);
}
const data = await res.json();
```

### 6.3 状态管理

#### 🟡 Minor: 表单状态与 URL 未同步

刷新页面后草稿丢失（`appId` 仅存在于 React state）。应使用 URL query param 或 localStorage 保存草稿 ID。

---

## 七、测试覆盖审查

### 7.1 E2E 测试

#### ✅ 良好: E2E 测试覆盖核心链路

34 个测试用例覆盖:
- 环境检查 (5)
- 主链路 (1)
- 申请与模板 (4)
- 校验与查重 (4)
- 编码与审批 (5)
- Golden Record (3)
- BTP 发布 (3)
- OpenMetadata (3)
- 审计追踪 (5)

**通过率**: 29/34 (85.3%)

#### 🟡 Minor: 缺失的测试场景

1. **并发测试**: 同时提交两个申请，验证编码唯一性
2. **边界测试**: 物料名称 200 字符上限、空属性值
3. **安全测试**: 未认证访问、越权审批
4. **性能测试**: 1000 条 GR 下的查重性能

### 7.2 单元测试

#### 🔴 Critical: 完全缺少单元测试

**现状**: 无 `pytest` 测试文件

**应补充**:
- `test_material_validator.py` - 各种输入组合的校验
- `test_duplicate_detector.py` - 相似度算法测试
- `test_code_generator.py` - 编码唯一性测试
- `test_audit_service.py` - step_id 生成唯一性测试

---

## 八、完整问题清单（按优先级排序）

| 优先级 | 类别 | 问题 | 文件 | 行号 |
|--------|------|------|------|------|
| 🔴 Critical | 安全 | 无用户认证/授权 | `applications.py` | 20-29 |
| 🔴 Critical | 安全 | CORS 开放所有来源 | `main.py` | 28 |
| 🔴 Critical | 质量 | 无单元测试 | - | - |
| 🟠 Major | 事务 | 编码流水号非原子操作 | `crud.py` | 134 |
| 🟠 Major | 事务 | submit 多步骤非原子 | `applications.py` | 110-210 |
| 🟠 Major | 性能 | 查重全表扫描 | `duplicate_detector.py` | 30 |
| 🟠 Major | 功能 | 缺少撤销/修订 API | - | - |
| 🟠 Major | 配置 | 数据库连接硬编码 | `database.py` | 7 |
| 🟠 Major | 前端 | API 错误未处理 | `NewApplication.tsx` | 55 |
| 🟡 Minor | 代码 | `import re` 未使用 | `material_validator.py` | 2 |
| 🟡 Minor | 代码 | `or_, func` 未使用 | `duplicate_detector.py` | 4 |
| 🟡 Minor | 代码 | 参数命名笼统 | `crud.py` | 多处 |
| 🟡 Minor | 前端 | 使用 `alert()` | 多个文件 | 多处 |
| 🟡 Minor | 前端 | `any` 类型泛滥 | 多个文件 | 多处 |
| 🟡 Minor | 功能 | Dashboard 统计粒度不足 | `dashboard.py` | - |
| 🟡 Minor | 功能 | 日期/布尔字段未渲染 | `NewApplication.tsx` | - |
| 🟡 Minor | 输入 | 缺少 skip/limit 校验 | `applications.py` | 32 |
| 🟢 Info | 架构 | 外部系统日志未暴露 API | `models.py` | - |
| 🟢 Info | 架构 | SQLite 仅适合演示 | `database.py` | - |

---

## 九、修复优先级建议

### Phase 1: 立即修复（上线前必须）
1. 添加 JWT 认证中间件 + 角色校验
2. 限制 CORS 来源
3. 修复 `increment_seq` 原子性（使用数据库原子更新）
4. 将 `submit_application` 改为单事务

### Phase 2: 短期修复（1-2 周内）
5. 修复数据库连接读取环境变量
6. 修复查重全表扫描（使用 LIKE 或 trigram）
7. 前端统一错误处理（替换 alert）
8. 补充单元测试（pytest）

### Phase 3: 中期增强（1 个月内）
9. 实现撤销/修订 API
10. 完善编码规则（3+2+5 格式校验）
11. 补充 Dashboard 统计维度
12. 定义 TypeScript 类型替代 any

---

## 十、总体评分

| 维度 | 评分 (1-10) | 说明 |
|------|-------------|------|
| 架构设计 | 7 | 分层清晰，但事务管理有缺陷 |
| 代码质量 | 6 | 有重复导入、裸异常、类型缺失 |
| 安全性 | 3 | 无认证，CORS 过宽，生产不可部署 |
| 功能完整度 | 7 | 核心链路完整，撤销/修订缺失 |
| 性能 | 5 | 查重全表扫描，无连接池 |
| 测试覆盖 | 4 | E2E 较好，但无单元测试 |
| 可维护性 | 6 | 结构清晰，但类型/注释不足 |
| **综合评分** | **5.4/10** | **MVP 可运行，但生产需大量加固** |

---

## 十一、核心代码修复示例

### 修复 1: 认证中间件
```python
# app/core/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

SECRET_KEY = "your-secret-key"  # 从环境变量读取
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(roles: list):
    def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return role_checker
```

### 修复 2: 原子性编码生成
```python
# app/crud.py
from sqlalchemy import text

def increment_seq_atomic(db: Session, rule_id: str) -> int:
    """Atomically increment sequence using database-level operation."""
    result = db.execute(
        text("""
            UPDATE code_rules 
            SET current_seq = current_seq + 1 
            WHERE id = :id 
            RETURNING current_seq
        """),
        {"id": rule_id}
    )
    db.commit()
    return result.scalar()
```

### 修复 3: 事务包裹
```python
# app/api/applications.py
@router.post("/{app_id}/submit")
def submit_application(app_id: str, ...):
    try:
        # ... 所有操作 ...
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
```

---

*报告结束。建议按 Phase 1 → Phase 2 → Phase 3 的顺序执行修复。*
