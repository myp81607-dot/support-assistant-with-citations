"""Fixed retrieval labels; no network, model requests, or answer-accuracy claim."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from support_app.main import create_app


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = json.loads((ROOT / "evaluation/questions.json").read_text(encoding="utf-8"))["cases"]
PAIRED = json.loads((ROOT / "evaluation/paired_questions.json").read_text(encoding="utf-8"))["cases"]
OLD_FAILURES = {"N04", "P01", "P02", "P03", "P04", "P05"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORT_MODEL", "")
    monkeypatch.delenv("SUPPORT_DOCUMENTS", raising=False)
    with TestClient(create_app(tmp_path / "support.db")) as client:
        yield client


@pytest.mark.parametrize("case", ORIGINAL + PAIRED, ids=lambda case: case["id"])
def test_fixed_retrieval_expectations(client, case):
    if "update" in case:
        update = dict(case["update"])
        doc_id = update.pop("doc_id")
        assert client.put(f"/api/documents/{doc_id}", json=update).status_code == 200
    response = client.post("/api/ask", json={"question": case["question"]})
    assert response.status_code == 200
    result = response.json()
    sources = result["retrieval"]
    assert result["status"] == case["expected_status"], result
    assert set(case["expected_docs"]) <= {source["doc_id"] for source in sources}
    text = "\n".join(source["text"] for source in sources).lower()
    assert all(fragment.lower() in text for fragment in case["expected_text"])
    for doc_id, version in case.get("expected_versions", {}).items():
        assert any(source["doc_id"] == doc_id and source["version"] == version for source in sources)
    assert result["generated_answer"] is None and result["claims"] == []
    if case["id"] in OLD_FAILURES:
        assert result["unknown_terms"] == []
    if case["id"] in {"U02", "PAIR02"}:
        assert "json" in result["unknown_terms"]
    if case["id"] in {"PAIR06", "PAIR07"}:
        assert "refund" in result["unknown_terms"] and result["conflicts"] == []


def test_key_procedure_does_not_remove_an_explicit_guarantee(client):
    result = client.post("/api/ask", json={
        "question": "Is API key replacement guaranteed without downtime?",
    }).json()
    assert result["status"] == "needs_review"
    assert "guaranteed" in result["unknown_terms"]
    assert any(source["doc_id"] == "api-keys" for source in result["retrieval"])


def test_unknown_fact_stays_unknown_when_question_contains_supported_synonym(client):
    result = client.post("/api/ask", json={
        "question": "Can I invite a coworker with SCIM provisioning?",
    }).json()
    assert result["status"] == "needs_review"
    assert {"scim", "provisioning"} <= set(result["unknown_terms"])
