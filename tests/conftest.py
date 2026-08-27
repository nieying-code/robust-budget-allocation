import json
from pathlib import Path

import pytest

from robust_budget_allocation.data.model_data import BudgetAllocationData


M0_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "n2_m0_hand_cases.json"
M0_CASES = json.loads(M0_FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.fixture
def m0_data() -> BudgetAllocationData:
    return BudgetAllocationData.from_dict(M0_CASES[0]["data"])
