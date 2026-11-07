"""Offline checks (no internet, no API key). Run:  python tests/test_offline.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
check("MCP server lists 3 tools" + (f" ({err})" if err else ""), not err and len(tools) == 3)
data, info = mcp_bridge.call("check_registration", {"registration_no": "PRM/KA/RERA/1251/310/PR/170915/000063"})
check("MCP call works: " + info["via"], info["via"].startswith("MCP") and data["found"])
print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
