import os
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from .model import ModelFailure, ChatCompletions
from .documents import Document, DocUpdate
from .retrieval import retrieve, suspicious, tokens
from .store import Store

ROOT = Path(__file__).resolve().parent


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def check_text(self):
        self.question = self.question.strip()
        if len(self.question) < 3:
            raise ValueError("Enter a question of at least 3 characters.")
        return self


class NewTicket(BaseModel):
    query_id: int = Field(gt=0)


class TicketUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"]
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def resolution_note(self):
        if self.status == "resolved" and not self.notes.strip():
            raise ValueError("Add a resolution note before resolving the ticket.")
        return self


class DraftReview(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=2000)
    support_checked: bool = False

    @model_validator(mode="after")
    def check_note(self):
        if len(self.note.strip()) < 3:
            raise ValueError("Add a short review note.")
        return self


def create_app(db_path=None, model=None):
    app = FastAPI(title="HarborDesk support workspace", version="1.1.0")
    store = Store(db_path or os.environ.get("SUPPORT_DB", "runtime/support.db"), os.environ.get("SUPPORT_DOCUMENTS"))
    app.state.store = store
    if model is None and os.environ.get("SUPPORT_MODEL"):
        model = ChatCompletions(os.environ["SUPPORT_MODEL"], os.environ.get("SUPPORT_API_KEY", ""),
                               os.environ.get("SUPPORT_API_BASE", "https://api.deepseek.com"),
                               int(os.environ.get("MODEL_MAX_CALLS", "10")))
    mode = "answer" if model else "evidence"

    @app.middleware("http")
    async def same_origin_writes(request: Request, call_next):
        # The UI is local-only; reject cross-site browser mutations.
        origin = request.headers.get("origin")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Cross-origin writes are not allowed."}, status_code=403)
        return await call_next(request)

    @app.get("/api/overview")
    def overview():
        return {"mode": mode, "model_verified": False, "model_name": model.model if model else None,
                "model_requests": model.calls if model else 0, "documents": len(store.documents()),
                "open_tickets": sum(t["status"] != "resolved" for t in store.tickets())}

    @app.get("/api/documents")
    def documents():
        return store.documents()

    @app.post("/api/documents")
    def new_document(body: Document):
        try:
            return store.add_document(body.model_dump())
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/api/documents/{doc_id}/history")
    def history(doc_id: str):
        result = store.history(doc_id)
        if not result:
            raise HTTPException(404, "Document not found.")
        return result

    @app.put("/api/documents/{doc_id}")
    def update_doc(doc_id: str, body: DocUpdate):
        try:
            return store.update_document(doc_id, body.model_dump())
        except KeyError:
            raise HTTPException(404, "Document not found.") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/api/ask")
    def ask(body: Question):
        start = time.perf_counter()
        current_documents = store.documents()
        sources, coverage, conflicts, blocked = retrieve(body.question, current_documents)
        vocabulary = set().union(*(tokens(d["title"] + " " + d["text"]) for d in current_documents
                                   if d["id"] not in blocked))
        unknown_terms = sorted(tokens(body.question) - vocabulary)
        result = {"question": body.question, "mode": mode, "retrieval": sources, "conflicts": conflicts,
                  "coverage": round(coverage, 3), "unknown_terms": unknown_terms,
                  "blocked_documents": blocked, "claims": [], "generated_answer": None,
                  "citation_validation": "not_applicable", "support_validation": "not_assessed",
                  "review": {"status": "not_applicable"}, "usage": {},
                  "revision_label": ", ".join(dict.fromkeys(f'{s["doc_id"]} v{s["version"]}' for s in sources))}
        if suspicious(body.question):
            result.update(status="unsafe_request", reason="This request includes an instruction override or secret request. It was not executed; a person can review it.")
        elif conflicts:
            result.update(status="conflict", reason="Current documents disagree on a tagged policy. A person must reconcile the sources before giving a policy answer.")
        elif not sources or coverage < .60 or unknown_terms:
            result.update(status="needs_review", reason="The documents do not cover enough of this question. No answer was generated. Create a handoff for a person to investigate.")
        elif not model:
            result.update(status="evidence_found", reason="Relevant document excerpts found. No language model was called. Verify the excerpts answer your question; hand off if they do not.")
        else:
            try:
                draft = model.draft(body.question, sources)
                result["claims"] = draft["claims"]
                result["generated_answer"] = "\n\n".join(c["text"] + " " + " ".join(
                    f'[{citation["source_id"]}]' for citation in c["citations"]) for c in result["claims"])
                result.update(status="draft_ready", reason="Review the draft and its evidence before using it as a customer reply.",
                              citation_validation="passed", support_validation="human_review_required",
                              review={"status": "pending"}, usage=draft["usage"], model=draft["model"])
            except ModelFailure as exc:
                result.update(status=exc.status, reason=exc.message)
        result["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return store.save_query(result)

    @app.post("/api/queries/{query_id}/review")
    def review_draft(query_id: int, body: DraftReview):
        try:
            return store.review_query(query_id, body.decision, body.note.strip(), body.support_checked)
        except KeyError:
            raise HTTPException(404, "Question not found.") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/api/queries/{query_id}/reply")
    def copy_reply(query_id: int):
        try:
            return {"reply": store.approved_reply(query_id)}
        except KeyError:
            raise HTTPException(404, "Question not found.") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/api/tickets")
    def new_ticket(body: NewTicket):
        try:
            return store.ticket(body.query_id)
        except KeyError:
            raise HTTPException(404, "Question not found.") from None

    @app.get("/api/tickets")
    def tickets():
        return store.tickets()

    @app.patch("/api/tickets/{ticket_id}")
    def update_ticket(ticket_id: int, body: TicketUpdate):
        try:
            return store.update_ticket(ticket_id, body.status, body.notes)
        except KeyError:
            raise HTTPException(404, "Ticket not found.") from None

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static", check_dir=False), name="static")
    return app
