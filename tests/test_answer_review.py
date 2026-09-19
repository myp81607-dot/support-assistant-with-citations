"""Draft review and customer-data workflows; model responses are transport fixtures."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from support_app.main import create_app
from support_app.model import ChatCompletions


QUESTION = "How do I rotate an API key?"
PARAPHRASE = "Create a replacement key in Settings > API keys, then test it before revoking the old key."


@pytest.fixture(autouse=True)
def disable_environment_model_and_documents(monkeypatch):
    monkeypatch.setenv("SUPPORT_MODEL", "")
    monkeypatch.delenv("SUPPORT_DOCUMENTS", raising=False)


def response_for(request, text=PARAPHRASE, finish_reason="stop"):
    payload = json.loads(request.content)
    sources = json.loads(payload["messages"][1]["content"])["sources"]
    source = next(s for s in sources if s["doc_id"] == "api-keys")
    quote = source["text"].split(" Only workspace")[0]
    content = {"answerable": True, "claims": [{"text": text, "citations": [
        {"source_id": source["source_id"], "quote": quote}
    ]}]}
    return httpx.Response(200, json={"model": "transport-test-only", "choices": [
        {"finish_reason": finish_reason, "message": {"content": json.dumps(content)}}
    ], "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}})


def model_for(handler=response_for):
    return ChatCompletions("transport-test-only", "synthetic-key", transport=httpx.MockTransport(handler))


def ask(client):
    response = client.post("/api/ask", json={"question": QUESTION})
    assert response.status_code == 200
    return response.json()


def approve(client, query_id):
    return client.post(f"/api/queries/{query_id}/review", json={
        "decision": "approved", "support_checked": True,
        "note": "Checked the replacement and verification steps against the quoted source."
    })


def update_cited_document(client):
    return client.put("/api/documents/api-keys", json={
        "text": "To rotate an API key, open Settings > Security > API keys. Verify a request with the new key before revoking the old key.",
        "expected_version": 1,
    })


def test_paraphrased_draft_is_pending_until_claim_support_review(tmp_path):
    with TestClient(create_app(tmp_path / "draft.db", model=model_for())) as client:
        draft = ask(client)
        assert draft["status"] == "draft_ready"
        assert draft["claims"][0]["text"] == PARAPHRASE
        cite = draft["claims"][0]["citations"][0]
        source = next(s for s in draft["retrieval"] if s["source_id"] == cite["source_id"])
        assert cite["quote"] in source["text"] and PARAPHRASE not in source["text"]
        assert draft["citation_validation"] == "passed"
        assert draft["support_validation"] == "human_review_required"
        assert draft["review"]["status"] == "pending"
        assert draft["usage"]["total_tokens"] == 130
        assert client.get(f'/api/queries/{draft["id"]}/reply').status_code == 409


def test_real_quote_does_not_prove_semantic_support_or_enable_copy(tmp_path):
    # The citation is real, but it says nothing about a price or guaranteed uptime.
    invented = "The replacement costs $0 and guarantees that service never stops."
    model = model_for(lambda request: response_for(request, text=invented))
    with TestClient(create_app(tmp_path / "unsupported.db", model=model)) as client:
        draft = ask(client)
        assert draft["status"] == "draft_ready"
        assert draft["citation_validation"] == "passed"
        assert draft["support_validation"] == "human_review_required"
        assert draft["review"]["status"] == "pending"
        assert client.get(f'/api/queries/{draft["id"]}/reply').status_code == 409
        rejected = client.post(f'/api/queries/{draft["id"]}/review', json={
            "decision": "rejected", "note": "The quote does not support the price or uptime guarantee."
        })
        assert rejected.status_code == 200
        assert rejected.json()["review"]["status"] == "rejected"
        assert client.get(f'/api/queries/{draft["id"]}/reply').status_code == 409
        assert approve(client, draft["id"]).status_code == 409


def test_approval_requires_support_checkbox_and_meaningful_note(tmp_path):
    with TestClient(create_app(tmp_path / "review.db", model=model_for())) as client:
        draft = ask(client)
        route = f'/api/queries/{draft["id"]}/review'
        no_check = client.post(route, json={"decision": "approved", "note": "Reviewed the answer."})
        assert no_check.status_code == 409
        for note in (None, "   "):
            body = {"decision": "approved", "support_checked": True}
            if note is not None:
                body["note"] = note
            assert client.post(route, json=body).status_code == 422
        assert client.get(f'/api/queries/{draft["id"]}/reply').status_code == 409
        approved = approve(client, draft["id"])
        assert approved.status_code == 200
        assert approved.json()["review"]["support_checked"] is True
        reply = client.get(f'/api/queries/{draft["id"]}/reply')
        assert reply.status_code == 200 and reply.json()["reply"] == draft["generated_answer"]


@pytest.mark.parametrize("update_after_approval", [False, True])
def test_cited_document_update_invalidates_draft_or_approved_reply(tmp_path, update_after_approval):
    with TestClient(create_app(tmp_path / "stale.db", model=model_for())) as client:
        draft = ask(client)
        if update_after_approval:
            assert approve(client, draft["id"]).status_code == 200
        assert update_cited_document(client).status_code == 200
        if not update_after_approval:
            stale_approval = approve(client, draft["id"])
            assert stale_approval.status_code == 409
            assert "changed" in stale_approval.json()["detail"]
        assert client.get(f'/api/queries/{draft["id"]}/reply').status_code == 409


@pytest.mark.parametrize("change", ["new_document", "uncited_document_update"])
@pytest.mark.parametrize("change_after_approval", [False, True])
def test_new_policy_conflict_blocks_old_draft_and_reply(tmp_path, change, change_after_approval):
    def respond(request):
        sources = json.loads(json.loads(request.content)["messages"][1]["content"])["sources"]
        source = next(s for s in sources if s["doc_id"] == "api-limits")
        content = {"answerable": True, "claims": [{
            "text": "The limit is 100 requests per minute per workspace.",
            "citations": [{"source_id": source["source_id"], "quote": source["text"]}]
        }]}
        return httpx.Response(200, json={"choices": [{
            "finish_reason": "stop", "message": {"content": json.dumps(content)}
        }]})

    with TestClient(create_app(tmp_path / "new-conflict.db", model=model_for(respond))) as client:
        question = {"question": "What is the API rate limit?"}
        draft = client.post("/api/ask", json=question).json()
        assert draft["status"] == "draft_ready"
        assert draft["claims"][0]["citations"][0]["source_id"] == "api-limits@v1#p1"
        route = f'/api/queries/{draft["id"]}/review'
        review = {"decision": "approved", "support_checked": True, "note": "Checked the rate and workspace scope against the source."}
        if change_after_approval:
            assert client.post(route, json=review).status_code == 200
            assert client.get(f'/api/queries/{draft["id"]}/reply').status_code == 200
        conflicting = {"text": "The API rate limit is 200 requests per minute per workspace.",
                       "fact_key": "api_rate_limit", "fact_value": "200 requests per minute"}
        if change == "new_document":
            changed = client.post("/api/documents", json={**conflicting, "id": "new-limit", "title": "Updated API limits"})
        else:
            changed = client.put("/api/documents/api-errors", json={**conflicting, "expected_version": 1})
        assert changed.status_code == 200
        assert client.get("/api/documents/api-limits/history").json()[0]["version"] == 1
        assert client.post("/api/ask", json=question).json()["status"] == "conflict"
        if change_after_approval:
            blocked = client.get(f'/api/queries/{draft["id"]}/reply')
        else:
            blocked = client.post(route, json=review)
        assert blocked.status_code == 409
        assert "conflicting policy" in blocked.json()["detail"]


def test_approval_and_reply_persist_after_restart(tmp_path):
    path = tmp_path / "persisted-review.db"
    with TestClient(create_app(path, model=model_for())) as client:
        draft = ask(client)
        approved = approve(client, draft["id"])
        assert approved.status_code == 200
    with TestClient(create_app(path)) as reopened:
        reply = reopened.get(f'/api/queries/{draft["id"]}/reply')
        assert reply.status_code == 200 and reply.json()["reply"] == draft["generated_answer"]
        assert approve(reopened, draft["id"]).status_code == 409


def test_custom_document_seed_and_new_document_do_not_mix_demo_data(tmp_path, monkeypatch):
    imported = {"id": "records", "title": "Import records", "text": "Import records from Settings > Records using a TSV file."}
    seed = tmp_path / "customer-documents.json"
    seed.write_text(json.dumps([imported]), encoding="utf-8")
    monkeypatch.setenv("SUPPORT_DOCUMENTS", str(seed))
    path = tmp_path / "customer.db"
    with TestClient(create_app(path)) as client:
        docs = client.get("/api/documents").json()
        assert [d["id"] for d in docs] == ["records"]
        result = client.post("/api/ask", json={"question": "How do I import records?"}).json()
        assert result["status"] == "evidence_found"
        assert result["retrieval"][0]["doc_id"] == "records"
        new_doc = {"id": "export-invoices", "title": "Export invoices", "text": "Export invoices from Settings > Billing as a PDF file."}
        added = client.post("/api/documents", json=new_doc)
        assert added.status_code == 200 and added.json()["version"] == 1
        result = client.post("/api/ask", json={"question": "How do I export invoices?"}).json()
        assert result["status"] == "evidence_found" and result["retrieval"][0]["doc_id"] == "export-invoices"
        assert client.post("/api/documents", json=new_doc).status_code == 409
    monkeypatch.delenv("SUPPORT_DOCUMENTS")
    with TestClient(create_app(path)) as reopened:
        assert {d["id"] for d in reopened.get("/api/documents").json()} == {"records", "export-invoices"}


@pytest.mark.parametrize("http_status, finish_reason, expected", [
    (429, "stop", "model_rate_limited"),
    (401, "stop", "model_unavailable"),
    (402, "stop", "model_budget_exhausted"),
    (200, "length", "model_rejected"),
    (200, "content_filter", "model_rejected"),
])
def test_failed_model_response_never_becomes_a_customer_reply(tmp_path, http_status, finish_reason, expected):
    def respond(request):
        if http_status != 200:
            return httpx.Response(http_status, json={"error": {"message": "Synthetic transport failure"}})
        return response_for(request, finish_reason=finish_reason)
    model = model_for(respond)
    with TestClient(create_app(tmp_path / "failure.db", model=model)) as client:
        result = ask(client)
        assert result["status"] == expected and model.calls == 1
        assert result["generated_answer"] is None and result["claims"] == []
        assert client.get(f'/api/queries/{result["id"]}/reply').status_code == 409
        assert approve(client, result["id"]).status_code == 409
        handoff = client.post("/api/tickets", json={"query_id": result["id"]})
        assert handoff.status_code == 200 and handoff.json()["query_status"] == expected
