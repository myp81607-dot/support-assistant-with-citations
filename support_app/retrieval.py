"""Small, explainable lexical retrieval. Scores are ranks, never confidence."""
import math
import re
from collections import Counter

STOP = set("a an the is are was be been to of for in on at and or my your our i we you can could how what when where do does should would please harbor harbordesk it with from me get there this that after before about have has as all".split())
STOP.update({"many", "much", "fix"})  # Question phrasing, not requested facts.
ALIASES = {"rotating": "rotate", "rotation": "rotate", "exporting": "export", "closing": "close", "closed": "close", "retained": "retention", "retains": "retention", "limit": "limit", "inviting": "invite", "invitation": "invite"}
INJECTION = re.compile(r"ignore.{0,60}(instruction|previous|system)|reveal.{0,40}(secret|prompt|key)|system\s*prompt|environment\s*variable|execute\s+(?:a\s+)?(?:shell|command)|<script", re.I | re.S)


def suspicious(text):
    return bool(INJECTION.search(text))


def tokens(text):
    parts = re.findall(r"[a-z0-9]+", text.lower())
    return {ALIASES.get(t, t[:-1] if len(t) > 4 and t.endswith("s") else t)
            for t in parts if t not in STOP}


def retrieve(question, documents, limit=4):
    query = tokens(question)
    chunks = []
    blocked = []
    for d in documents:
        if suspicious(d["text"]):
            blocked.append(d["id"])
            continue
        for i, paragraph in enumerate(d["text"].split("\n\n"), 1):
            if paragraph.strip():
                chunks.append({"source_id": f'{d["id"]}@v{d["version"]}#p{i}',
                               "doc_id": d["id"], "title": d["title"], "version": d["version"],
                               "text": paragraph.strip(), "terms": tokens(d["title"] + " " + paragraph)})
    frequency = Counter(t for c in chunks for t in c["terms"])
    weights = {t: math.log(1 + (len(chunks) + 1) / (frequency[t] + 1)) for t in query}
    total = sum(weights.values()) or 1
    ranked = []
    for c in chunks:
        overlap = query & c["terms"]
        score = sum(weights[t] for t in overlap)
        if score:
            ranked.append({**c, "score": round(score, 3), "coverage": round(score / total, 3)})
    ranked.sort(key=lambda c: (-c["score"], c["source_id"]))
    # Do not pad context with weak incidental matches.
    selected = [c for c in ranked[:limit] if c["score"] >= ranked[0]["score"] * .4]
    covered = set().union(*(c["terms"] for c in selected)) if selected else set()
    coverage = sum(weights[t] for t in query & covered) / total
    for c in selected:
        c.pop("terms")
    relevant_ids = {c["doc_id"] for c in selected}
    # A shared number (e.g. a 30-day refund question) is not a policy topic.
    policy_query = {t for t in query if not t.isdigit()} - {
        "support", "guide", "policy", "appendix", "day", "days", "hour", "minute", "month", "year"}
    keys = {d["fact_key"] for d in documents if d["id"] in relevant_ids and d["fact_key"]
            and policy_query & tokens(d["title"] + " " + d["text"])}
    conflicts = []
    for key in sorted(keys):
        siblings = [d for d in documents if d["fact_key"] == key]
        values = sorted({d["fact_value"].strip().lower() for d in siblings})
        if len(values) > 1:
            conflicts.append({"key": key, "values": values})
            # Include both sides even if one fell below the retrieval cutoff.
            for d in siblings:
                if d["id"] not in relevant_ids and not suspicious(d["text"]):
                    selected.append({"source_id": f'{d["id"]}@v{d["version"]}#p1', "doc_id": d["id"],
                                     "title": d["title"], "version": d["version"], "text": d["text"].split("\n\n")[0],
                                     "score": 0, "coverage": 0})
    return selected, coverage, conflicts, blocked
