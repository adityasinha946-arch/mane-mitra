"""K-RERA project register lookups.

Data: 10,096 project records exported from rera.karnataka.gov.in on
7 November 2026 and cleaned (see 03_Clean in the project folder). This is a
snapshot; the live K-RERA website is the final authority.
"""
from __future__ import annotations

import csv
import difflib
import re
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "KRERA_Project_Register_2026-11-07.csv"
DATA_DATE = "7 Nov 2026"
RED_FLAG_STATUSES = {"REJECTED", "WITHDRAWN", "REVOKED", "LAPSED"}


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 1]


@lru_cache(maxsize=1)
def _rows() -> list[dict]:
    with open(DATA_FILE, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _public(r: dict) -> dict:
    yes = lambda v: str(v).strip().lower() in ("true", "yes", "1")
    ext = [n for k, n in (("HAS_COVID_EXTENSION", "COVID-19 extension"),
                          ("HAS_SECTION6_EXTENSION", "Section 6 extension"),
                          ("HAS_FURTHER_EXTENSION", "further extension")) if yes(r.get(k))]
    status = (r.get("STATUS") or "").strip().upper()
    return {
        "registration_no": r.get("REGISTRATION_NO") or "none (never registered)",
        "acknowledgement_no": r.get("ACKNOWLEDGEMENT_NO") or "",
        "project_name": r.get("PROJECT_NAME", ""),
        "promoter": r.get("PROMOTER_NAME", ""),
        "status": status,
        "red_flag_status": status in RED_FLAG_STATUSES,
        "district": r.get("DISTRICT", ""),
        "taluk": r.get("TALUK", ""),
        "project_type": r.get("PROJECT_TYPE", ""),
        "approved_on": r.get("APPROVED_ON") or "not approved",
        "completion_date_at_registration": r.get("ORIGINAL_COMPLETION_DATE", ""),
        "current_completion_date": r.get("CURRENT_COMPLETION_DATE", ""),
        "days_later_than_original": r.get("DELAY_DAYS", ""),
        "extensions": ext or ["none recorded"],
    }


def _wrap(found: bool, matches: list[dict], note: str, similar: list[str] | None = None) -> dict:
    out = {"found": found, "data_as_of": DATA_DATE, "matches": matches, "note": note,
           "final_authority": "Live K-RERA website rera.karnataka.gov.in"}
    if similar:
        out["similar_but_different_projects"] = similar
    return out


def check_registration(registration_no: str) -> dict:
    """Exact lookup by registration number (or acknowledgement number)."""
    key = _norm(registration_no)
    if not key:
        return _wrap(False, [], "No registration number given.")
    hits = [r for r in _rows() if key in (_norm(r.get("REGISTRATION_NO")), _norm(r.get("ACKNOWLEDGEMENT_NO")))]
    if hits:
        return _wrap(True, [_public(r) for r in hits[:5]], f"Exact match in the K-RERA register (data as of {DATA_DATE}).")
    return _wrap(False, [], f"Not found in the K-RERA register (data as of {DATA_DATE}). This is a red flag, not a sign of safety. "
                            "Check rera.karnataka.gov.in before paying anything.")


def search_projects(project_name: str = "", promoter: str = "", district: str = "", limit: int = 5) -> dict:
    """Name search. All words of the name must appear; otherwise similar names are listed as DIFFERENT projects."""
    qn, qp, qd = _words(project_name), _words(promoter), (district or "").strip().lower()
    if not qn and not qp:
        return _wrap(False, [], "Give a project name or promoter name.")
    rows = _rows()
    if qd:
        dist_rows = [r for r in rows if qd in (r.get("DISTRICT") or "").lower() or qd in (r.get("TALUK") or "").lower()]
        rows = dist_rows or rows

    def ok(r):
        name, prom = (r.get("PROJECT_NAME") or "").lower(), (r.get("PROMOTER_NAME") or "").lower()
        return all(w in name for w in qn) and all(w in prom for w in qp)

    hits = [r for r in rows if ok(r)]
    if hits:
        return _wrap(True, [_public(r) for r in hits[:limit]],
                     f"{len(hits)} record(s) match all the words given (showing up to {limit}). Confirm the registration number with the builder.")
    target = " ".join(qn or qp)
    pool = {(r.get("PROJECT_NAME") or "") for r in _rows()}
    close = difflib.get_close_matches(target, [p.lower() for p in pool], n=6, cutoff=0.6)
    lead = [p for p in pool if qn and qn[0] in p.lower()][:6] if qn else []
    similar = sorted({p for p in pool if p.lower() in close} | set(lead))[:6]
    return _wrap(False, [], f"Not found in the K-RERA register (data as of {DATA_DATE}). This is a red flag, not a sign of safety. "
                            "Any similar names are DIFFERENT projects. Check rera.karnataka.gov.in before paying anything.", similar)


def register_summary() -> dict:
    rows = _rows()
    by = {}
    for r in rows:
        by[r.get("STATUS", "")] = by.get(r.get("STATUS", ""), 0) + 1
    return {"records": len(rows), "by_status": by, "data_as_of": DATA_DATE}
