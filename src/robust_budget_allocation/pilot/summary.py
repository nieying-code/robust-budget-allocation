"""Descriptive pilot diagnosis and capacity arithmetic, never formal inference."""

import json
from statistics import median

from robust_budget_allocation.algorithms.common import tolerance
from .configuration import METHODS, SCOPE


def describe(values):
    return dict(min=min(values), median=median(values), max=max(values))


def summarize(bundle):
    decoded = [(json.loads(r["files"]["record.json"]), json.loads(r["files"]["result.json"]),
                sum(e["bytes"] for e in r["manifest"]["files"])) for r in bundle["runs"]]
    successful = [(r, v, b) for r, v, b in decoded if r["status"] == "success/certified"]
    per_method = {}
    for method in METHODS:
        rows = [(r, v, b) for r, v, b in successful if r["method"] == method]
        if not rows:
            continue
        per_method[method] = dict(count=len(rows),
            algorithm_seconds=describe([v["metrics"]["algorithm_seconds"] for r, v, b in rows]),
            supervisor_wall_seconds=describe([r["watchdog"]["wall_seconds"] for r, v, b in rows]),
            bytes=describe([b for r, v, b in rows]),
            python_peak_bytes=describe([v["timing"]["python_call_peak_bytes"] for r, v, b in rows]),
            process_peak_rss_bytes=describe([v["timing"]["process_lifetime_peak_rss_bytes"] or 0 for r, v, b in rows]),
            workload={key: describe([v["metrics"][key] for r, v, b in rows]) for key in
                ("iterations", "exact_oracle_calls", "scenario_evaluations", "active_size")},
            totals={key: sum(v["metrics"][key] for r, v, b in rows) for key in
                ("phase_i_hits", "phase_ii_hits", "phase_iii_calls", "exact_oracle_calls",
                 "complete_oracle_calls", "scenario_evaluations", "iterations", "scenarios_added")})
    groups = {}
    for r, v, b in successful:
        groups.setdefault(r["config_id"], {})[r["method"]] = (r, v, b)
    observations, ratios, pair_times, pair_walls, pair_bytes = [], [], [], [], []
    for name, group in groups.items():
        if set(group) != set(METHODS):
            continue
        r, ef, _ = group["EF"]
        a0, a1 = group["A0"][1]["metrics"], group["A1"][1]["metrics"]
        ratios.append(a1["algorithm_seconds"]/a0["algorithm_seconds"])
        pair_times.append(a0["algorithm_seconds"]+a1["algorithm_seconds"])
        pair_walls.append(group["A0"][0]["watchdog"]["wall_seconds"]+group["A1"][0]["watchdog"]["wall_seconds"])
        pair_bytes.append(group["A0"][2]+group["A1"][2])
        obj = {m: group[m][1]["metrics"]["objective"] for m in METHODS}
        m = ef["mechanism"]
        observations.append(dict(config_id=name, config=r["binding"]["config"], objectives=obj,
            delta_reliability=obj["M0"]-obj["M1"], delta_option=obj["M1"]-obj["EF"],
            q=m["q"], quantity=m["quantity"], C_Q=m["C_Q"], C_R=m["C_R"],
            y_F=m["y_F"], option_fee=m["option_fee"], reliability_choice=m["reliability_choice"],
            paid_suppliers=m["paid_suppliers"], exercise_scenarios=sum(x["E"] > tolerance(x["E"], 0) for x in m["scenarios"]),
            E_range=[min(x["E"] for x in m["scenarios"]), max(x["E"] for x in m["scenarios"])],
            unused_cash_range=[min(x["unused_budget"] for x in m["scenarios"]), max(x["unused_budget"] for x in m["scenarios"])],
            unused_resource_range=[min(x["h"] for x in m["scenarios"]), max(x["h"] for x in m["scenarios"])],
            A0=a0, A1=a1))
    model_risk = bool(observations) and all(
        abs(o["delta_reliability"]) <= tolerance(o["objectives"]["M0"], o["objectives"]["M1"])
        and abs(o["delta_option"]) <= tolerance(o["objectives"]["M1"], o["objectives"]["EF"])
        and o["y_F"] == 0 and o["paid_suppliers"] == 0 for o in observations)
    model_risk = model_risk and all(all(
        abs(o["q"][j]-observations[0]["q"][j]) <= tolerance(o["q"][j], observations[0]["q"][j])
        for j in o["q"]) for o in observations)
    algorithm_risk = False
    if observations:
        algorithm_risk = (all(o["A1"]["phase_i_hits"]+o["A1"]["phase_ii_hits"] == 0
            and o["A1"]["phase_iii_calls"] == o["A1"]["iterations"]
            and o["A1"]["exact_oracle_calls"] >= o["A0"]["exact_oracle_calls"]
            and o["A1"]["scenario_evaluations"] >= o["A0"]["scenario_evaluations"] for o in observations)
            and median(ratios) > 1.20)
    projection = {}
    if pair_times:
        for count in (100, 1000):
            projection[str(count)+"_pairs"] = dict(
                algorithm_hours_median=count*median(pair_times)/3600,
                algorithm_hours_observed_slow=count*max(pair_times)/3600,
                end_to_end_hours_median=count*median(pair_walls)/3600,
                end_to_end_hours_observed_slow=count*max(pair_walls)/3600,
                contingency_hours_2x_slow=count*max(pair_walls)*2/3600,
                raw_storage_bytes_median=count*median(pair_bytes),
                raw_storage_bytes_observed_max=count*max(pair_bytes),
                contingency_storage_bytes_2x=count*max(pair_bytes)*2)
    narrow = []
    if observations and not any(o["y_F"] for o in observations):
        narrow.append("Option never selected in this coverage; B/C/E unresolved, not proof of structural worthlessness")
    if observations and not any(o["paid_suppliers"] for o in observations):
        narrow.append("Reliability never selected in this coverage; A/B/C/E unresolved")
    if observations and not any(o["A1"]["phase_i_hits"] for o in observations):
        narrow.append("No Memory hit in pilot; B/D/E coverage/mechanism risk, no redesign authorized")
    status = "N6_BLOCKED" if bundle["status"] != "PASS" else (
        "N6_SCIENTIFIC_INFORMATIVENESS_RISK" if model_risk or algorithm_risk else "N6_READY_FOR_PR_REVIEW")
    return dict(classification=SCOPE, state=status, successful_runs=len(successful),
        failed_runs=len(decoded)-len(successful), completed_pairs=len(observations),
        model_severe_risk=model_risk, algorithm_severe_risk=algorithm_risk,
        narrow_coverage_warnings=narrow, per_method=per_method, observations=observations,
        projection=projection, projection_scope="illustrative measured-size A0/A1 pairs, not an N7 matrix or OOS estimate",
        memory_caveat="Python call peak excludes native solver; RSS is process lifetime, not call-only")
