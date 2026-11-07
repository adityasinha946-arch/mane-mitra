"""Retrieval over the official source files (the "R" in RAG).

Nothing is trained. The official texts are split into short passages, and for
each question the passages that share the most important words with the
question are returned (BM25 ranking, a standard search-engine formula).
Every passage keeps its source file and page number, so answers can cite
exactly where they came from. For citations there is also an exact lookup of
"Act section N" and "Karnataka Rules rule N".
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "data" / "knowledge"

# file name -> (short label shown to users, type of authority)
SOURCES = {
    "RERA_Act_2016_KRERA_copy.txt": ("RERA Act 2016", "Act"),
    "Karnataka_RERA_Rules_2017_EN.txt": ("Karnataka RERA Rules 2017", "Karnataka Rules"),
    "Karnataka_RERA_Rules_2017_KN.txt": ("Karnataka RERA Rules 2017 (Kannada)", "Karnataka Rules"),
    "Karnataka_RERA_General_Regulations_2022.txt": ("K-RERA General Regulations 2022", "Regulations"),
    "KRERA_Proforma_Agreement_of_Sale.txt": ("K-RERA model Agreement for Sale (Proforma)", "Official model agreement"),
    "MoHUA_RERA_FAQs_July2025.txt": ("MoHUA RERA FAQs, July 2025", "Ministry guidance (not law)"),
    "KRERA_Act_FAQs.txt": ("K-RERA FAQs on the Act", "K-RERA guidance (not law)"),
    "KRERA_Rules_FAQs.txt": ("K-RERA FAQs on the Rules", "K-RERA guidance (not law)"),
}

CHUNK_CHARS = 1000
OVERLAP_CHARS = 200

STOPWORDS = set(
    "a an the and or of to in on for by with is are was be been as at it its this that these those "
    "any such shall may from which who whom what when where how if not no do does my me i we our you "
    "your can will would should there their them he she his her has have had into than then under".split()
)
_TOKEN = re.compile(r"[a-z0-9]+|[ಀ-೿]+")
_PAGE = re.compile(r"^\[Page (\d+)\]\s*$", re.M)
_PARA = re.compile(r"^\s*(\d{1,2}\.\d{1,2})\b", re.M)
# a section/rule heading in the body, e.g. "18. Return of amount and compensation.—(1)"
# or "16. Rate of interest payable by the promoter and the allottee.- The"
_HEADING = re.compile(r"^\s{0,12}(\d{1,3}[A-Z]?)\.\s+[A-Z][^\n]{2,160}?(?:\n[^\n]{0,160}?)?[.,]\s*[—–-]\s*(?:\(1\)|[A-Z(])", re.M)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower())
            if (t not in STOPWORDS and len(t) > 1) or t.isdigit()]


@dataclass
class Passage:
    pid: str
    file: str
    source: str
    authority: str
    page: str  # "p.N", or the nearest paragraph number for the Proforma
    text: str


def _pages(text: str) -> list[tuple[str, str]]:
    marks = list(_PAGE.finditer(text))
    if not marks:
        return [("", text)]
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1), text[m.end():end]))
    return out


def _split(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) <= CHUNK_CHARS:
        return [text] if text else []
    parts, start = [], 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):  # end on a line break or sentence end if one is near
            cut = max(text.rfind("\n", start + 600, end), text.rfind(". ", start + 600, end))
            if cut > 0:
                end = cut + 1
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP_CHARS, start + 1)
    return [p for p in parts if p]


class Index:
    def __init__(self, knowledge_dir: Path = KNOWLEDGE_DIR):
        self.dir = knowledge_dir
        self.passages: list[Passage] = []
        n = 0
        for fname, (label, authority) in SOURCES.items():
            path = knowledge_dir / fname
            if not path.exists():
                continue
            raw = path.read_text(encoding="utf-8")
            for page, body in _pages(raw):
                last_para = ""
                for chunk in _split(body):
                    if not page:  # Proforma: label with the clause number the passage starts in
                        found = _PARA.findall(chunk)
                        where = f"para {found[0]}" if found else (f"after para {last_para}" if last_para else "opening part")
                        if found:
                            last_para = found[-1]
                    else:
                        where = f"p.{page}"
                    n += 1
                    self.passages.append(Passage(f"P{n}", fname, label, authority, where, chunk))
        self._docs = [Counter(tokenize(p.text)) for p in self.passages]
        self._low = [re.sub(r"\s+", " ", p.text.lower()) for p in self.passages]
        self._alpha = [sum(ch.isalpha() for ch in p.text) / max(1, len(p.text)) for p in self.passages]
        self._len = [sum(d.values()) for d in self._docs]
        self._avg = sum(self._len) / max(1, len(self._len))
        df = Counter()
        for d in self._docs:
            df.update(d.keys())
        N = len(self._docs)
        self._idf = {t: math.log(1 + (N - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.by_id = {p.pid: p for p in self.passages}
        self._sec_cache: dict[str, tuple[str, dict[str, int]]] = {}

    # ---------- ranked search ----------
    def search(self, query: str, k: int = 6, sources: list[str] | None = None) -> list[tuple[Passage, float]]:
        q = tokenize(query)
        if not q:
            return []
        k1, b = 1.5, 0.75
        scored = []
        for i, d in enumerate(self._docs):
            p = self.passages[i]
            if sources and p.file not in sources:
                continue
            s = 0.0
            for t in q:
                f = d.get(t)
                if f:
                    s += self._idf.get(t, 0) * f * (k1 + 1) / (f + k1 * (1 - b + b * self._len[i] / self._avg))
            if s <= 0:
                continue
            # bonus when two query words appear side by side (phrases like "carpet area")
            for a, c in zip(q, q[1:]):
                if f"{a} {c}" in self._low[i]:
                    s += 0.5 * (self._idf.get(a, 0) + self._idf.get(c, 0))
            # penalty for table-like passages made mostly of dashes and numbers
            if self._alpha[i] < 0.45:
                s *= 0.6
            scored.append((p, s))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    # ---------- exact lookups (more reliable than search for citations) ----------
    def _sections(self, fname: str) -> tuple[str, dict[str, int]]:
        if fname not in self._sec_cache:
            text = (self.dir / fname).read_text(encoding="utf-8")
            heads: dict[str, int] = {}
            for m in _HEADING.finditer(text):
                heads.setdefault(m.group(1), m.start())  # first full heading in the body
            self._sec_cache[fname] = (text, heads)
        return self._sec_cache[fname]

    def lookup(self, kind: str, number: str, clause: str = "") -> dict:
        """Exact text of Act section N (kind='act') or Karnataka Rules rule N (kind='rules')."""
        fname = "RERA_Act_2016_KRERA_copy.txt" if kind == "act" else "Karnataka_RERA_Rules_2017_EN.txt"
        label, authority = SOURCES[fname]
        number = re.sub(r"[^0-9A-Za-z]", "", str(number)).upper()
        word = "Section" if kind == "act" else "Rule"
        text, heads = self._sections(fname)
        if number not in heads:
            return {"found": False, "source": label,
                    "message": f"{word} {number} was not found in {label}. Do not cite it."}
        start = heads[number]
        later = sorted(v for v in heads.values() if v > start)
        end = later[0] if later else min(len(text), start + 6000)
        b0, b1 = start, end
        if clause:
            c = clause.strip("() ").lower()
            m = re.search(rf"^[ \t]*\({re.escape(c)}\)[ \t]", text[start:end], re.M)
            if m:
                b0 = start + m.start()
                after = start + m.end()
                nxt = re.search(r"^[ \t]*\([a-z]{1,4}\)[ \t]+[“\"]", text[after:end], re.M)
                b1 = after + nxt.start() if nxt else min(end, b0 + 2500)
            else:
                clause = ""
        pages = _PAGE.findall(text[:b0])
        page = int(pages[-1]) if pages else None
        body = re.sub(r"\[Page \d+\]\s*", "", text[b0:b1])
        body = re.sub(r"[ \t]+", " ", body).strip()
        if not body:
            return {"found": False, "source": label, "message": f"Could not read {word} {number}. Use search instead."}
        if len(body) > 5000:
            body = body[:5000] + " ... [truncated]"
        ref = ("Act s." if kind == "act" else "Karnataka Rules r.") + number + (f"({clause.strip('() ')})" if clause else "")
        return {"found": True, "source": label, "authority": authority, "reference": ref,
                "page": page, "text": body}

    def stats(self) -> dict:
        per = Counter(p.source for p in self.passages)
        return {"passages": len(self.passages), "per_source": dict(per)}
