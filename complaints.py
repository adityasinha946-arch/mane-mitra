"""K-RERA complaint and recovery records.

Data (all from rera.karnataka.gov.in, collected 7 Nov 2026, cleaned by 03_Clean/clean_complaints.py):
  - Complaints by project (2,479 names) and by promoter (2,036 names): 13,461 complaints in total.
    These are COUNTS published by K-RERA, not the complaints themselves.
  - Revenue Recovery Certificates: 2,694 orders, 356 marked as recovered.
  - Complaint Realization list: 1,074 complaints with money realised or settled.
Matching is by name (K-RERA's complaint reports carry no registration number), so the same name
can belong to different projects. The answer always shows the names exactly as K-RERA wrote them.
Complainant names are not stored.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

import registry

DATA = Path(__file__).parent / "data"
DATA_DATE = "7 Nov 2026"
FILES = {
    "project": DATA / "KRERA_Complaints_by_Project_2026-11-07.csv",
    "promoter": DATA / "KRERA_Complaints_by_Promoter_2026-11-07.csv",
    "rrc": DATA / "KRERA_Recovery_Certificates_2026-11-07.csv",
    "realization": DATA / "KRERA_Complaint_Realization_2026-11-07.csv",
}
CAVEATS = [
    "A complaint is a buyer's allegation filed with K-RERA, not a finding against the builder.",
    "Large builders with many flats usually have more complaints; compare with the project's size.",
    "K-RERA's complaint reports list names, not registration numbers, so a name match can include a different project with the same name.",
    "A revenue recovery certificate (RRC) is issued when money that K-RERA ordered to be paid was not paid; it is then recoverable as arrears of land revenue (RERA Act s.40(1)).",
]


def key(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", re.sub(r"\s+", " ", str(s or "")).strip().upper())


def promoter_key(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip().upper().replace("&", " AND ")
    s = re.sub(r"\bM\s*/\s*S\.?|\bMESSRS\b", " ", s)
    s = re.sub(r"\b(PVT|PRIVATE|LTD|LIMITED|LLP|CO|COMPANY)\b\.?", " ", s)
    return re.sub(r"[^A-Z0-9]", "", s)


@lru_cache(maxsize=None)
def _load(name: str) -> list[dict]:
    with open(FILES[name], encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _counts(table: str, k: str, name_col: str) -> dict:
    rows = [r for r in _load(table) if k and r["MATCH_KEY"] == k]
    return {"complaints": sum(_int(r["COMPLAINTS"]) for r in rows),
            "names_on_report": sorted({r[name_col] for r in rows})}


def _rrc(pk: str, mk: str) -> dict:
    by_project = [r for r in _load("rrc") if pk and r["PROJECT_KEY"] == pk]
    by_promoter = [r for r in _load("rrc") if mk and r["PROMOTER_KEY"] == mk]

    def summ(rows):
        rec = [r for r in rows if r["RECOVERED"] == "yes"]
        latest = sorted(rows, key=lambda r: r["RRC_DATE"], reverse=True)[:3]
        return {"certificates": len(rows), "amount_rs": sum(_int(r["AMOUNT_RS"]) for r in rows),
                "marked_recovered": len(rec), "recovered_amount_rs": sum(_int(r["AMOUNT_RS"]) for r in rec),
                "latest": [{"complaint_no": r["COMPLAINT_NO"], "project": r["PROJECT"], "amount_rs": _int(r["AMOUNT_RS"]),
                            "rrc_date": r["RRC_DATE"], "recovered": r["RECOVERED"]} for r in latest]}
    return {"against_this_project": summ(by_project), "against_this_promoter_all_projects": summ(by_promoter)}


def _realization(pk: str) -> dict:
    rows = [r for r in _load("realization") if pk and r["PROJECT_KEY"] == pk]
    return {"complaints_listed": len(rows), "amount_realised_rs": sum(_int(r["AMOUNT_RS"]) for r in rows),
            "settled_in_lok_adalat": sum("lok adalat" in r["REMARKS"].lower() for r in rows)}


def complaint_history(project_name: str = "", promoter: str = "", registration_no: str = "") -> dict:
    """Complaint counts and recovery certificates for a project and its promoter."""
    source = "names given by the user"
    if registration_no:
        reg = registry.check_registration(registration_no)
        if reg.get("found"):
            m = reg["matches"][0]
            project_name = project_name or m["project_name"]
            promoter = promoter or m["promoter"]
            source = f"registration {m['registration_no']} in the K-RERA register"
        elif not (project_name or promoter):
            return {"found": False, "data_as_of": DATA_DATE,
                    "note": "Registration number not found in the register, so there is no name to look up complaints for."}
    pk, mk = key(project_name), promoter_key(promoter)
    if not pk and not mk:
        return {"found": False, "data_as_of": DATA_DATE, "note": "Give a project name, promoter name or registration number."}
    proj = _counts("project", pk, "PROJECT_NAME_ON_REPORT")
    prom = _counts("promoter", mk, "PROMOTER_NAME_ON_REPORT")
    rrc = _rrc(pk, mk)
    real = _realization(pk)
    any_hit = proj["complaints"] or prom["complaints"] or rrc["against_this_project"]["certificates"] \
        or rrc["against_this_promoter_all_projects"]["certificates"] or real["complaints_listed"]
    return {
        "found": bool(any_hit),
        "looked_up": {"project_name": project_name, "promoter": promoter, "names_from": source},
        "data_as_of": DATA_DATE,
        "complaints_against_project": proj,
        "complaints_against_promoter_all_projects": prom,
        "revenue_recovery_certificates": rrc,
        "complaint_realization_list": real,
        "note": ("Exact name match in K-RERA's complaint reports." if any_hit else
                 "No complaints or recovery certificates found under these exact names. This does not prove there are none: "
                 "names can be spelled differently. Search the complaint pages on rera.karnataka.gov.in."),
        "caveats": CAVEATS,
        "source": "K-RERA website: project and promoter complaint reports, Revenue Recovery list, Complaint Realization list",
    }


def complaints_summary() -> dict:
    p, q = _load("project"), _load("promoter")
    rrc = _load("rrc")
    rec = [r for r in rrc if r["RECOVERED"] == "yes"]
    return {"data_as_of": DATA_DATE,
            "complaints_total_on_site": 13461,
            "project_names_with_complaints": len(p), "promoter_names_with_complaints": len(q),
            "recovery_certificates": len(rrc), "recovery_amount_rs": sum(_int(r["AMOUNT_RS"]) for r in rrc),
            "recovered_certificates": len(rec), "recovered_amount_rs": sum(_int(r["AMOUNT_RS"]) for r in rec),
            "realization_list_rows": len(_load("realization"))}
