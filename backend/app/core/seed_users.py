"""种子用户单一来源定义：init_db.py 与测试 conftest 共用。

角色映射与 v2.0 之前的 MOCK_USERS 保持一致，保证既有凭据与测试语义不变。
密码哈希在模块导入时一次性预生成，避免测试套件中逐条 bcrypt 的开销。
"""

from app.core.auth import hash_password

SEED_USERS = [
    {
        "id": "admin001",
        "name": "王管理员",
        "department": "IT部",
        "role": "admin",
        "password": "adminpass001",
    },
    {
        "id": "user001",
        "name": "张三",
        "department": "研发部",
        "role": "applicant",
        "password": "password001",
    },
    {
        "id": "user002",
        "name": "李四",
        "department": "采购部",
        "role": "applicant",
        "password": "password002",
    },
    {
        "id": "dept001",
        "name": "赵部长",
        "department": "生产部",
        "role": "dept_approver",
        "password": "deptpass001",
    },
    {
        "id": "data001",
        "name": "钱数据",
        "department": "数据治理部",
        "role": "data_admin",
        "password": "datapass001",
    },
]

# 进程内一次性预生成，避免测试中每条种子都跑 bcrypt
_SEED_PASSWORD_HASHES = {u["id"]: hash_password(u["password"]) for u in SEED_USERS}


def seed_users(db_session) -> None:
    """向数据库写入种子用户（幂等：已存在则跳过）。"""
    from app import models

    for spec in SEED_USERS:
        if db_session.get(models.User, spec["id"]) is None:
            db_session.add(
                models.User(
                    id=spec["id"],
                    name=spec["name"],
                    department=spec["department"],
                    role=spec["role"],
                    password_hash=_SEED_PASSWORD_HASHES[spec["id"]],
                )
            )
    db_session.commit()
