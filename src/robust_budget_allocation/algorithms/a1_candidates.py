"""Frozen deterministic shortage-exposure proxy, not recourse/UB estimation."""

import math

from .common import summarize_first

EVALUATION_LIMIT = 1


def candidate_plan(data, decision, active, inspected):
    summarize_first(data, decision)
    excluded, pool, scores = [], [], {}
    for w in sorted(data.base.scenarios):
        reason = "active" if w in active else "already_inspected" if w in inspected else None
        if reason:
            excluded.append(dict(scenario=w, reason=reason))
            continue
        received = sum(data.reliability.fulfillment[w][j][k]*decision["q_by_level"][j][k]
                       for j in data.base.suppliers for k in data.reliability.levels[j])
        score = data.base.shortage_penalty*max(data.base.demand[w]-received, 0.0)
        if not math.isfinite(score):
            raise ValueError("nonfinite candidate score")
        pool.append(w)
        scores[w] = score
    ranking = sorted(pool, key=lambda w: (-scores[w], w))
    return dict(pool=pool, excluded=excluded, scores=scores, ranking=ranking,
                planned=ranking[:EVALUATION_LIMIT])
