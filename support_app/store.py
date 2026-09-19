"""SQLite revisions and local handoffs; queries retain the evidence seen at the time."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
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
                docs = json.loads(Path(__file__).with_name("sample_docs.json").read_text())
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

    def save_query(self, result):
        with self.connect() as db:
            result["id"] = db.execute("INSERT INTO queries(result) VALUES (?)", (json.dumps(result),)).lastrowid
            db.execute("UPDATE queries SET result=? WHERE id=?", (json.dumps(result), result["id"]))
        return result

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
