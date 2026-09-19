"""Opt-in live model run. Never called by pytest or the offline evaluator."""
import argparse
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from support_app.main import create_app
from support_app.model import ChatCompletions


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Make up to 10 billable requests using configured credentials.")
    args = parser.parse_args()
    if not args.run:
        parser.error("Live calls are opt-in. Read the fixed questions and obtain API spending authorization before --run.")
    model = ChatCompletions(os.environ.get("SUPPORT_MODEL", "deepseek-flash"), os.environ.get("SUPPORT_API_KEY", ""),
                            os.environ.get("SUPPORT_API_BASE", "https://api.deepseek.com"), max_calls=10)
    questions = json.loads(Path(__file__).with_name("answer_questions.json").read_text(encoding="utf-8"))
    results = []
    with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"SUPPORT_DOCUMENTS": ""}):
        for case in questions["cases"]:
            with TestClient(create_app(Path(folder) / (case["id"] + ".db"), model=model)) as client:
                if case.get("update"):
                    update = dict(case["update"])
                    doc_id = update.pop("doc_id")
                    client.put("/api/documents/" + doc_id, json=update).raise_for_status()
                before = model.calls
                start = time.perf_counter()
                response = client.post("/api/ask", json={"question": case["question"]})
                response.raise_for_status()
                result = response.json()
                result.update(case_id=case["id"], expected_status=case["expected_status"],
                              status_matches=result["status"] == case["expected_status"],
                              model_request_made=model.calls > before,
                              request_ms=round((time.perf_counter() - start) * 1000, 2))
                results.append(result)
                print(case["id"], result["status"], result["request_ms"], flush=True)
    output = Path(__file__).resolve().parents[1] / "docs" / "answer-results.json"
    output.write_text(json.dumps({"run_at_utc": datetime.now(timezone.utc).isoformat(), "model": model.model,
                                 "requests": model.calls, "cases": results,
                                 "claim_support_review": "Pending separate review against quoted source text; status or citation existence is not answer correctness."}, indent=2) + "\n", encoding="utf-8")
    print("Saved docs/answer-results.json; semantic correctness is not automatically scored.")


if __name__ == "__main__":
    run()
