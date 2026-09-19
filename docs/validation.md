# Validation: measured behavior and remaining failures

Run date: 2026-09-19. Windows, Python 3.14.3, FastAPI 0.135.1. Local synthetic corpus only; no paid or real model request. Results describe this small demo, not a customer deployment.

## Functional checks

`python -m pytest -q` → **15 passed**. Two dependency deprecation warnings were emitted by Starlette/TestClient; there were no failures. `node --check support_app/static/app.js` also passed.

The functional suite covers changed input changing retrieved evidence, version updates changing the source and fact, stale edit rejection, preservation of old ticket evidence, repeat handoff without duplicate tickets, ticket notes/status across restart, known query/document injection patterns, and local-model HTTP contract success/rejection/timeout/call allowance. Model transport uses `httpx.MockTransport`; it does not exercise a real model.

## Independent question diagnostics

`python -m evaluation.run` → **exit 1**, deliberately retaining six failures. [Raw per-case results](evaluation-results.json) include questions, fixed expected labels, returned excerpts, source IDs, checks, unrecognized terms, and timings.

| Measurement | Observed | Meaning |
| --- | --- | --- |
| All diagnostic checks | 23 / 29 | Expected status plus required excerpts/source IDs/version checks |
| Required-source questions | 22 / 23 | Every required source present; excludes cases with no source label |
| Required document IDs retrieved | 26 / 27 | Recall of labeled IDs, counting each question separately |
| Exact source quotations | 47 / 47 | Text, document ID, revision, and paragraph match the stored source |
| Missing-information handling | 6 / 6 | Explicit review state for the labeled absent facts |
| Policy conflict handling | 2 / 2 | Both tagged policies shown, no answer generated |
| Known injection cases | 3 / 3 | Instruction override state; no action or model call |
| Multi-source questions | 2 / 2 | Both required source documents retrieved |
| Document update question | 1 / 1 | New value and v2 used after update |
| Initially held-out subset | 5 / 7 | Labels unchanged; inspected during fixes, no longer a blind estimate |
| Local request latency | median 5.83 ms; max 8.02 ms | One TestClient run including SQLite persistence, not a hosted SLA |
| Generated-answer correctness | Not measured | Evidence mode emits no model answers |
| Actual model requests / API spend | 0 / no API spend | Local retrieval only; hardware and development costs not measured |

Labels were independently authored by another coding agent after the initial implementation, based on the synthetic documents. They are not customer traffic, human expert judgments, or a statistically representative benchmark. Quote equality establishes attribution integrity only; it cannot establish relevance, truth of the document, completeness, or answer accuracy.

### Retained failures

- **N04:** “How long do export download links last?” finds the correct 24-hour passage but conservatively returns `needs_review` because the wording is not fully covered.
- **P01–P03, P05:** Credential replacement, inviting a colleague, moving billing messages, and handling duplicate callbacks find the expected sources but still require review. Their paraphrases do not pass the lexical gate.
- **P04:** “What should my integration do when it gets throttled?” misses the rate-limit source and requires review. The corpus does not use “throttled.”

These limitations are visible in the diagnostic file and were not repaired by changing expected labels or claiming that any copied text is a correct answer. Semantic retrieval could be evaluated if paraphrase support becomes a real requirement; it is not included here.

### Observed defect and correction

The first independent diagnostic run exposed “Can I export tickets as a JSON archive?” receiving `evidence_found` from a CSV-only guide. The fix conservatively routes unrecognized corpus terms to review; it does not invent support for JSON. An independent reviewer also reproduced a missed tagged conflict with “After workspace closure, how many days before deletion?” The conflict trigger now considers meaningful title and body terms, excluding incidental numbers and time units. A regression confirms the 30/90-day disagreement while a 30-day refund question remains a missing-information handoff. The reviewer reran the affected wording and reported the defect resolved.

## Browser walkthrough and real captures

All captures came from the running FastAPI app, using a separate browser tab and synthetic local SQLite database. They are screenshots of actual actions, not generated success mockups.

1. Ask about API-key rotation; inspect the original instructions and versioned sources: [evidence](screenshots/01-evidence.jpg).
2. Ask whether retention is 30 or 90 days; see the disagreement and both sources: [conflict](screenshots/02-conflict.jpg).
3. Create a local ticket, set In progress, save a policy-investigation note, reopen it: [handoff](screenshots/03-handoff.jpg).
4. Change the API limit from 100 to 200 requests/minute in the editor, save v2: [editor](screenshots/04-version-editor.jpg).
5. Ask the API-limit question again and see 200 with `api-limits@v2#p1`: [updated evidence](screenshots/05-updated-evidence.jpg).
6. Ask for a refund after 30 days; see the explicit review state: [missing information](screenshots/06-insufficient-evidence.jpg).

The browser reported no console errors during the walkthrough. Functional tests also verify resolution notes and persistence across application restart. A continuous demo video was not recorded; the reproducible walkthrough and real screenshots are supplied instead.

## Scope of independent review

A separate agent examined the actual backend, tests, corpus, and bilingual documentation, ran the functional suite, checked the unchanged learning baseline, and checked candidate text for local paths or credentials. It found the conflict-trigger defect above; a targeted recheck passed after correction. Screenshot capture and this final metric summary were completed by the implementation agent.
