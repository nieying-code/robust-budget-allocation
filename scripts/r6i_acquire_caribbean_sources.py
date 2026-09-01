"""Acquire immutable R6-I Caribbean source inputs; this script never invokes a solver.

The EM-DAT custom extract is copied from the user-provided read-only source
library. Official/public remote files are downloaded once and subsequently
verified against the frozen acquisition ledger. CHN HTML is intentionally not
committed because the pages state "All Rights Reserved"; the exact pages remain
re-fetchable and their hashes are frozen in the ledger.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/formal/caribbean/raw"
LEDGER = RAW / "source_acquisition.json"

HURDAT_URL = (
    "https://www.nhc.noaa.gov/data/hurdat/"
    "hurdat2-1851-2025-02272026.txt"
)
WPP_URL = (
    "https://population.un.org/wpp/assets/Excel%20Files/"
    "1_Indicator%20(Standard)/CSV_FILES/"
    "WPP2024_Demographic_Indicators_Medium.csv.gz"
)
CHN_BASE_URL = "https://www.stormcarib.com/climatology/"

# Every CHN island/location page used for explicit source evidence. The mapping
# is deliberately visible and reviewable; it is not attributed to Balcik's
# unpublished merge decisions.
CHN_COUNTRY_PAGES: dict[str, tuple[str, ...]] = {
    "AIA": ("TQPF_all_isl.htm",),
    "ATG": ("TAPA_all_isl.htm", "TABA_all_isl.htm"),
    "BHS": (
        "MYAB_all_isl.htm",
        "MYGF_all_isl.htm",
        "MYBS_all_isl.htm",
        "MYSM_all_isl.htm",
        "MYNN_all_isl.htm",
        "MYEG_all_isl.htm",
        "MYIG_all_isl.htm",
    ),
    "BLZ": ("MZAC_all_isl.htm",),
    "BMU": ("TXKF_all_isl.htm",),
    "BRB": ("TBPB_all_isl.htm",),
    "BVI": ("TUPJ_all_isl.htm", "TUVG_all_isl.htm", "TUAN_all_isl.htm"),
    "CYM": ("MWCR_all_isl.htm", "MWLC_all_isl.htm", "MWCB_all_isl.htm"),
    "DMA": ("TDPD_all_isl.htm",),
    "GRD": ("TGPY_all_isl.htm",),
    "GUY": (),
    "HTI": ("MTPP_all_isl.htm",),
    "JAM": ("MKJP_all_isl.htm", "MKJS_all_isl.htm"),
    "KNA": ("TKNV_all_isl.htm", "TKPK_all_isl.htm"),
    "LCA": ("TLPC_all_isl.htm",),
    "MST": ("TKMN_all_isl.htm",),
    "SUR": (),
    "TCA": ("MBPV_all_isl.htm", "MBSC_all_isl.htm", "MBGT_all_isl.htm"),
    "TTO": ("TTPT_all_isl.htm", "TTPP_all_isl.htm"),
    "VCT": ("TVSV_all_isl.htm",),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "robust-budget-allocation-r6i-source-audit/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _copy_once(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(source, target)


def _file_record(
    *,
    identity: str,
    target: Path,
    source_url: str,
    source_role: str,
    committed: bool,
    license_note: str,
) -> dict[str, object]:
    return {
        "identity": identity,
        "source_url": source_url,
        "source_role": source_role,
        "local_path": target.relative_to(ROOT).as_posix(),
        "filename": target.name,
        "bytes": target.stat().st_size,
        "sha256": _sha256(target),
        "committed": committed,
        "license_note": license_note,
    }


def _find_one(source_library: Path, pattern: str) -> Path:
    matches = sorted(source_library.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one source-library match for {pattern!r}; "
            f"found {len(matches)}"
        )
    return matches[0]


def _restore_uncommitted_sources(ledger: dict[str, object]) -> None:
    """Re-fetch licensed-out raw pages without changing their frozen identity."""
    for record in ledger["sources"]:  # type: ignore[index]
        local_path = ROOT / record["local_path"]  # type: ignore[index]
        if local_path.exists() or record["committed"]:  # type: ignore[index]
            continue
        _download(str(record["source_url"]), local_path)  # type: ignore[index]


def _verify_frozen_ledger(ledger: dict[str, object]) -> None:
    for record in ledger["sources"]:  # type: ignore[index]
        local_path = ROOT / record["local_path"]  # type: ignore[index]
        if not local_path.exists():
            raise RuntimeError(f"frozen source missing: {local_path}")
        observed = _sha256(local_path)
        expected = record["sha256"]  # type: ignore[index]
        if observed != expected:
            raise RuntimeError(
                f"frozen source hash mismatch for {local_path}: "
                f"expected {expected}, observed {observed}"
            )


def _verify_source_library_evidence(ledger: dict[str, object], source_library: Path) -> None:
    evidence = ledger["source_library"]  # type: ignore[index]
    xlsx = source_library / str(evidence["emdat_xlsx_filename"])  # type: ignore[index]
    if not xlsx.exists():
        raise RuntimeError(f"source-library EM-DAT XLSX missing: {xlsx}")
    if _sha256(xlsx) != evidence["emdat_xlsx_sha256"]:  # type: ignore[index]
        raise RuntimeError(f"source-library EM-DAT XLSX hash mismatch: {xlsx}")


def acquire(source_library: Path) -> dict[str, object]:
    emdat_csv_source = _find_one(
        source_library,
        "public_emdat_custom_request_2026-09-01_*.csv",
    )
    emdat_xlsx_source = _find_one(
        source_library,
        "public_emdat_custom_request_2026-09-01_*.xlsx",
    )

    emdat_csv = RAW / "emdat" / emdat_csv_source.name
    hurdat = RAW / "hurdat2" / "hurdat2-1851-2025-02272026.txt"
    wpp = RAW / "population" / "WPP2024_Demographic_Indicators_Medium.csv.gz"
    chn_dir = RAW / "chn"
    chn_frequency = chn_dir / "freq.htm"

    _copy_once(emdat_csv_source, emdat_csv)
    if not hurdat.exists():
        _download(HURDAT_URL, hurdat)
    if not wpp.exists():
        _download(WPP_URL, wpp)
    if not chn_frequency.exists():
        _download(CHN_BASE_URL + "freq.htm", chn_frequency)

    chn_targets: list[tuple[str, Path]] = [("frequency", chn_frequency)]
    for paper_code, pages in CHN_COUNTRY_PAGES.items():
        for page in pages:
            target = chn_dir / page
            if not target.exists():
                _download(CHN_BASE_URL + page, target)
            chn_targets.append((paper_code, target))

    sources: list[dict[str, object]] = [
        _file_record(
            identity="EMDAT_PUBLIC_CUSTOM_REQUEST_2026_08_28",
            target=emdat_csv,
            source_url="https://public.emdat.be/",
            source_role="explicit_country_impact_evidence",
            committed=True,
            license_note="EM-DAT public data; cite CRED/UCLouvain and preserve extraction metadata.",
        ),
        _file_record(
            identity="NHC_HURDAT2_ATLANTIC_1851_2025_2026_02_27",
            target=hurdat,
            source_url=HURDAT_URL,
            source_role="primary_storm_identity_track_and_intensity",
            committed=True,
            license_note="Official NOAA/NHC public data.",
        ),
        _file_record(
            identity="UN_WPP_2024_MEDIUM_DEMOGRAPHIC_INDICATORS",
            target=wpp,
            source_url=WPP_URL,
            source_role="event_year_population_denominator",
            committed=True,
            license_note="United Nations WPP 2024; CC BY 3.0 IGO attribution applies.",
        ),
    ]
    for paper_code, target in chn_targets:
        record = _file_record(
            identity=f"CHN_CURRENT_{target.stem.upper()}",
            target=target,
            source_url=CHN_BASE_URL + target.name,
            source_role=(
                "proximity_convention_and_page_index"
                if paper_code == "frequency"
                else "explicit_affected_island_evidence"
            ),
            committed=False,
            license_note=(
                "Page states All Rights Reserved; raw HTML is local-only. "
                "Git stores retrieval instructions, hash, and normalized factual evidence."
            ),
        )
        record["paper_country_code"] = paper_code
        sources.append(record)

    ledger = {
        "schema_version": 1,
        "document_type": "R6_I_CARIBBEAN_SOURCE_ACQUISITION",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_library": {
            "identity": "USER_PROVIDED_READ_ONLY_SOURCE_LIBRARY",
            "path": str(source_library),
            "emdat_xlsx_filename": emdat_xlsx_source.name,
            "emdat_xlsx_bytes": emdat_xlsx_source.stat().st_size,
            "emdat_xlsx_sha256": _sha256(emdat_xlsx_source),
            "emdat_xlsx_committed": False,
        },
        "rules": {
            "hurdat_role": "primary storm identity, track, and intensity",
            "chn_role": "explicit island evidence under page-stated 60 nautical mile convention",
            "emdat_role": "explicit country-impact evidence when unambiguously matched",
            "wpp_role": "R6-I reconstruction population denominator; not Balcik original source",
            "chn_country_pages": {
                code: list(pages) for code, pages in CHN_COUNTRY_PAGES.items()
            },
        },
        "sources": sources,
    }
    return ledger


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-library",
        type=Path,
        default=ROOT.parents[1],
        help="read-only directory containing the user-provided EM-DAT files",
    )
    args = parser.parse_args()

    if LEDGER.exists():
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        _restore_uncommitted_sources(ledger)
        _verify_frozen_ledger(ledger)
        _verify_source_library_evidence(ledger, args.source_library.resolve())
        print(json.dumps({"status": "PASS", "mode": "verify", "sources": len(ledger["sources"])}, indent=2))
        return 0

    ledger = acquire(args.source_library.resolve())
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _verify_frozen_ledger(ledger)
    print(json.dumps({"status": "PASS", "mode": "acquire", "sources": len(ledger["sources"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
