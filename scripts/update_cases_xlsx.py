from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import shutil
import tempfile
import xml.etree.ElementTree as ET


SOURCE = Path(r"C:\Users\admin\Downloads\Cases_知识库匹配评测_20260902.xlsx")
OUTPUT = SOURCE.with_name("Cases_知识库匹配评测_20260902_知识库补足.xlsx")
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)

UPDATES = {
    2: "【⚠️ 部分补强】补充包第2条：Group Costing / Material Valuations / Costing Parameters / Material Ledger。可支撑集团估值、跨公司交易和内部加价的配置检查项；5HP+多公司统一物料账的优选方案仍需结合公司代码、valuation area、成本流和集团消除口径人工评估。",
    3: "【✅ 已补强】补充包第3条：PO→CPI 迁移可按 migration assessment、interface migration、migration tool、测试与切换组织培训；现有官方迁移指南可作素材，中文术语表和客户 interface inventory 仍需项目化整理。",
    4: "【⚠️ 推导回答】补充包第4条：SF-IAS、Common Super Domain、Cloud Identity Services、EC Payroll 官方资料可组合支撑；开发环境是否影响 EC Payroll 需核对每个环境的 IAS tenant、trust、登录入口和 provisioning，暂无该问法的直接 FAQ。",
    5: "【✅ 已补强】补充包第5条：Cloud Identity Services 出站证书到期后不能延长；可在到期前生成第二张、后端上传后激活，支持 Cloud Identity infrastructure 的场景建议 Automatic Regeneration。未开启时按到期前30/14/3天告警轮换；需区分 CPI keystore、外部 CA 与 CI outbound certificate 生命周期。",
    7: "【❗合同口径缺口】补充包第7条：本地 user management/license compliance 资料不能证明“未登录是否计费”。需查合同 license metric、SKU、授权类型及 SAP for Me/账单口径；技术上可另行补充用户清单与登录审计取数方法。",
    9: "【⚠️ 部分补强】补充包第9条：可结合 Data Storage Considerations、Instance Refresh、Delegated Authentication、Identity Provisioning 排查人员同步 job、属性映射和认证模式；密码能否同步取决于身份源和认证方式，不能直接承诺跨 tenant 复制密码免重置。",
    11: "【⚠️ 推导回答】补充包第11条：生产迁移完成不等于开发 tenant 自动完成；是否需重做取决于开发 tenant 是否独立、是否共用 IAS、Common Super Domain 和按环境配置的应用 trust。建议按 tenant 建环境矩阵并逐项验证。",
    14: "【⚠️ 部分补强】补充包第14条：已有 Adobe Forms Service 产品介绍及 S/4HANA Output Management/Cloud ADS 资料；补充包列出实施级待补采目录：entitlement/service instance、destination、OAuth、模板版本、运行时、监控、权限、网络、故障排查及容量高可用。",
}


def set_inline_text(cell, value):
    for child in list(cell):
        if child.tag == f"{{{NS}}}v" or child.tag == f"{{{NS}}}is":
            cell.remove(child)
    inline = ET.Element(f"{{{NS}}}is")
    text = ET.SubElement(inline, f"{{{NS}}}t")
    text.text = value
    cell.set("t", "inlineStr")
    cell.append(inline)


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        with ZipFile(SOURCE) as archive:
            archive.extractall(temp_path)
        sheet = temp_path / "xl" / "worksheets" / "sheet1.xml"
        tree = ET.parse(sheet)
        root = tree.getroot()
        rows = root.find(f"{{{NS}}}sheetData")
        if rows is None:
            raise RuntimeError("sheetData not found")
        for row in rows.findall(f"{{{NS}}}row"):
            row_number = int(row.get("r", "0"))
            case_number = row_number - 1
            if case_number not in UPDATES:
                continue
            target = None
            for cell in row.findall(f"{{{NS}}}c"):
                if cell.get("r") == f"D{row_number}":
                    target = cell
                    break
            if target is None:
                target = ET.SubElement(row, f"{{{NS}}}c", {"r": f"D{row_number}"})
            set_inline_text(target, UPDATES[case_number])
        tree.write(sheet, encoding="utf-8", xml_declaration=True)
        with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
            for path in temp_path.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(temp_path).as_posix())
    print(OUTPUT)


if __name__ == "__main__":
    main()