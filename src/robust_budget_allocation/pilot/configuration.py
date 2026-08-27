"""Fixed N6 registration and deterministic, new-project pilot-only inputs."""

import json
from pathlib import Path
import random

from robust_budget_allocation.data.mechanism_data import OptionData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file

ROOT = Path(__file__).resolve().parents[3]
SCOPE = "PILOT ONLY — NOT FORMAL SCIENTIFIC PARAMETERS"
PROTOCOL = "docs/N6_PILOT_PROTOCOL.md"
PROTOCOL_SHA = "ba60833a951ea4ad69ba123ea421329a1387a0cf581645f8bc7040d0c3414b0d"
CONFIG_PATH = "configs/pilot/n6_candidates.json"
CONFIG_SHA = "974c5b9e13d278cff2ead221d1c838aff4db2c3c3b97314b2595ecb00d6db0d2"
PROTOCOL_COMMIT = "db31c2551a697461fdd1dfde4b797959217f6e40"
BASELINE_COMMIT = "9dc61f3f7d4b329a2bcf65084c56bbfc1cee78bc"
METHODS = ("M0", "M1", "EF", "A0", "A1")


def registration():
    for name, sha in ((PROTOCOL, PROTOCOL_SHA), (CONFIG_PATH, CONFIG_SHA)):
        if sha256_file(ROOT / name) != sha:
            raise ValueError("N6 preregistration hash mismatch: " + name)
    config = json.loads((ROOT / CONFIG_PATH).read_text(encoding="utf-8"))
    if config["classification"] != SCOPE:
        raise ValueError("pilot classification")
    return config


def scenario_payload(data):
    """Full scenario identity, unlike the legacy base-only convenience property."""
    rel = data.reliability
    return dict(resource_id=data.base.resource_id, suppliers=list(data.base.suppliers),
                levels={j: list(rel.levels[j]) for j in data.base.suppliers},
                ordered_scenarios=[dict(id=w, demand=data.base.demand[w],
                    fulfillment={j: dict(rel.fulfillment[w][j]) for j in data.base.suppliers},
                    emergency_price=data.emergency_price[w]) for w in data.base.scenarios])


def generate(config):
    # Only registered values can be run; tests may test validation independently.
    if config not in registration()["configs"]:
        raise ValueError("unregistered pilot configuration")
    rng = random.Random(config["seed"])
    suppliers = ["j0", "j1", "j2"]
    scenarios = [f"w{i:03d}" for i in range(config["scenarios"])]
    demand, base_rho, fulfillment, price = {}, {}, {}, {}
    threshold = .08 if config["risk"] == "low" else .40
    for w in scenarios:
        demand[w] = round(60 + 40*rng.random(), 8)
        base_rho[w], fulfillment[w] = {}, {}
        for j in suppliers:
            state, severity = rng.random(), rng.random()
            rho = round(.10+.30*severity if state < threshold else .85+.15*severity, 8)
            base_rho[w][j] = rho
            fulfillment[w][j] = {"0": rho, "1": round(rho+.65*(1-rho), 8)}
        price[w] = round(2.2+1.8*rng.random(), 8)
    mult = config["premium_multiplier"]
    base = dict(schema_version=1, resource_id="resource", suppliers=suppliers,
                scenarios=scenarios, budget=config["budget"],
                unit_cost=dict(zip(suppliers, (1, 1.15, 1.35))),
                procurement_limit=dict(zip(suppliers, (60, 50, 40))),
                demand=demand, base_fulfillment=base_rho, shortage_penalty=8)
    rel = dict(schema_version=1, base=base, levels={j: ["0", "1"] for j in suppliers},
               fixed_premium={j: {"0": 0, "1": v*mult} for j, v in zip(suppliers, (2, 2.5, 3))},
               unit_premium={j: {"0": 0, "1": v*mult} for j, v in zip(suppliers, (.18, .22, .25))},
               fulfillment=fulfillment)
    return OptionData.from_dict(dict(schema_version=1, reliability=rel,
        option_fee=6*config["option_fee_multiplier"], option_cap=45, emergency_price=price))


def binding(config, data):
    return dict(classification=SCOPE, config_id=config["id"], config=config,
                config_sha256=canonical_json_sha256(config), data=data.to_dict(),
                data_sha256=data.data_sha256, scenario_sha256=canonical_json_sha256(scenario_payload(data)),
                seed=config["seed"], budget=config["budget"],
                protocol_sha256=PROTOCOL_SHA, registered_config_sha256=CONFIG_SHA)


def execution_order(index):
    return ("M0", "M1", "EF", "A0", "A1") if index % 2 == 0 else ("M0", "M1", "EF", "A1", "A0")

