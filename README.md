# Mane Mitra · ಮನೆ ಮಿತ್ರ

A chatbot for first-time home buyers in Karnataka. It explains flat sale agreements in plain English or simple Kannada, flags risky clauses against official Karnataka RERA sources, checks a project in the K-RERA register, and shows its K-RERA complaint and recovery record. Student project, TAPMI (TLM). General information, not legal advice.

## How it works
| Part | What it does | File |
|---|---|---|
| Knowledge base (RAG) | 8 official texts (RERA Act 2016, Karnataka RERA Rules 2017 EN + KN, K-RERA Regulations 2022, K-RERA model Agreement for Sale, MoHUA FAQs 2025, K-RERA FAQs) split into ~930 passages with page numbers; BM25 search plus exact "Act section N / Rule N" lookup | `rag.py`, `data/knowledge/` |
| MCP server | `krera-registry`, a real Model Context Protocol server (stdio) with tools `check_registration`, `search_projects`, `register_summary` over 10,096 K-RERA project records, and `complaint_history`, `complaints_summary` over K-RERA's complaint reports (13,461 complaints), 2,694 revenue recovery certificates (356 recovered) and 1,074 realization records (official, 7 Nov 2026; no complainant names) | `registry_mcp_server.py`, `registry.py`, `complaints.py`, `mcp_bridge.py` |
| Agent | Gemini decides which tools to call, reads the results, and answers in a fixed 5-heading format with citations | `agent.py`, `prompts.py` |
| App | Chat page, agreement upload, examples, and a "How I got this answer" trace for every answer | `app.py` |

Nothing is trained: answers are generated from passages retrieved at question time. The register is a snapshot; the live site rera.karnataka.gov.in is the final authority.

## Run on Windows
Double-click `run_app.bat`. Paste your Gemini API key in the left panel (kept only for that browser session).

## Run anywhere
```
pip install -r requirements.txt
python tests/test_offline.py
streamlit run app.py
```
For a hosted copy, set `GEMINI_API_KEY` in the host's secrets (see `.streamlit/secrets.toml.example`). Never commit the key.
