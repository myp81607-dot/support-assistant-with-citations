"""Run `python -m evaluation.run`; use only seeded SQLite and no model service."""
import json
import os
import statistics
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from support_app.main import create_app


ROOT = Path(__file__).resolve().parents[1]


def run():
    dataset = json.loads((Path(__file__).with_name("questions.json")).read_text(encoding="utf-8"))
    results = []
    with tempfile.TemporaryDirectory(prefix="harbordesk-evaluation-") as temporary:
        for case in dataset["cases"]:
            with patch.dict(os.environ, {"SUPPORT_MODEL": ""}):
                app = create_app(Path(temporary) / f'{case["id"]}.db')
            with TestClient(app) as client:
                if "update" in case:
                    update = dict(case["update"])
                    doc_id = update.pop("doc_id")
                    response = client.put(f"/api/documents/{doc_id}", json=update)
                    response.raise_for_status()
                start = time.perf_counter()
                response = client.post("/api/ask", json={"question": case["question"]})
                response.raise_for_status()
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                observed = response.json()
                documents = {s["doc_id"] for s in observed["retrieval"]}
                text = "\n".join(s["text"] for s in observed["retrieval"]).lower()
                original_paragraphs = {
                    f'{doc["id"]}@v{doc["version"]}#p{index}': (doc["id"], doc["version"], paragraph.strip())
                    for doc in app.state.store.documents()
                    for index, paragraph in enumerate(doc["text"].split("\n\n"), 1)
                    if paragraph.strip()
                }
                citation_checks = [{
                    "source_id": source["source_id"],
                    "matches_current_document": original_paragraphs.get(source["source_id"]) ==
                        (source["doc_id"], source["version"], source["text"]),
                } for source in observed["retrieval"]]
                checks = {
                    "status_matches": observed["status"] == case["expected_status"],
                    "required_documents_present": set(case["expected_docs"]) <= documents,
                    "required_fragments_present": all(t.lower() in text for t in case["expected_text"]),
                    "required_versions_present": all(any(s["doc_id"] == doc_id and s["version"] == version
                        for s in observed["retrieval"]) for doc_id, version in case.get("expected_versions", {}).items()),
                    "no_generated_answer": observed["generated_answer"] is None and not observed["claims"],
                    "citations_match_current_documents": all(c["matches_current_document"] for c in citation_checks),
                }
                results.append({
                    "id": case["id"], "split": case["split"], "category": case["category"],
                    "question": case["question"], "expected_status": case["expected_status"],
                    "observed_status": observed["status"], "expected_docs": case["expected_docs"],
                    "expected_text": case["expected_text"],
                    "observed_sources": [{k: source[k] for k in ("source_id", "doc_id", "version", "text")}
                                         for source in observed["retrieval"]],
                    "coverage": observed["coverage"], "unknown_terms": observed.get("unknown_terms", []),
                    "latency_ms": latency_ms, "citation_checks": citation_checks,
                    "checks": checks, "passed": all(checks.values()),
                })
    def counts(group):
        labeled = [r for r in group if r["expected_docs"]]
        return {"cases": len(group), "all_checks_passed": sum(r["passed"] for r in group),
                "status_matches": sum(r["checks"]["status_matches"] for r in group),
                "required_document_checks_passed": sum(r["checks"]["required_documents_present"] for r in group),
                "labeled_retrieval_cases": len(labeled),
                "required_document_hits": sum(r["checks"]["required_documents_present"] for r in labeled),
                "expected_gold_document_ids": sum(len(set(r["expected_docs"])) for r in labeled),
                "matched_gold_document_ids": sum(len(set(r["expected_docs"]) &
                    {s["doc_id"] for s in r["observed_sources"]}) for r in labeled),
                "checked_quotes": sum(len(r["citation_checks"]) for r in group),
                "quotes_matching_current_documents": sum(c["matches_current_document"]
                    for r in group for c in r["citation_checks"])}
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "label_provenance": dataset["description"], "status_definition": dataset["status_definition"],
        "execution": "Fresh temporary SQLite database per case; FastAPI TestClient; model disabled. No network or real model calls.",
        "metric_definitions": {
            "required_document_checks_passed": "Legacy count over all cases, including vacuous passes where expected_docs is empty; not retrieval accuracy.",
            "required_document_hits": "Cases with nonempty expected_docs where every required document is retrieved; denominator is labeled_retrieval_cases.",
            "expected_gold_document_ids": "Sum of distinct expected document IDs within each labeled case; the same document in different cases is counted separately.",
            "matched_gold_document_ids": "Expected document IDs found in each case, summed across labeled cases; measures source recall only, not relevance of extra sources.",
            "checked_quotes": "Number of returned source excerpts checked against current stored document ID, version, paragraph ID, and exact paragraph text.",
            "quotes_matching_current_documents": "Returned excerpts whose cited ID/version and exact text match the original stored paragraph; does not assess answer usefulness.",
        },
        "generated_answer_accuracy": "N/A: model disabled; citation equality is not generated answer accuracy.",
        "summary": {**counts(results), "failed_case_ids": [r["id"] for r in results if not r["passed"]],
                    "observed_status_counts": dict(Counter(r["observed_status"] for r in results)),
                    "median_request_latency_ms": round(statistics.median(r["latency_ms"] for r in results), 2),
                    "max_request_latency_ms": max(r["latency_ms"] for r in results)},
        "by_category": {category: counts([r for r in results if r["category"] == category])
                        for category in sorted({r["category"] for r in results})},
        "by_split": {split: counts([r for r in results if r["split"] == split])
                     for split in sorted({r["split"] for r in results})},
        "limitations": ["Agent-authored synthetic labels are not a human evaluation or a production benchmark.",
                        "A matching status and excerpt do not establish answer correctness or exhaustive retrieval.",
                        "Expected empty document lists impose no source constraint; absent facts are assessed by status.",
                        "Latency is one local run, includes TestClient and persistence overhead, and is not a service SLA.",
                        "Injection cases cover known patterns only; they do not certify adversarial robustness."],
        "cases": results,
    }
    destination = ROOT / "docs" / "evaluation-results.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("Saved docs/evaluation-results.json. Failing labels are reported unchanged.")
    return int(any(not r["passed"] for r in results))


if __name__ == "__main__":
    sys.exit(run())
