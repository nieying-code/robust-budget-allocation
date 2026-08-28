"""Immutable N7-pre registration and authorized economic-condition generator."""

import hashlib
import json
from pathlib import Path
import random

from robust_budget_allocation.data.mechanism_data import OptionData
from robust_budget_allocation.io.hashing import canonical_json_sha256, sha256_file
from robust_budget_allocation.pilot.configuration import scenario_payload

ROOT = Path(__file__).resolve().parents[3]
SCOPE = "N7-PRE DIAGNOSTIC ONLY — NOT FORMAL SCIENTIFIC PARAMETERS"
REGISTRATION_COMMIT = "4df5d90c8a3bd5a131cd47f8f7baba55e90773ac"
FROZEN = {
    "docs/N7_PRE_MECHANISM_PROTOCOL.md": "b110e1ecf24b83c2fa217204bb35177be72cc13da57ef7e8d7b81d14b1497b1e",
    "configs/n7_pre/matrix.json": "b25eea24b3610c0635262fae2549958d16058ff7a3f2aad8ae31fe44a9d10d16",
    "configs/n7_pre/seeds.json": "5af50e8c337691652bd9045e4957c5fc61778aa096778fcedf0ba8791dd8e71b",
}
METHODS = ("M0", "M1", "EF", "A0", "A1")


def registration():
    for name, digest in FROZEN.items():
        if sha256_file(ROOT / name) != digest:
            raise ValueError("N7-pre frozen registration changed: " + name)
    matrix = json.loads((ROOT / "configs/n7_pre/matrix.json").read_text(encoding="utf-8"))
    seeds = json.loads((ROOT / "configs/n7_pre/seeds.json").read_text(encoding="utf-8"))
    expected = [int(hashlib.sha256((seeds["namespace"]+str(i)).encode()).hexdigest()[:8], 16)
                for i in range(1, 7)]
    if seeds["seeds"] != expected or len(set(expected)) != 6 or {61001, 61002} & set(expected):
        raise ValueError("diagnostic seed registry")
    if matrix["classification"] != SCOPE or len(matrix["configs"]) != 54:
        raise ValueError("N7-pre scope/matrix")
    return matrix


def generate(config):
    if config not in registration()["configs"]:
        raise ValueError("unregistered N7-pre config")
    rng = random.Random(config["seed"])
    suppliers = ["j0", "j1", "j2"]
    scenarios = [f"w{i:03d}" for i in range(config["scenarios"])]
    demand, rho0, fulfillment, prices = {}, {}, {}, {}
    for w in scenarios:
        demand[w] = round(60+40*rng.random(), 8)
        rho0[w], fulfillment[w] = {}, {}
        for j in suppliers:
            state, severity = rng.random(), rng.random()
            rho = round(.10+.30*severity if state < .40 else .85+.15*severity, 8)
            rho0[w][j] = rho
            fulfillment[w][j] = {"0": rho, "1": round(rho+.65*(1-rho), 8)}
        prices[w] = round(config["price_intercept"]+config["price_slope"]*rng.random(), 8)
    base = dict(schema_version=1, resource_id="resource", suppliers=suppliers, scenarios=scenarios,
                budget=config["budget"], unit_cost=dict(zip(suppliers, (1, 1.15, 1.35))),
                procurement_limit=dict(zip(suppliers, (60, 50, 40))), demand=demand,
                base_fulfillment=rho0, shortage_penalty=8)
    mult = config["premium_multiplier"]
    rel = dict(schema_version=1, base=base, levels={j: ["0", "1"] for j in suppliers},
        fixed_premium={j: {"0": 0, "1": v*mult} for j, v in zip(suppliers, (2, 2.5, 3))},
        unit_premium={j: {"0": 0, "1": v*mult} for j, v in zip(suppliers, (.18, .22, .25))},
        fulfillment=fulfillment)
    return OptionData.from_dict(dict(schema_version=1, reliability=rel, option_fee=config["option_fee"],
                                    option_cap=45, emergency_price=prices))


def binding(config, data):
    return dict(classification=SCOPE, config=config, config_sha256=canonical_json_sha256(config),
                data=data.to_dict(), data_sha256=data.data_sha256,
                scenario_sha256=canonical_json_sha256(scenario_payload(data)),
                registration_commit=REGISTRATION_COMMIT, frozen_hashes=FROZEN)


def order(index):
    return METHODS if index % 2 == 0 else ("M0", "M1", "EF", "A1", "A0")
