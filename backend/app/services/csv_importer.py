"""供应商/客户 CSV 导入（SPEC §7 Phase 4.1）。

上游业务系统负责数据创建与分发（SPEC §1.4），本系统只通过导入接收存量
数据后做检测/报告/人工处理建议，因此导入是**存量数据的唯一入口**。

安全约束沿用 AGENTS.md 附件规则（Phase 0 删除申请链路时一并删掉了原
upload 校验，这里按同一不变量重建）：扩展名白名单 + MIME 白名单 +
单文件 ≤ 10MB；拒绝 HTML/SVG/JS 等可执行类型。

语义要点：

* 按 ``(entity_type, partner_code)`` upsert，非全量替换；
* 非必填列以表头（SAP 字段名，SPEC §4.2）为键折叠进 ``attributes``；
  更新时**合并**而非覆盖——CSV 未出现的列保留旧值，空单元格也不清旧值；
* 格式错误行只影响该行（计入明细报告），合法行照常入库，满足验收
  “CSV 导入成功；格式错误行返回明细报告”的部分成功语义；
* 文件级缺陷（类型/大小/表头/行数超限）直接失败，不落任何数据。

审计由 API 层完成（沿用 quality_checks 的两段提交模式）。
"""
import csv
import io
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app import crud, models

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10MB，与 AGENTS.md 附件上限一致
MAX_ROWS = 5_000                   # 与单次质量检测的实体上限对齐（SPEC §5）
ALLOWED_SUFFIXES = (".csv",)
#: 白名单而非黑名单：真实客户端对 CSV 的 MIME 说法不一，但 html/svg/js 必须挡住
ALLOWED_CONTENT_TYPES = frozenset({
    "text/csv",
    "text/plain",
    "application/csv",
    "application/vnd.ms-excel",
    "application/octet-stream",
})

REQUIRED_COLUMNS = ("partner_code", "partner_name")
MAX_CODE_LEN = 50       # PartnerRecord.partner_code String(50)
MAX_NAME_LEN = 200      # PartnerRecord.partner_name String(200)
MAX_ATTRIBUTE_VALUE_LEN = 500


class CsvImportError(Exception):
    """文件级缺陷，整批拒绝（API 层映射为 400）。"""


@dataclass
class RowError:
    """单行明细（row 为 CSV 数据行号，从 1 起，不含表头）。"""
    row: int
    field: Optional[str]
    message: str


@dataclass
class PartnerImportResult:
    total_rows: int = 0
    created: int = 0
    updated: int = 0
    errors: List[RowError] = field(default_factory=list)

    @property
    def failed(self) -> int:
        """失败行数（一行可报多条错，按行去重计数）。"""
        return len({e.row for e in self.errors})


def _guard_file(filename: str, content_type: Optional[str], raw: bytes) -> None:
    suffix = "" if "." not in filename else filename[filename.rfind("."):].lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise CsvImportError(
            f"不支持的文件类型 '{suffix or filename}'；仅接受 {', '.join(ALLOWED_SUFFIXES)}"
        )
    if content_type and content_type.split(";")[0].strip().lower() not in ALLOWED_CONTENT_TYPES:
        raise CsvImportError(f"不支持的 Content-Type '{content_type}'")
    if not raw:
        raise CsvImportError("文件为空")
    if len(raw) > MAX_FILE_BYTES:
        raise CsvImportError(f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 上限")


def _decode(raw: bytes) -> str:
    # utf-8-sig 兼容 Excel 导出的 BOM
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvImportError(f"文件不是有效的 UTF-8 文本：{exc}") from exc


def _parse_rows(text: str) -> Tuple[List[Dict[str, str]], List[RowError], int]:
    """返回 (合法行, 行错误, 数据行总数)。全空行静默跳过且不计入总数。"""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CsvImportError("CSV 缺少表头")
    reader.fieldnames = [(h or "").strip() for h in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise CsvImportError(
            f"CSV 缺少必需列 {', '.join(missing)}；必需列为 {', '.join(REQUIRED_COLUMNS)}"
        )

    rows: List[Dict[str, str]] = []
    errors: List[RowError] = []
    total = 0
    seen_codes: Set[str] = set()

    for index, raw_row in enumerate(reader, start=1):
        row = {k: (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue
        total += 1
        if total > MAX_ROWS:
            raise CsvImportError(f"单次导入不超过 {MAX_ROWS} 行，请分批导入")

        row_errors: List[RowError] = []
        code = row.get("partner_code", "")
        if not code:
            row_errors.append(RowError(index, "partner_code", "编码不能为空"))
        elif len(code) > MAX_CODE_LEN:
            row_errors.append(
                RowError(index, "partner_code", f"编码长度超过 {MAX_CODE_LEN} 字符")
            )
        elif code in seen_codes:
            row_errors.append(RowError(index, "partner_code", f"文件内编码重复：{code}"))
        else:
            seen_codes.add(code)

        name = row.get("partner_name", "")
        if not name:
            row_errors.append(RowError(index, "partner_name", "名称不能为空"))
        elif len(name) > MAX_NAME_LEN:
            row_errors.append(
                RowError(index, "partner_name", f"名称长度超过 {MAX_NAME_LEN} 字符")
            )

        attributes: Dict[str, str] = {}
        for key, value in row.items():
            if key in REQUIRED_COLUMNS or not value:
                continue
            if len(value) > MAX_ATTRIBUTE_VALUE_LEN:
                row_errors.append(
                    RowError(index, key, f"字段值长度超过 {MAX_ATTRIBUTE_VALUE_LEN} 字符")
                )
                continue
            attributes[key] = value

        if row_errors:
            errors.extend(row_errors)
        else:
            rows.append({"partner_code": code, "partner_name": name, "attributes": attributes})

    return rows, errors, total


def import_partners(
    db: Session,
    entity_type: str,
    filename: str,
    content_type: Optional[str],
    content: bytes,
    source_system: str = "csv_import",
) -> PartnerImportResult:
    """导入供应商/客户 CSV，按 (entity_type, partner_code) upsert。"""
    _guard_file(filename, content_type, content)
    rows, errors, total = _parse_rows(_decode(content))

    result = PartnerImportResult(total_rows=total, errors=errors)
    if not rows:
        return result

    existing = crud.map_partner_records_by_code(
        db, entity_type, [r["partner_code"] for r in rows]
    )
    for parsed in rows:
        record = existing.get(parsed["partner_code"])
        if record is None:
            db.add(models.PartnerRecord(
                entity_type=entity_type,
                partner_code=parsed["partner_code"],
                partner_name=parsed["partner_name"],
                attributes=parsed["attributes"],
                source_system=source_system,
                status="active",
            ))
            result.created += 1
            continue
        record.partner_name = parsed["partner_name"]
        # 必须整体赋新 dict：SQLAlchemy 不追踪 JSON 列的就地修改
        record.attributes = {**(record.attributes or {}), **parsed["attributes"]}
        record.status = "active"
        result.updated += 1

    db.commit()
    return result
