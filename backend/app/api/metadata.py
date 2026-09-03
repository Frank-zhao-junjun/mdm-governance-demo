"""元数据管理 API：实体总览 / 字段登记册 / 业务术语。

读权限：所有认证角色（require_any）；写权限：admin / data_admin（require_admin）。
所有写操作落审计（SPEC §3.0）。
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core.auth import require_admin, require_any
from app.core.database import get_db
from app.services import metadata_service
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/metadata", tags=["Metadata"])


def _require_glossary_term(db: Session, term_id: Optional[str]) -> None:
    """payload 带非空 glossary_term_id 时校验术语存在（显式 null 表示解除关联，不校验）。"""
    if term_id and db.get(models.GlossaryTerm, term_id) is None:
        raise HTTPException(status_code=404, detail="关联的术语不存在")


@router.get("/entities", response_model=List[schemas.MetadataEntityResponse])
def list_metadata_entities(user: dict = Depends(require_any), db: Session = Depends(get_db)):
    """实体总览：每个实体附 must_govern 字段数 / 总字段数。"""
    _ = user
    return metadata_service.get_entity_overview(db)


@router.put("/entities/{entity_type}", response_model=schemas.MetadataEntityResponse)
def update_metadata_entity(
    entity_type: str,
    payload: schemas.MetadataEntityUpdate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新实体级治理属性（负责人 / 部门 / 标签 / 敏感级别等）。"""
    entity = crud.get_metadata_entity(db, entity_type)
    if entity is None:
        raise HTTPException(status_code=404, detail="实体元数据不存在")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="未提供可更新字段")
    entity = crud.update_metadata_entity(db, entity, changes)
    AuditService(db).log(
        step_name=models.StepName.METADATA_ENTITY_UPDATE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={"entity_type": entity.entity_type, "fields": sorted(changes.keys())},
    )
    # 响应模型含计数字段，复用总览装配逻辑取当前实体一项
    return next(
        item for item in metadata_service.get_entity_overview(db)
        if item["entity_type"] == entity.entity_type
    )


@router.get("/fields", response_model=schemas.MetadataFieldListResponse)
def list_metadata_fields(
    entity_type: Optional[str] = Query(None, max_length=50),
    view_section: Optional[str] = Query(None, max_length=100),
    must_govern: Optional[bool] = Query(None),
    keyword: Optional[str] = Query(None, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    """字段登记册列表：支持实体 / 视图分区 / 治理标记 / 关键字（名称+标签模糊）过滤。"""
    _ = user
    items, total = crud.get_metadata_fields(
        db,
        entity_type=entity_type,
        view_section=view_section,
        must_govern=must_govern,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    # 批量装配关联术语名 / 引用标准数：两次查询建映射，避免逐行 count（N+1）
    standard_counts = crud.count_standards_by_field_ids(db, [f.id for f in items])
    term_map = crud.get_glossary_terms_by_ids(
        db, [f.glossary_term_id for f in items if f.glossary_term_id]
    )
    result = []
    for f in items:
        item = schemas.MetadataFieldResponse.model_validate(f).model_dump()
        term = term_map.get(f.glossary_term_id) if f.glossary_term_id else None
        item["glossary_term_name"] = term.term if term else None
        item["standard_count"] = standard_counts.get(f.id, 0)
        result.append(item)
    return {"total": total, "items": result}


@router.post("/fields", response_model=schemas.MetadataFieldResponse, status_code=201)
def create_metadata_field(
    payload: schemas.MetadataFieldCreate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """登记元数据字段。同（实体, SAP表, 字段）冲突返回 409；术语不存在返回 404。"""
    _require_glossary_term(db, payload.glossary_term_id)
    conflict = crud.find_metadata_field_conflict(
        db, payload.entity_type, payload.sap_table, payload.field_name
    )
    if conflict:
        raise HTTPException(status_code=409, detail="同（实体, SAP表, 字段）的元数据字段已存在")

    field = crud.create_metadata_field(db, payload.model_dump())
    AuditService(db).log(
        step_name=models.StepName.METADATA_FIELD_CREATE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={
            "field_id": field.id,
            "entity_type": field.entity_type,
            "sap_table": field.sap_table,
            "field_name": field.field_name,
        },
    )
    return field


@router.put("/fields/{field_id}", response_model=schemas.MetadataFieldResponse)
def update_metadata_field(
    field_id: str,
    payload: schemas.MetadataFieldUpdate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新元数据字段可编辑属性（身份键不可变）。"""
    field = crud.get_metadata_field(db, field_id)
    if field is None:
        raise HTTPException(status_code=404, detail="元数据字段不存在")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="未提供可更新字段")
    # 显式 null 解除术语关联不校验；非空值必须指向存在的术语
    _require_glossary_term(db, changes.get("glossary_term_id"))
    field = crud.update_metadata_field(db, field, changes)
    AuditService(db).log(
        step_name=models.StepName.METADATA_FIELD_UPDATE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={
            "field_id": field.id,
            "entity_type": field.entity_type,
            "sap_table": field.sap_table,
            "field_name": field.field_name,
            "fields": sorted(changes.keys()),
        },
    )
    return field


def _to_glossary_response(db: Session, term: models.GlossaryTerm) -> dict:
    """组装术语响应：带出真实关联字段数（与列表端点共用 count_fields_by_glossary_term_ids 口径）。"""
    item = schemas.GlossaryTermResponse.model_validate(term).model_dump()
    item["field_count"] = crud.count_fields_by_glossary_term_ids(db, [term.id]).get(term.id, 0)
    return item


@router.get("/glossary", response_model=List[schemas.GlossaryTermResponse])
def list_glossary_terms(user: dict = Depends(require_any), db: Session = Depends(get_db)):
    """业务术语列表：每个术语附关联元数据字段数 field_count。"""
    _ = user
    terms = crud.get_glossary_terms(db)
    counts = crud.count_fields_by_glossary_term_ids(db, [t.id for t in terms])
    items = []
    for term in terms:
        item = schemas.GlossaryTermResponse.model_validate(term).model_dump()
        item["field_count"] = counts.get(term.id, 0)
        items.append(item)
    return items


@router.post("/glossary", response_model=schemas.GlossaryTermResponse, status_code=201)
def create_glossary_term(
    payload: schemas.GlossaryTermCreate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建业务术语。term 重复返回 409。"""
    existing = (
        db.query(models.GlossaryTerm).filter(models.GlossaryTerm.term == payload.term).first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="术语已存在")

    term = crud.create_glossary_term(db, payload.model_dump())
    AuditService(db).log(
        step_name=models.StepName.GLOSSARY_CREATE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={"term_id": term.id, "term": term.term},
    )
    return _to_glossary_response(db, term)


@router.put("/glossary/{term_id}", response_model=schemas.GlossaryTermResponse)
def update_glossary_term(
    term_id: str,
    payload: schemas.GlossaryTermUpdate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新业务术语（term 名称不可变，仅定义 / 别名可改）。"""
    term = db.get(models.GlossaryTerm, term_id)
    if term is None:
        raise HTTPException(status_code=404, detail="术语不存在")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="未提供可更新字段")
    term = crud.update_glossary_term(db, term, changes)
    AuditService(db).log(
        step_name=models.StepName.GLOSSARY_UPDATE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={"term_id": term.id, "term": term.term, "fields": sorted(changes.keys())},
    )
    return _to_glossary_response(db, term)
