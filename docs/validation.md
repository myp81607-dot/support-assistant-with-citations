# Validation

Updated 2026-09-19. Windows, Python 3.14.3, FastAPI 0.135.1. All data is synthetic. Local retrieval and application workflows have been exercised; live DeepSeek requests are **0**. Generated-answer quality, semantic citation support, live-model latency, and inference cost have not been measured. Paid verification is awaiting authorization.

## Local checks

**73 tests passed across focused runs:** 28 workflow and model-transport checks, 41 retrieval checks, and 4 added conflict regressions. These were separate runs, not one reported full-suite run. To reproduce the current suite:

```sh
python -m pytest -q
python -m evaluation.run
```

The workflow checks cover changed questions and sources, document versions, stale edits, persistent handoffs and notes, custom document imports, and known injection patterns. Model checks use `httpx.MockTransport`: paraphrased drafts, valid and invalid citations, malformed or incomplete output, timeout, rate limit, insufficient account funds, and the local request allowance. No fixture is a real model response.

Human review is required before the reply endpoint permits copying. Tests cover pending, approved, rejected, and stale drafts, including approvals retained after restart. A fixture with an invented price and uptime guarantee but a real quotation remains pending and can be rejected: the quote check alone does not authorize the answer.

An independent review reproduced an old draft remaining approvable after a new, conflicting policy was added. Approval and copying now check current relevant tagged conflicts as well as cited document versions. Four regressions cover adding a conflicting document or changing an uncited document, both before and after approval. The independent reviewer rechecked the two new-document paths; both return HTTP 409.

## Retrieval results

The original 29 questions retain their expected labels. [Per-case results](evaluation-results.json) include excerpts, source IDs, checks, unknown terms, and timings from fresh temporary databases with the model disabled.

| Measurement | Result | What it establishes |
| --- | --- | --- |
| Complete case checks | 29 / 29 | Expected status, required source/text, and version checks |
| Questions with required sources | 23 / 23 | Every labeled required source was retrieved |
| Required document IDs | 27 / 27 | Recall of labeled IDs, counted separately per question |
| Exact source excerpts | 48 / 48 | Stored document, version, paragraph ID, and text match |
| Missing-information cases | 6 / 6 | Absent facts route to review |
| Tagged-policy conflicts | 2 / 2 | Disagreement is shown without selecting a policy answer |
| Known injection cases | 3 / 3 | The tested override requests are withheld |
| Local request time | Median 5.51 ms; maximum 7.29 ms | One TestClient run including persistence; not a hosted SLA |

The six earlier misses remain identifiable: N04 (export-link expiry), P01 (key replacement), P02 (team invitation), P03 (billing email), P04 (throttling), and P05 (duplicate callbacks). Small phrase aliases fixed their retrieval/gating behavior without changing labels. The unknown-term guard still withholds unsupported JSON-export, refund, and explicit uptime-guarantee requests. The retrieval suite and evaluator also passed with `SUPPORT_DOCUMENTS` set to the custom example: fixed regression runs explicitly use the demo corpus, independently of that setting.

The [ten paired questions](../evaluation/paired_questions.json), fixed before this retrieval revision, improved from 5/10 to 10/10. They check supported and unsupported wording together. They are now seen regression cases, not a blind benchmark. The original labels were authored by another coding agent from the synthetic documents; neither set represents customer traffic or human-expert judgments.

Matching a quotation establishes source existence and attribution. It does not prove that the source supports the answer, that the policy is true, or that the reply is complete. Retrieval scores are ranks, not confidence or answer accuracy.

## Model validation boundary

The DeepSeek-compatible adapter requests structured claims with exact supporting quotations. Automatic checks validate the response structure, source IDs, and quoted text. An operator must separately compare each claim with its evidence and approve the draft before copying a customer reply. The application sends no reply and exposes no business-action tools to the model.

The [fixed live question set](../evaluation/answer_questions.json) has 14 cases: 10 intended model requests and 4 questions blocked before a call. The opt-in harness is prepared but has **not been executed**:

```sh
python -m evaluation.run_answers --run
```

That command makes billable requests and requires configured credentials and spending authorization. It caps the run at 10 calls; the adapter bounds input size and output tokens and explicitly disables DeepSeek thinking. A future run must report answer correctness, semantic citation support, incorrect release, unnecessary handoff, latency, and actual cost separately. Status matches and valid quote IDs cannot substitute for reviewing the answers.

## Browser walkthrough

[Watch the actual application recording](demo.webm). The roughly 35-second video uses screenshots captured during real browser operations, with waiting intervals trimmed. It shows an export-link-expiry question, a refund handoff with notes, editing the API limit from 100 to 200 requests/minute as v2, and a new question retrieving the updated source. It contains no generated-model-answer footage.

Six updated captures show the running app:

- [Retrieved evidence](screenshots/01-evidence.jpg)
- [30/90-day policy conflict](screenshots/02-conflict.jpg), captured separately from the video
- [Saved handoff](screenshots/03-handoff.jpg)
- [Document version editor](screenshots/04-version-editor.jpg)
- [Updated source evidence](screenshots/05-updated-evidence.jpg)
- [Missing refund information](screenshots/06-insufficient-evidence.jpg)

The evidence-mode browser workflow completed, including recovery of a stale tab. No application console errors were observed. Captures use a separate local demo database; they are not generated mockups or customer records.

A separate browser check used the visibly named `transport-fixture-only` model with `httpx.MockTransport`: pending draft, opening the cited quote, required checkbox and note, approval, and copying the exact reply with its source to the clipboard all passed without console errors. This was a simulated response testing the transport/UI integration, not a real model; no fixture footage or screenshots are published.

These checks support a local demonstration and a starting point for customer-specific testing. They do not establish production readiness or automatic answer accuracy.
