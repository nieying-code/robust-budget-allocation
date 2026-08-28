"""Model-independent verification of original JUnit evidence for passed gates."""

import hashlib
import xml.etree.ElementTree as ET


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
            rows = list(root.iter("testsuite"))
            counts = {key: 0 for key in keys}
            for row in rows:
                for key in keys:
                    value = int(row.attrib.get(key, "0"))
                    if value < 0:
                        raise ValueError("negative JUnit count")
                    counts[key] += value
        except (ET.ParseError, ValueError) as exc:
            raise ValueError("invalid gate XML") from exc
        if any(type(saved[key]) is not int or counts[key] != saved[key] for key in keys):
            raise ValueError("gate XML counts")
        if (type(saved["returncode"]) is not int or saved["returncode"] != 0
                or counts["failures"] or counts["errors"]
                or counts["tests"] <= counts["skipped"]
                or (counts["skipped"] and not allow_skips)):
            raise ValueError("failed/skipped/empty gate suite")
    return True
