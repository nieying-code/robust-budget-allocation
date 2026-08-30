"""Read and audit the frozen local WFP Syria workbook for R5."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping
from xml.etree import ElementTree as ET
from zipfile import ZipFile


_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def _column(reference: str) -> int:
    match = re.match(r"([A-Z]+)", reference)
    if match is None:
        raise ValueError(f"invalid Excel cell reference: {reference!r}")
    value = 0
    for character in match.group(1):
        value = value * 26 + ord(character) - 64
    return value - 1


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter(f"{{{_MAIN}}}t")) for item in root]


def _cell_value(cell: ET.Element, shared: list[str]) -> Any:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{_MAIN}}}t"))
    value = cell.find(f"{{{_MAIN}}}v")
    if value is None or value.text is None:
        return None
    raw = value.text
    if kind == "s":
        return shared[int(raw)]
    if kind in {"str", "e"}:
        return raw
    if kind == "b":
        return raw == "1"
    number = float(raw)
    return int(number) if number.is_integer() else number


def read_xlsx_tables(path: Path) -> dict[str, list[list[Any]]]:
    """Return rectangular cached-value tables without modifying the workbook."""

    source = path.resolve()
    with ZipFile(source) as archive:
        shared = _shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            relationship.get("Id"): relationship.get("Target")
            for relationship in rels.findall(f"{{{_PKG_REL}}}Relationship")
        }
        result: dict[str, list[list[Any]]] = {}
        sheets = workbook.find(f"{{{_MAIN}}}sheets")
        if sheets is None:
            raise ValueError("workbook has no sheets")
        for sheet in sheets:
            name = str(sheet.get("name"))
            relationship = sheet.get(f"{{{_DOC_REL}}}id")
            target = targets.get(relationship)
            if not target:
                raise ValueError(f"missing workbook relationship for sheet {name!r}")
            normalized = str(PurePosixPath("xl") / target).replace("xl/../", "")
            root = ET.fromstring(archive.read(normalized))
            rows: list[list[Any]] = []
            for row in root.findall(f".//{{{_MAIN}}}sheetData/{{{_MAIN}}}row"):
                values: list[Any] = []
                for cell in row.findall(f"{{{_MAIN}}}c"):
                    index = _column(str(cell.get("r")))
                    values.extend([None] * (index + 1 - len(values)))
                    values[index] = _cell_value(cell, shared)
                rows.append(values)
            width = max((len(row) for row in rows), default=0)
            result[name] = [row + [None] * (width - len(row)) for row in rows]
        return result


def audit_wfp_workbook(path: Path, specification: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the exact workbook and return the registered R5 source audit."""

    source = path.resolve()
    if source.name != specification["file_name"]:
        raise ValueError("WFP workbook file name mismatch")
    digest = sha256(source.read_bytes()).hexdigest()
    if digest != specification["sha256"]:
        raise ValueError("WFP workbook SHA-256 mismatch")
    tables = read_xlsx_tables(source)
    if list(tables) != list(specification["sheet_names"]):
        raise ValueError("WFP workbook sheet inventory mismatch")

    nodes = tables["Nodes - Types"]
    if nodes[0][:4] != ["Name", "Type", "Demand", "Country"]:
        raise ValueError("WFP demand-node fields mismatch")
    demand_rows = [[row[0], int(row[2])] for row in nodes[1:] if row[1] == "D"]
    if demand_rows != specification["demand_nodes"]:
        raise ValueError("WFP demand-node values mismatch")
    if sum(row[1] for row in demand_rows) != specification["demand_total"]:
        raise ValueError("WFP demand total mismatch")

    nutrition = tables["Food - Nutritional value"]
    nutrition_rows = {row[0]: row[1:12] for row in nutrition[1:] if row and row[0] in {"Sugar", "Rice"}}
    if nutrition_rows != specification["nutrition_rows"]:
        raise ValueError("WFP Sugar/Rice nutritional rows mismatch")
    international = tables["Food - InternationalPrice"]
    international_rows = {row[0]: row[1] for row in international[1:] if row and row[0] in {"Sugar", "Rice"}}
    if international_rows != specification["international_price"]:
        raise ValueError("WFP Sugar/Rice international-price rows mismatch")
    costs = tables["Food - Cost"]
    cost_jurisdictions = {
        item: [row[0] for row in costs[1:] if len(row) > 1 and row[1] == item]
        for item in ("Sugar", "Rice")
    }
    expected_jurisdictions = list(specification["cost_jurisdictions"])
    if any(values != expected_jurisdictions for values in cost_jurisdictions.values()):
        raise ValueError("WFP Sugar/Rice cost-row coverage mismatch")
    return {
        "path": str(source),
        "file_name": source.name,
        "sha256": digest,
        "sheet_names": list(tables),
        "demand_node_count": len(demand_rows),
        "demand_nodes": demand_rows,
        "demand_total": sum(row[1] for row in demand_rows),
        "nutrition_header": nutrition[0][:12],
        "nutrition_rows": nutrition_rows,
        "international_price_header": international[0][:2],
        "international_price": international_rows,
        "cost_sheet_header": costs[0],
        "cost_jurisdictions": cost_jurisdictions,
        "cost_observations_per_item": {
            item: sum(max(0, len(row) - 2) for row in costs[1:] if len(row) > 1 and row[1] == item)
            for item in ("Sugar", "Rice")
        },
    }
