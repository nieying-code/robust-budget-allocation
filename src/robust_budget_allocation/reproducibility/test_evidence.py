"""Model-independent verification of original JUnit evidence for passed gates."""

import hashlib
import xml.etree.ElementTree as ET


def _case_counts(root):
    """Count actual cases once, validating each container's declarations.

    Support flat or nested JUnit suites without double-counting parent totals.
    Reject orphan/hidden cases and outcomes, rather than treating them as passes.
    """
    keys = ("tests", "failures", "errors", "skipped")
    outcomes = {"failure": "failures", "error": "errors", "skipped": "skipped"}
    seen_cases, seen_outcomes = set(), set()

    def visit(node):
        if node.tag not in ("testsuite", "testsuites"):
            raise ValueError("unsupported JUnit container")
        counts = dict.fromkeys(keys, 0)
        for child in node:
            if child.tag in ("testsuite", "testsuites"):
                nested = visit(child)
                for key in keys:
                    counts[key] += nested[key]
            elif child.tag == "testcase":
                if node.tag != "testsuite" or not child.get("name", "").strip():
                    raise ValueError("invalid/unnamed JUnit testcase")
                seen_cases.add(child)
                counts["tests"] += 1
                states = [state for state in child if state.tag in outcomes]
                if len(states) > 1:
                    raise ValueError("contradictory testcase outcomes")
                for state in states:
                    seen_outcomes.add(state)
                    counts[outcomes[state.tag]] += 1
        for key in keys:
            # Suite counters are required; optional wrapper totals must agree too.
            if node.tag == "testsuite" or key in node.attrib:
                if int(node.attrib[key]) != counts[key]:
                    raise ValueError("JUnit testcase/count mismatch")
        return counts

    counts = visit(root)
    if seen_cases != set(root.iter("testcase")):
        raise ValueError("orphan JUnit testcase")
    if seen_outcomes != {node for node in root.iter() if node.tag in outcomes}:
        raise ValueError("orphan JUnit outcome")
    return counts


def verify_junit_suites(suites, xml_files, *, allow_skips=False):
    """Recompute hashes/counts; callers retain their required suite inventory.

    XML values are original bytes (or their lossless UTF-8 archive strings).
    This verifies recorded execution evidence, not a new test or license run.
    """
    if not suites or set(suites) != set(xml_files):
        raise ValueError("gate XML inventory")
    keys = ("tests", "failures", "errors", "skipped")
    for name, saved in suites.items():
        raw = xml_files[name]
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != saved["xml_sha256"]:
            raise ValueError("gate XML hash")
        try:
            root = ET.fromstring(raw)
            counts = _case_counts(root)
        except (ET.ParseError, ValueError, KeyError) as exc:
            raise ValueError("invalid gate XML") from exc
        if any(type(saved[key]) is not int or counts[key] != saved[key] for key in keys):
            raise ValueError("gate XML counts")
        if (type(saved["returncode"]) is not int or saved["returncode"] != 0
                or counts["failures"] or counts["errors"]
                or counts["tests"] <= counts["skipped"]
                or (counts["skipped"] and not allow_skips)):
            raise ValueError("failed/skipped/empty gate suite")
    return True
