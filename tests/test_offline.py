"""Offline checks (no internet, no API key). Run:  python tests/test_offline.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import complaints  # noqa: E402
import mcp_bridge  # noqa: E402
import registry  # noqa: E402
from rag import Index  # noqa: E402

ok = fail = 0


def check(name, cond):
    global ok, fail
    print(("PASS " if cond else "FAIL ") + name)
    ok, fail = ok + bool(cond), fail + (not cond)


ix = Index()
check("knowledge base loaded (>500 passages)", ix.stats()["passages"] > 500)
r = ix.lookup("act", "18"); check("Act s.18 lookup", r["found"] and "Return of amount" in r["text"])
r = ix.lookup("act", "2", "k"); check("Act s.2(k) carpet area", r["found"] and "net usable floor area" in r["text"])
r = ix.lookup("act", "13"); check("Act s.13 ten per cent", r["found"] and "ten per cent" in r["text"])
r = ix.lookup("rules", "16"); check("Rules r.16 MCLR plus two", r["found"] and "marginal cost of lending" in r["text"])
r = ix.lookup("act", "999"); check("non-existent section refused", not r["found"])
hits = ix.search("rate of interest highest marginal cost of lending rate plus two percent", 5)
check("search finds interest rule", any("marginal cost" in p.text.lower() for p, _ in hits))
d = registry.check_registration("PRM/KA/RERA/1251/310/PR/170915/000063")
check("register: approved project found", d["found"] and d["matches"][0]["status"] == "APPROVED")
d = registry.check_registration("PRM/KA/RERA/1248/469/PR/210804/004232")
check("register: withdrawn project flagged", d["found"] and d["matches"][0]["red_flag_status"])
d = registry.check_registration("PRM/KA/RERA/0000/000/PR/000000/000000")
check("register: fake number not found", not d["found"])
d = registry.search_projects("Saffron Meadows", district="Bengaluru Urban")
check("register: Saffron Meadows not found, similar listed", not d["found"] and d.get("similar_but_different_projects"))
tools, err = mcp_bridge.list_tools()
check("MCP server lists 5 tools" + (f" ({err})" if err else ""), not err and len(tools) == 5)
data, info = mcp_bridge.call("check_registration", {"registration_no": "PRM/KA/RERA/1251/310/PR/170915/000063"})
check("MCP call works: " + info["via"], info["via"].startswith("MCP") and data["found"])
s = complaints.complaints_summary()
check("complaints: totals match the site", s["complaints_total_on_site"] == 13461 and s["recovery_certificates"] == 2694
      and s["recovered_certificates"] == 356 and s["recovery_amount_rs"] == 12531190831)
d = complaints.complaint_history(project_name="Mantri Webcity2B")
check("complaints: named project found with recovery certificates",
      d["found"] and d["complaints_against_project"]["complaints"] > 0 and d["revenue_recovery_certificates"]["against_this_project"]["certificates"] > 0)
d = complaints.complaint_history(registration_no="PRM/KA/RERA/1251/310/PR/170915/000063")
check("complaints: lookup by registration number uses register names", d["looked_up"]["names_from"].startswith("registration"))
d = complaints.complaint_history(project_name="Saffron Meadows")
check("complaints: fictional project has none, with a caution", not d["found"] and "does not prove" in d["note"])
data, info = mcp_bridge.call("complaint_history", {"project_name": "Ozone Urbana", "promoter": "", "registration_no": ""})
check("MCP complaint_history works: " + info["via"], info["via"].startswith("MCP") and data["found"])
print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
