"""Mane Mitra - Karnataka home buyer RERA helper (student project, TAPMI TLM).

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import html
import io
import json
import os
import time
from pathlib import Path

import streamlit as st

import agent
import complaints
import mcp_bridge
import registry
from rag import SOURCES, Index

APP_DIR = Path(__file__).parent
SAMPLE = APP_DIR / "data" / "Sample_Agreement_Saffron_Meadows.txt"

st.set_page_config(page_title="Mane Mitra | RERA helper", page_icon="🏠", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1100px;}
.mm-hero {background: linear-gradient(135deg,#0f3d5e 0%,#1b6a8f 100%); color:#fff; padding:18px 22px;
          border-radius:14px; margin-bottom:14px;}
.mm-hero h1 {color:#fff; font-size:1.7rem; margin:0 0 4px 0;}
.mm-hero p {margin:0; opacity:.92; font-size:.95rem;}
.mm-chip {display:inline-block; background:rgba(255,255,255,.16); border-radius:999px; padding:2px 10px;
          margin:8px 6px 0 0; font-size:.78rem;}
.mm-step {border-left:3px solid #1b6a8f; padding:4px 10px; margin:6px 0; background:rgba(27,106,143,.06);
          border-radius:0 8px 8px 0; font-size:.88rem;}
.mm-pass {font-size:.82rem; opacity:.9; margin-bottom:8px;}
</style>
""", unsafe_allow_html=True)


# ---------------- resources ----------------
@st.cache_resource(show_spinner="Loading the official sources...")
def load_index() -> Index:
    return Index()


@st.cache_resource(show_spinner="Connecting to the K-RERA registry MCP server...")
def mcp_status():
    return mcp_bridge.list_tools()


def get_api_key() -> str:
    try:
        k = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:  # no secrets file
        k = ""
    return k or os.environ.get("GEMINI_API_KEY", "") or st.session_state.get("saved_key", "")


def _save_key():
    # Copy the typed key to a normal session value: a text box's own value is deleted
    # by Streamlit as soon as the box stops being drawn.
    st.session_state["saved_key"] = (st.session_state.get("user_key") or "").strip()


def get_model() -> str:
    chosen = st.session_state.get("model_choice", "Automatic (newest Flash)")
    if chosen and not chosen.startswith("Automatic"):
        return chosen
    try:
        return st.secrets.get("GEMINI_MODEL", "")
    except Exception:
        return os.environ.get("GEMINI_MODEL", "")


def read_upload(f) -> str:
    name = f.name.lower()
    data = f.getvalue()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".docx"):
        import docx
        d = docx.Document(io.BytesIO(data))
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return "\n".join(parts)
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)
    return ""


index = load_index()
tools_found, mcp_err = mcp_status()

ss = st.session_state
ss.setdefault("messages", [])
ss.setdefault("agreement", "")
ss.setdefault("agreement_name", "")
ss.setdefault("pending", "")

# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown("### 🏠 Mane Mitra")
    st.caption("Karnataka home buyer RERA helper · English and ಕನ್ನಡ")

    if not get_api_key():
        st.text_input("Gemini API key", type="password", key="user_key", on_change=_save_key,
                      help="Stored only for this browser session. For the shared app, the owner sets it in Secrets.")

    st.markdown("**📄 Your agreement (optional)**")
    up = st.file_uploader("Upload .txt, .docx or .pdf", type=["txt", "docx", "pdf"], label_visibility="collapsed")
    if up is not None and up.name != ss.agreement_name:
        ss.agreement, ss.agreement_name = read_upload(up), up.name
    c1, c2 = st.columns(2)
    if c1.button("Use sample", use_container_width=True, help="Fictional 'Saffron Meadows' agreement with planted problems"):
        ss.agreement, ss.agreement_name = SAMPLE.read_text(encoding="utf-8"), SAMPLE.name
    if c2.button("Remove", use_container_width=True, disabled=not ss.agreement):
        ss.agreement, ss.agreement_name = "", ""
    if ss.agreement:
        st.success(f"Attached: {ss.agreement_name} ({len(ss.agreement):,} characters)")

    st.markdown("**💬 Try a question**")
    examples = [
        "Review this agreement and list all the risky clauses.",
        "If my builder delays possession, what are my rights?",
        "ಬಿಲ್ಡರ್ ಮನೆ ಹಸ್ತಾಂತರವನ್ನು ತಡ ಮಾಡಿದರೆ ನನಗೆ ಯಾವ ಹಕ್ಕುಗಳಿವೆ?",
        "How much booking amount can a builder take before the agreement?",
        "Check whether 'Saffron Meadows' in Whitefield is RERA registered.",
        "Check the RERA registration and complaint record of 'Ozone Urbana'.",
        "What is carpet area?",
    ]
    for i, q in enumerate(examples):
        if st.button(q, key=f"ex{i}", use_container_width=True):
            ss.pending = q

    st.divider()
    if st.button("🧹 New chat", use_container_width=True):
        ss.messages = []
        st.rerun()
    if ss.messages:
        st.download_button("⬇️ Download chat + evidence (JSON)", use_container_width=True,
                           file_name=f"mane_mitra_chat_{time.strftime('%Y%m%d_%H%M')}.json",
                           data=json.dumps(ss.messages, ensure_ascii=False, indent=2))

    if get_api_key():
        try:
            from google import genai as _genai
            names = agent.available_models(_genai.Client(api_key=get_api_key()), get_api_key())
        except Exception:  # noqa: BLE001
            names = list(agent.FALLBACK_MODELS)
        st.selectbox("Gemini model", ["Automatic (newest Flash)"] + names, key="model_choice",
                     help="Models your key can use, newest first. Automatic tries them in this order.")

    with st.expander("⚙️ System status"):
        stats = index.stats()
        st.write(f"**Knowledge base:** {stats['passages']} passages from {len(stats['per_source'])} official documents")
        for s, n in stats["per_source"].items():
            st.caption(f"• {s}: {n}")
        summ = registry.register_summary()
        st.write(f"**K-RERA register:** {summ['records']:,} records (data as of {summ['data_as_of']})")
        cs = complaints.complaints_summary()
        st.write(f"**K-RERA complaint records:** {cs['complaints_total_on_site']:,} complaints across "
                 f"{cs['project_names_with_complaints']:,} project names; {cs['recovery_certificates']:,} recovery "
                 f"certificates ({cs['recovered_certificates']} marked recovered); data as of {cs['data_as_of']}")
        if mcp_err:
            st.warning(f"MCP server not reachable, using direct lookup. {mcp_err}")
        else:
            st.write("**MCP server:** krera-registry connected · tools: " + ", ".join(tools_found))

# ---------------- header ----------------
st.markdown("""
<div class="mm-hero">
  <h1>Mane Mitra · ಮನೆ ಮಿತ್ರ</h1>
  <p>Understand your flat sale agreement before you sign. Plain English or simple Kannada, checked against official Karnataka RERA sources.</p>
  <span class="mm-chip">📚 8 official documents</span><span class="mm-chip">🗂️ 10,096 K-RERA project records</span><span class="mm-chip">⚖️ 13,461 complaints · 2,694 recovery orders</span>
  <span class="mm-chip">🔌 MCP registry tool</span><span class="mm-chip">🔍 shows its evidence</span>
</div>
""", unsafe_allow_html=True)
st.caption("Student project (TAPMI). General information from official sources, not legal advice. "
           "Do not type Aadhaar, PAN, bank or phone numbers.")


def show_trace(trace: list[dict], meta: dict):
    label = f"🔍 How I got this answer · {len(trace)} tool call(s)"
    if meta.get("model"):
        label += f" · {meta['model']} · {meta.get('seconds', '')}s"
    with st.expander(label):
        if not trace:
            st.caption("No tool was called for this answer.")
        for i, s in enumerate(trace, 1):
            args = ", ".join(f"{k}={v!r}" for k, v in s["args"].items() if v)
            via = s.get("via", "")
            st.markdown(f"<div class='mm-step'><b>Step {i}: {s['tool']}</b>({args})<br>"
                        f"<small>via {via} · {s.get('ms', '?')} ms</small></div>", unsafe_allow_html=True)
            for p in s.get("passages", [])[:6]:
                st.markdown(f"**{p['source']}**, {p['where']} · _{p['authority']}_")
                body = html.escape(p["text"][:700] + ("…" if len(p["text"]) > 700 else "")).replace("\n", "<br>")
                st.markdown(f"<div class='mm-pass'>{body}</div>", unsafe_allow_html=True)
            if s.get("data"):
                st.json(s["data"], expanded=False)
            if s.get("error"):
                st.caption(f"MCP error: {s['error']}")


for m in ss.messages:
    with st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else "🏠"):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            show_trace(m.get("trace", []), m.get("meta", {}))

if not ss.messages:
    st.info("Ask a question below, or attach your agreement in the left panel and ask me to review it. "
            "ಕನ್ನಡದಲ್ಲೂ ಕೇಳಬಹುದು.")

prompt = st.chat_input("Ask about your agreement, your rights, or a project's RERA registration…")
if ss.pending and not prompt:
    prompt, ss.pending = ss.pending, ""

if prompt:
    key = get_api_key()
    ss.messages.append({"role": "user", "content": prompt + (f"\n\n📎 _{ss.agreement_name}_" if ss.agreement else "")})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(ss.messages[-1]["content"])
    with st.chat_message("assistant", avatar="🏠"):
        if not key:
            st.error("Add a Gemini API key in the left panel first.")
            ss.messages.pop()
        else:
            with st.spinner("Searching the official sources and the K-RERA register…"):
                history = [{"role": m["role"], "content": m["content"]} for m in ss.messages[:-1]]
                turn = agent.answer(key, index, prompt, history, ss.agreement, get_model())
            if turn.error:
                st.error(turn.error)
                ss.messages.pop()
            else:
                st.markdown(turn.answer)
                meta = {"model": turn.model, "seconds": turn.seconds}
                show_trace(turn.trace, meta)
                ss.messages.append({"role": "assistant", "content": turn.answer, "trace": turn.trace, "meta": meta})
