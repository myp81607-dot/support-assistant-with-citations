"""Small, explainable lexical retrieval. Scores are ranks, never confidence."""
import math
import re
from collections import Counter

STOP = set("a an the is are was be been to of for in on at and or my your our i we you can could how what when where do does should would please harbor harbordesk it with from me get there this that after before about have has as all".split())
STOP.update({"many", "much", "fix", "being", "if", "let", "gets"})
ALIASES = {
    "rotating": "rotate", "rotation": "rotate", "exporting": "export", "exported": "export",
    "closing": "close", "closed": "close", "retained": "retention", "retains": "retention",
    "limiting": "limit", "limited": "limit", "inviting": "invite", "invitation": "invite",
    "colleague": "member", "coworker": "member", "mailbox": "email",
    "callback": "webhook", "handling": "processing",
}
INJECTION = re.compile(r"ignore.{0,60}(instruction|previous|system)|reveal.{0,40}(secret|prompt|key)|system\s*prompt|environment\s*variable|execute\s+(?:a\s+)?(?:shell|command)|<script", re.I | re.S)


def suspicious(text):
    return bool(INJECTION.search(text))


def tokens(text):
    # A deliberately small domain vocabulary, shared by queries and documents.
    # Context matters: "last" is expiration wording for a download link, but is
    # not discarded from an unrelated request. Product formats (JSON/CSV),
    # amounts, guarantees, and unknown requested features remain visible.
    normalized = text.lower()
    if re.search(r"\b(?:export\w*|download)\b", normalized) and re.search(r"\blinks?\b", normalized):
        normalized = re.sub(r"\b(?:how long|lasts?|valid|validity|lifetime|expiry|expiration)\b", "expire", normalized)
    normalized = re.sub(r"\bthrottl(?:e|ed|es|ing)\b", "rate limit", normalized)
    normalized = re.sub(r"\baccess credentials?\b", "api key", normalized)
    if re.search(r"\bapi[- ]keys?\b", normalized):
        normalized = re.sub(r"\breplac(?:e|ing|ement)\b", "rotate", normalized)
        # These phrases ask about the order of key replacement. The source's
        # verify-new-before-revoke-old procedure is relevant evidence; it is not
        # a service uptime guarantee. Explicit "guaranteed" remains unsupported.
        normalized = re.sub(r"\bwithout (?:interrupting|interruption|downtime)\b", "", normalized)
    if re.search(r"\b(?:team|colleague|coworker|members?)\b", normalized):
        normalized = re.sub(r"\bjoin\b", "invite", normalized)
    if re.search(r"\b(?:billing|invoices?)\b", normalized):
        normalized = re.sub(r"\bmove\b", "change", normalized)
        normalized = re.sub(r"\bmessages?\b", "email", normalized)
        normalized = re.sub(r"\bdifferent\b", "new", normalized)
    if re.search(r"\b(?:callbacks?|webhooks?|events?)\b", normalized):
        normalized = re.sub(r"\bsame\b|\btwice\b", "duplicate", normalized)
    parts = re.findall(r"[a-z0-9]+", normalized)
    result = set()
    for term in parts:
        if term in STOP:
            continue
        singular = term[:-1] if len(term) > 4 and term.endswith("s") else term
        result.add(ALIASES.get(term, ALIASES.get(singular, singular)))
    return result


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
