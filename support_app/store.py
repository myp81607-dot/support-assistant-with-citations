"""SQLite revisions and local handoffs; queries retain the evidence seen at the time."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .documents import Document
from .retrieval import retrieve


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path, seed_path=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT, version INTEGER, title TEXT, text TEXT,
                    fact_key TEXT, fact_value TEXT, updated_at TEXT,
                    PRIMARY KEY(id, version));
                CREATE TABLE IF NOT EXISTS queries (id INTEGER PRIMARY KEY, result TEXT);
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY, query_id INTEGER UNIQUE,
                    status TEXT, notes TEXT, created_at TEXT);
            """)
            if not db.execute("SELECT 1 FROM documents LIMIT 1").fetchone():
                source = Path(seed_path) if seed_path else Path(__file__).with_name("sample_docs.json")
                raw = json.loads(source.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    raise ValueError("The document file must contain a JSON array.")
                docs = [Document.model_validate(d).model_dump() for d in raw]
                if len({d["id"] for d in docs}) != len(docs):
                    raise ValueError("Document IDs must be unique in the import file.")
                db.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?)", [
                    (d["id"], 1, d["title"], d["text"], d.get("fact_key", ""),
                     d.get("fact_value", ""), now()) for d in docs
                ])

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def documents(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("""SELECT d.* FROM documents d JOIN
                (SELECT id, MAX(version) version FROM documents GROUP BY id) latest
                ON d.id=latest.id AND d.version=latest.version ORDER BY d.id""")]

    def history(self, doc_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM documents WHERE id=? ORDER BY version DESC", (doc_id,))]

    def update_document(self, doc_id, data):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM documents WHERE id=? ORDER BY version DESC LIMIT 1", (doc_id,)).fetchone()
            if old is None:
                raise KeyError(doc_id)
            if old["version"] != data["expected_version"]:
                raise ValueError("This document changed. Reload it before saving.")
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?)", (
                doc_id, old["version"] + 1, old["title"], data["text"],
                data["fact_key"], data["fact_value"], now()))
        return self.history(doc_id)[0]

    def add_document(self, data):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM documents WHERE id=?", (data["id"],)).fetchone():
                raise ValueError("That document ID already exists. Open it to save a new version.")
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?)", (
                data["id"], 1, data["title"], data["text"], data["fact_key"], data["fact_value"], now()))
        return self.history(data["id"])[0]

    def save_query(self, result):
        with self.connect() as db:
            result["id"] = db.execute("INSERT INTO queries(result) VALUES (?)", (json.dumps(result),)).lastrowid
            db.execute("UPDATE queries SET result=? WHERE id=?", (json.dumps(result), result["id"]))
        return result

    @staticmethod
    def _query(db, query_id):
        row = db.execute("SELECT result FROM queries WHERE id=?", (query_id,)).fetchone()
        if row is None:
            raise KeyError(query_id)
        return json.loads(row[0])

    @staticmethod
    def _check_current_sources(db, query):
        used = {c["source_id"] for claim in query["claims"] for c in claim["citations"]}
        for source in query["retrieval"]:
            if source["source_id"] in used:
                latest = db.execute("SELECT MAX(version) FROM documents WHERE id=?", (source["doc_id"],)).fetchone()[0]
                if latest != source["version"]:
                    raise ValueError("A cited document changed. Ask the question again and review the new draft.")
        current = [dict(row) for row in db.execute("""SELECT * FROM documents
            WHERE (id, version) IN (SELECT id, MAX(version) FROM documents GROUP BY id)""")]
        if retrieve(query["question"], current)[2]:
            raise ValueError("The current documents contain a conflicting policy. Ask again and resolve the conflict before replying.")

    def review_query(self, query_id, decision, note, support_checked):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            query = self._query(db, query_id)
            if query["status"] != "draft_ready":
                raise ValueError("Only a generated draft can be reviewed.")
            if query.get("review", {}).get("status") != "pending":
                raise ValueError("This draft was already reviewed. Ask again for a new draft.")
            if decision == "approved":
                if not support_checked:
                    raise ValueError("Check each claim against its evidence before approving.")
                self._check_current_sources(db, query)
            query["review"] = {"status": decision, "note": note, "reviewed_at": now(),
                               "support_checked": support_checked if decision == "approved" else False}
            db.execute("UPDATE queries SET result=? WHERE id=?", (json.dumps(query), query_id))
        return query

    def approved_reply(self, query_id):
        with self.connect() as db:
            db.execute("BEGIN")
            query = self._query(db, query_id)
            if query.get("review", {}).get("status") != "approved":
                raise ValueError("A person must approve the draft before it can be copied as a reply.")
            self._check_current_sources(db, query)
        return query["generated_answer"]

    def ticket(self, query_id):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM queries WHERE id=?", (query_id,)).fetchone():
                raise KeyError(query_id)
            db.execute("INSERT OR IGNORE INTO tickets(query_id,status,notes,created_at) VALUES (?,'open','',?)", (query_id, now()))
            ticket_id = db.execute("SELECT id FROM tickets WHERE query_id=?", (query_id,)).fetchone()[0]
        return next(t for t in self.tickets() if t["id"] == ticket_id)

    def tickets(self):
        with self.connect() as db:
            rows = db.execute("SELECT t.*, q.result FROM tickets t JOIN queries q ON q.id=t.query_id ORDER BY t.id DESC")
            results = []
            for row in rows:
                item = dict(row)
                query = json.loads(item.pop("result"))
                item.update(question=query["question"], reason=query["reason"],
                            sources=query["retrieval"], query_status=query["status"])
                results.append(item)
            return results

    def update_ticket(self, ticket_id, status, notes):
        with self.connect() as db:
            cursor = db.execute("UPDATE tickets SET status=?, notes=? WHERE id=?", (status, notes, ticket_id))
            if not cursor.rowcount:
                raise KeyError(ticket_id)
        return next(t for t in self.tickets() if t["id"] == ticket_id)
