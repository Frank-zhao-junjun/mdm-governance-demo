#!/usr/bin/env python3
"""Initialize database with seed data for the governance service (SPEC v1.3).

Seeds: data standards (appendix fields) + stock records for material /
supplier / customer (≥20 each, with deliberate dirty rows for detection demos).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import models
from app.core.database import SessionLocal, engine


# ========== Data Standards (SPEC §9 appendix) ==========

STANDARDS = [
    # --- material / MARA ---
    ("material", "MARA", "MATNR", "物料编码", "string", None, None, None, None, True, r"^M\d{5}$", True, "编码", "物料主编码，M + 5 位数字"),
    ("material", "MARA", "MAKTX", "物料描述", "string", 40, None, None, None, True, None, False, "名称", "物料短文本描述"),
    ("material", "MARA", "MEINS", "基本计量单位", "enum", None, None, None, ["KG", "G", "PC", "M", "L", "MM", "CM", "M2", "M3"], True, None, False, "计量", "基本计量单位（SAP CUNIT）"),
    ("material", "MARA", "MATKL", "物料组", "enum", None, None, None, ["001", "002", "003", "004", "005"], True, None, False, "分类", "物料组编码"),
    ("material", "MARA", "MTART", "物料类型", "enum", None, None, None, ["ROH", "HALB", "FERT", "HILF", "ERSA"], True, None, False, "分类", "SAP 物料类型"),
    ("material", "MARA", "BRGEW", "毛重", "number", None, 0, 999999, None, False, None, False, "属性", "毛重（公斤）"),
    ("material", "MARA", "NTGEW", "净重", "number", None, 0, 999999, None, False, None, False, "属性", "净重（公斤）"),
    ("material", "MARA", "GEWEI", "重量单位", "enum", None, None, None, ["KG", "G", "T"], False, None, False, "计量", "重量单位"),
    ("material", "MARC", "WERKS", "工厂", "string", None, None, None, None, True, None, False, "组织", "工厂（MARC 视图字段无存量数据源，检测时跳过并记录）"),
    # --- supplier / BUT000 + BUT020 + BUT0BANK + LFA1 ---
    ("supplier", "BUT000", "BU_TYPE", "BP 类型", "enum", None, None, None, ["1", "2"], True, None, False, "状态", "1=组织 2=个人"),
    ("supplier", "BUT000", "NAME_ORG1", "组织名称 1", "string", 40, None, None, None, True, None, False, "名称", "供应商组织名称"),
    ("supplier", "BUT000", "NAME_ORG2", "组织名称 2", "string", 40, None, None, None, False, None, False, "名称", "供应商组织名称补充"),
    ("supplier", "BUT020", "STREET", "街道", "string", 60, None, None, None, False, None, False, "地址", "街道地址"),
    ("supplier", "BUT020", "CITY1", "城市", "string", 40, None, None, None, True, None, False, "地址", "城市"),
    ("supplier", "BUT020", "POST_CODE1", "邮编", "string", 10, None, None, None, False, r"^\d{6}$", False, "地址", "中国邮政编码 6 位数字"),
    ("supplier", "BUT020", "COUNTRY", "国家", "enum", None, None, None, ["CN", "US", "DE", "JP", "SG"], True, None, False, "地址", "国家代码"),
    ("supplier", "BUT0BANK", "BANKS", "银行代码", "string", 10, None, None, None, False, None, False, "财务", "开户行银行代码"),
    ("supplier", "BUT0BANK", "BANKL", "银行账号", "string", 34, None, None, None, False, None, False, "财务", "银行账号"),
    ("supplier", "LFA1", "LIFNR", "供应商编号", "string", 10, None, None, None, True, r"^[0-9]{10}$", True, "编码", "SAP 供应商编号 10 位数字"),
    ("supplier", "LFA1", "NAME1", "供应商名称", "string", 40, None, None, None, True, None, False, "名称", "供应商名称（冗余列）"),
    ("supplier", "LFA1", "LAND1", "国家", "enum", None, None, None, ["CN", "US", "DE", "JP", "SG"], True, None, False, "地址", "供应商国家代码"),
    ("supplier", "LFA1", "ZTERM", "付款条件", "enum", None, None, None, ["0001", "0010", "0020", "0030"], True, None, False, "财务", "付款条件代码"),
    # --- customer / KNA1 + BUT000/BUT020 复用 ---
    ("customer", "KNA1", "KUNNR", "客户编号", "string", 10, None, None, None, True, r"^[0-9]{10}$", True, "编码", "SAP 客户编号 10 位数字"),
    ("customer", "KNA1", "NAME1", "客户名称", "string", 40, None, None, None, True, None, False, "名称", "客户名称（冗余列）"),
    ("customer", "KNA1", "LAND1", "国家", "enum", None, None, None, ["CN", "US", "DE", "JP", "SG"], True, None, False, "地址", "客户国家代码"),
    ("customer", "KNA1", "ZTERM", "付款条件", "enum", None, None, None, ["0001", "0010", "0020", "0030"], True, None, False, "财务", "付款条件代码"),
    ("customer", "BUT020", "CITY1", "城市", "string", 40, None, None, None, True, None, False, "地址", "城市"),
    ("customer", "BUT020", "POST_CODE1", "邮编", "string", 10, None, None, None, False, r"^\d{6}$", False, "地址", "中国邮政编码 6 位数字"),
    ("customer", "BUT020", "COUNTRY", "国家", "enum", None, None, None, ["CN", "US", "DE", "JP", "SG"], True, None, False, "地址", "国家代码"),
]

TOPIC_MAP = {"material": "物料", "supplier": "供应商", "customer": "客户"}


def _standard_rows():
    rows = []
    for (entity, table, field, label, dtype, maxlen, minv, maxv, enums,
         required, pattern, unique, subcategory, desc) in STANDARDS:
        rows.append(models.DataStandard(
            entity_type=entity,
            sap_table=table,
            field_name=field,
            field_label=label,
            data_type=dtype,
            max_length=maxlen,
            min_value=minv,
            max_value=maxv,
            enum_values=enums,
            required=required,
            pattern=pattern,
            unique=unique,
            business_attrs={"standard_topic": TOPIC_MAP[entity], "standard_subcategory": subcategory},
            owner="钱数据",
            standard_source="sap",
            dept_scope=["采购部", "生产部", "财务部"],
            description=desc,
            sap_field_desc=f"{table}-{field}",
        ))
    return rows


# ========== Stock Records (mock, with deliberate dirty rows) ==========

MATERIALS = [
    # (code, name, attrs) — 干净基线
    ("M10001", "六角螺栓 M8×30 镀锌", {"MTART": "ROH", "MEINS": "PC", "MATKL": "001", "BRGEW": 0.02, "NTGEW": 0.018, "GEWEI": "KG"}),
    ("M10002", "六角螺栓 M10×40 镀锌", {"MTART": "ROH", "MEINS": "PC", "MATKL": "001", "BRGEW": 0.04, "NTGEW": 0.035, "GEWEI": "KG"}),
    ("M10003", "不锈钢板 304 δ2.0", {"MTART": "ROH", "MEINS": "KG", "MATKL": "001", "BRGEW": 12.5, "NTGEW": 12.4, "GEWEI": "KG"}),
    ("M10004", "铝合金型材 6063-T5", {"MTART": "ROH", "MEINS": "M", "MATKL": "001", "BRGEW": 2.1, "NTGEW": 2.0, "GEWEI": "KG"}),
    ("M10005", "深沟球轴承 6205-2RS", {"MTART": "HALB", "MEINS": "PC", "MATKL": "002", "BRGEW": 0.13, "NTGEW": 0.12, "GEWEI": "KG"}),
    ("M10006", "油封 TC 35×52×7", {"MTART": "HALB", "MEINS": "PC", "MATKL": "002", "BRGEW": 0.02, "NTGEW": 0.015, "GEWEI": "KG"}),
    ("M10007", "减速机 RV063-30-E", {"MTART": "FERT", "MEINS": "PC", "MATKL": "003", "BRGEW": 12.0, "NTGEW": 11.2, "GEWEI": "KG"}),
    ("M10008", "三相异步电机 Y2-132-4", {"MTART": "FERT", "MEINS": "PC", "MATKL": "003", "BRGEW": 85.0, "NTGEW": 82.0, "GEWEI": "KG"}),
    ("M10009", "低压气动阀门 Z642H-16C-DN50", {"MTART": "FERT", "MEINS": "PC", "MATKL": "003", "BRGEW": 9.5, "NTGEW": 9.0, "GEWEI": "KG"}),
    ("M10010", "低压气动阀门 Z642H-16C-DN100", {"MTART": "FERT", "MEINS": "PC", "MATKL": "003", "BRGEW": 18.0, "NTGEW": 17.2, "GEWEI": "KG"}),
    ("M10011", "液压油 L-HM46", {"MTART": "HILF", "MEINS": "L", "MATKL": "004", "BRGEW": 17.5, "NTGEW": 17.0, "GEWEI": "KG"}),
    ("M10012", "润滑脂 NLGI-2", {"MTART": "HILF", "MEINS": "KG", "MATKL": "004", "BRGEW": 1.0, "NTGEW": 0.95, "GEWEI": "KG"}),
    ("M10013", "刀具 合金立铣刀 D10", {"MTART": "HILF", "MEINS": "PC", "MATKL": "004", "BRGEW": 0.08, "NTGEW": 0.07, "GEWEI": "KG"}),
    ("M10014", "易损件 密封圈套装", {"MTART": "ERSA", "MEINS": "SET", "MATKL": "005", "BRGEW": 0.5, "NTGEW": 0.45, "GEWEI": "KG"}),
    ("M10015", "备件 接触器 CJX2-2510", {"MTART": "ERSA", "MEINS": "PC", "MATKL": "005", "BRGEW": 0.3, "NTGEW": 0.28, "GEWEI": "KG"}),
    ("M10016", "万用表 FLUKE-15B+", {"MTART": "ERSA", "MEINS": "PC", "MATKL": "005", "BRGEW": 0.4, "NTGEW": 0.35, "GEWEI": "KG"}),
    # --- 故意脏数据（供检测演示）---
    ("M1234", "六角螺栓 M8x30 热镀锌", {"MTART": "ROH", "MEINS": "PC", "MATKL": "001", "BRGEW": 0.02, "NTGEW": 0.018, "GEWEI": "KG"}),          # 编码长度错误 + 与 M10001 名称近似
    ("MAT-00020", "不锈钢板 304 δ2", {"MTART": "ROH", "MEINS": "KG", "MATKL": "001", "BRGEW": 12.5, "NTGEW": 12.4, "GEWEI": "KG"}),           # 编码格式错误 + 名称与 M10003 近似
    ("M10019", "深沟球轴承 6205 2RS", {"MTART": "XXX", "MEINS": "PC", "MATKL": "002", "BRGEW": 0.13, "NTGEW": 0.12, "GEWEI": "KG"}),          # MTART 非法枚举
    ("M10020", "油封 TC 45×62×8", {"MTART": "HALB", "MATKL": "002", "BRGEW": 0.03, "NTGEW": -0.01, "GEWEI": "KG"}),                          # 缺 MEINS + 净重为负
]

SUPPLIERS = [
    ("1000000001", "华成精密机械有限公司", {"BU_TYPE": "1", "NAME_ORG1": "华成精密机械有限公司", "STREET": "金桥路 88 号", "CITY1": "上海", "POST_CODE1": "201206", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("1000000002", "远东液压设备股份有限公司", {"BU_TYPE": "1", "NAME_ORG1": "远东液压设备股份有限公司", "CITY1": "常州", "POST_CODE1": "213000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("1000000003", "宁波海天塑机集团", {"BU_TYPE": "1", "NAME_ORG1": "宁波海天塑机集团", "CITY1": "宁波", "POST_CODE1": "315800", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("1000000004", "沈阳机床股份有限公司", {"BU_TYPE": "1", "NAME_ORG1": "沈阳机床股份有限公司", "CITY1": "沈阳", "POST_CODE1": "110142", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0030"}),
    ("1000000005", "博世力士乐（中国）有限公司", {"BU_TYPE": "1", "NAME_ORG1": "博世力士乐（中国）有限公司", "CITY1": "上海", "POST_CODE1": "200131", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("1000000006", "SMC（中国）有限公司", {"BU_TYPE": "1", "NAME_ORG1": "SMC（中国）有限公司", "CITY1": "北京", "POST_CODE1": "100176", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("1000000007", "杭州轴承试验研究中心", {"BU_TYPE": "1", "NAME_ORG1": "杭州轴承试验研究中心", "CITY1": "杭州", "POST_CODE1": "310000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("1000000008", "广州密封件工业公司", {"BU_TYPE": "1", "NAME_ORG1": "广州密封件工业公司", "CITY1": "广州", "POST_CODE1": "510000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("1000000009", "武汉钢铁集团金属资源有限公司", {"BU_TYPE": "1", "NAME_ORG1": "武汉钢铁集团金属资源有限公司", "CITY1": "武汉", "POST_CODE1": "430000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0030"}),
    ("1000000010", "宝钢钢材贸易有限公司", {"BU_TYPE": "1", "NAME_ORG1": "宝钢钢材贸易有限公司", "CITY1": "上海", "POST_CODE1": "201900", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("1000000011", "昆山华成精密机械有限公司", {"BU_TYPE": "1", "NAME_ORG1": "昆山华成精密机械有限公司", "CITY1": "昆山", "POST_CODE1": "215300", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("1000000012", "托克斯冲压设备（苏州）", {"BU_TYPE": "1", "NAME_ORG1": "托克斯冲压设备（苏州）", "CITY1": "苏州", "POST_CODE1": "215000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("1000000013", "詹姆斯顿轴承贸易公司", {"BU_TYPE": "1", "NAME_ORG1": "詹姆斯顿轴承贸易公司", "CITY1": "天津", "POST_CODE1": "300000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("1000000014", "费斯托（中国）有限公司", {"BU_TYPE": "1", "NAME_ORG1": "费斯托（中国）有限公司", "CITY1": "上海", "POST_CODE1": "200233", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("1000000015", "无锡油缸制造厂", {"BU_TYPE": "1", "NAME_ORG1": "无锡油缸制造厂", "CITY1": "无锡", "POST_CODE1": "214000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0030"}),
    ("1000000016", "德阳重型装备配件公司", {"BU_TYPE": "1", "NAME_ORG1": "德阳重型装备配件公司", "CITY1": "德阳", "POST_CODE1": "618000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    # --- 故意脏数据 ---
    ("SUP-00017", "华成精密机械有限公", {"BU_TYPE": "1", "NAME_ORG1": "华成精密机械有限公", "CITY1": "上海", "POST_CODE1": "201206", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),  # 编码格式错误 + 名称与 0001 近似
    ("12345", "杭州轴承试验中心", {"BU_TYPE": "1", "NAME_ORG1": "杭州轴承试验中心", "POST_CODE1": "31000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),                     # 编码短 + 缺 CITY1 + 邮编 5 位
    ("1000000019", "广州密封件工业公司", {"BU_TYPE": "1", "NAME_ORG1": "广州密封件工业公司", "CITY1": "广州", "POST_CODE1": "510000", "COUNTRY": "CN", "LAND1": "XX"}),                # 与 0008 完全重名 + LAND1 非法
    ("1000000020", "重庆齿轮箱有限责任公司", {"BU_TYPE": "1", "NAME_ORG1": "重庆齿轮箱有限责任公司", "CITY1": "重庆", "POST_CODE1": "402262", "COUNTRY": "CN", "LAND1": "CN"}),           # 缺 ZTERM（必填）
]

CUSTOMERS = [
    ("2000000001", "一汽解放汽车有限公司", {"CITY1": "长春", "POST_CODE1": "130011", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("2000000002", "东风商用车有限公司", {"CITY1": "十堰", "POST_CODE1": "442000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("2000000003", "陕西重型汽车有限公司", {"CITY1": "西安", "POST_CODE1": "710200", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("2000000004", "徐州工程机械集团", {"CITY1": "徐州", "POST_CODE1": "221004", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0030"}),
    ("2000000005", "三一重工股份有限公司", {"CITY1": "长沙", "POST_CODE1": "410100", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("2000000006", "中联重科股份有限公司", {"CITY1": "长沙", "POST_CODE1": "410205", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("2000000007", "安徽合力股份有限公司", {"CITY1": "合肥", "POST_CODE1": "230601", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("2000000008", "杭叉集团股份有限公司", {"CITY1": "杭州", "POST_CODE1": "310000", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("2000000009", "柳工机械股份有限公司", {"CITY1": "柳州", "POST_CODE1": "545007", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("2000000010", "厦门工程机械股份有限公司", {"CITY1": "厦门", "POST_CODE1": "361026", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0030"}),
    ("2000000011", "北方重工集团有限公司", {"CITY1": "沈阳", "POST_CODE1": "110141", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("2000000012", "山东重工集团有限公司", {"CITY1": "济南", "POST_CODE1": "250022", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("2000000013", "太平洋精锻股份有限公司", {"CITY1": "泰州", "POST_CODE1": "225500", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("2000000014", "宁波拓普集团股份有限公司", {"CITY1": "宁波", "POST_CODE1": "315800", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    ("2000000015", "广东鸿图科技股份有限公司", {"CITY1": "肇庆", "POST_CODE1": "526238", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),
    ("2000000016", "重庆青山工业有限责任公司", {"CITY1": "重庆", "POST_CODE1": "402762", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),
    # --- 故意脏数据 ---
    ("CUS-0017", "三一重工股份公司", {"CITY1": "长沙", "POST_CODE1": "410100", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0020"}),   # 编码格式错误 + 与 0005 近似
    ("2000000018", "中联重科股份有限公司", {"CITY1": "长沙", "POST_CODE1": "410205", "LAND1": "CN", "ZTERM": "0020"}),                # 与 0006 完全重名 + 缺 COUNTRY
    ("2000000019", "杭叉集团股份公司", {"CITY1": "杭州", "POST_CODE1": "3100", "COUNTRY": "CN", "LAND1": "CN", "ZTERM": "0010"}),     # 与 0008 近似 + 邮编 4 位
    ("2000000020", "浙江长城减速机有限公司", {"CITY1": "嘉兴", "POST_CODE1": "314000", "COUNTRY": "CN", "LAND1": "CN"}),              # 缺 ZTERM（必填）
]


def init_db():
    """Create tables and seed data."""
    # Drop and recreate
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        standards = _standard_rows()
        db.add_all(standards)
        db.flush()  # 先取 standard.id 供规则行 standard_id FK

        # 质量检测规则：由数据标准派生（SPEC §2.4 + Phase 2 设计决策 1）
        from app.services.rule_derivation import derive_rule_rows

        db.add_all(derive_rule_rows(standards))

        db.add_all([
            models.MaterialRecord(
                material_code=code,
                material_name=name,
                attributes=attrs,
                source_system="mock_sap",
                status="active",
            )
            for code, name, attrs in MATERIALS
        ])

        db.add_all([
            models.PartnerRecord(
                entity_type="supplier",
                partner_code=code,
                partner_name=name,
                attributes=attrs,
                source_system="mock_sap",
                status="active",
            )
            for code, name, attrs in SUPPLIERS
        ])

        db.add_all([
            models.PartnerRecord(
                entity_type="customer",
                partner_code=code,
                partner_name=name,
                attributes=attrs,
                source_system="mock_sap",
                status="active",
            )
            for code, name, attrs in CUSTOMERS
        ])

        db.commit()

        print("✅ Governance DB initialized: standards + stock records (with dirty rows)")

    finally:
        db.close()


if __name__ == "__main__":
    init_db()
