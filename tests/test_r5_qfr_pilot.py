from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from robust_budget_allocation.pilot import qfr_wfp
from robust_budget_allocation.pilot.qfr_r5 import (
    EXECUTION_CONFIG_PATH,
    load_execution_config,
)


ROOT = Path(__file__).resolve().parents[1]


def test_read_xlsx_tables_reads_the_workbook_not_a_copied_json(tmp_path):
    workbook = tmp_path / "source.xlsx"
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Nodes - Types" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>Name</t></is></c>'
            '<c r="C1" t="inlineStr"><is><t>Demand</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>Node D</t></is></c><c r="C2"><v>67000</v></c></row>'
            '</sheetData></worksheet>',
        )
    assert qfr_wfp.read_xlsx_tables(workbook) == {
        "Nodes - Types": [["Name", None, "Demand"], ["Node D", None, 67000]]
    }


def _audit_tables():
    demand = [
        ["Ar Raqqa D", "D", 10000, "Syrian Arab Republic"],
        ["Daraa D", "D", 10000, "Syrian Arab Republic"],
        ["Dayr_Az_Zor D", "D", 25000, "Syrian Arab Republic"],
        ["Hassakeh D", "D", 10000, "Syrian Arab Republic"],
        ["Idleb D", "D", 5000, "Syrian Arab Republic"],
        ["Jubb_al_Jarrah D", "D", 2000, "Syrian Arab Republic"],
        ["Qamishli", "D", 5000, "Syrian Arab Republic"],
    ]
    nutrition = {
        "Sugar": [400, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "Rice": [360, 7, 0.5, 7, 1.2, 0, 0.2, 0.08, 2.6, 11, 0],
    }
    jurisdictions = [
        "Aleppo", "As_Suweida", "Damascus", "Daraa", "Dayr_Az_Zor", "Hama", "Hassakeh", "Homs"
    ]
    return {
        "Nodes - Types": [["Name", "Type", "Demand", "Country"], *demand],
        "Edges - Cost": [["A", "B"]],
        "Food - Nutritional value": [["Food", *[f"N{i}" for i in range(11)]], ["Rice", *nutrition["Rice"]], ["Sugar", *nutrition["Sugar"]]],
        "Food - Cost": [["adm1_name", "short_name", 1, "Mean"], *[[place, item, 1, 1] for place in jurisdictions for item in ("Rice", "Sugar")]],
        "Food - InternationalPrice": [["Food", "InternationalPrice"], ["Rice", 800], ["Sugar", 1100]],
        "Nutrient - Requirements": [["Type"]],
    }


def test_wfp_audit_checks_registered_nodes_and_sugar_rice(monkeypatch, tmp_path):
    source = tmp_path / "Data Syria Case WFP.xlsx"
    source.write_bytes(b"registered workbook bytes")
    config = load_execution_config(ROOT / EXECUTION_CONFIG_PATH)
    specification = dict(config["wfp_workbook"])
    specification["sha256"] = sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(qfr_wfp, "read_xlsx_tables", lambda _: _audit_tables())
    audit = qfr_wfp.audit_wfp_workbook(source, specification)
    assert audit["demand_node_count"] == 7
    assert audit["demand_total"] == 67000
    assert audit["international_price"] == {"Rice": 800, "Sugar": 1100}
    assert audit["cost_observations_per_item"] == {"Sugar": 16, "Rice": 16}


def test_wfp_audit_fails_closed_on_registered_demand_conflict(monkeypatch, tmp_path):
    source = tmp_path / "Data Syria Case WFP.xlsx"
    source.write_bytes(b"registered workbook bytes")
    config = load_execution_config(ROOT / EXECUTION_CONFIG_PATH)
    specification = dict(config["wfp_workbook"])
    specification["sha256"] = sha256(source.read_bytes()).hexdigest()
    specification["demand_total"] = 67001
    monkeypatch.setattr(qfr_wfp, "read_xlsx_tables", lambda _: _audit_tables())
    with pytest.raises(ValueError, match="demand total"):
        qfr_wfp.audit_wfp_workbook(source, specification)


def test_r5_execution_config_is_exactly_the_registered_matrix():
    payload = load_execution_config(ROOT / EXECUTION_CONFIG_PATH)
    assert payload["budget_ratios"] == [0.9, 1.0, 1.1]
    assert payload["models"] == ["M0", "M1", "M2"]
    assert payload["algorithms"] == ["EF", "A0", "A1"]
    assert payload["memory_phase_enabled"] is True
