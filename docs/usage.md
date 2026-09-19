# Setup and everyday use

Use this on your own computer with documents you are permitted to process. The application is a single local workspace, not an authenticated public service.

## Start with a small corpus

`examples/documents.json` is a working two-article input file. Point `SUPPORT_DOCUMENTS` to your copy and `SUPPORT_DB` to a new database filename before starting the server. On macOS/Linux use `export NAME=value` instead of PowerShell's `$env:NAME = 'value'`.

```json
[
  {
    "id": "export-links",
    "title": "Export download links",
    "text": "Export download links expire after 48 hours. Generate a new export when a link expires.",
    "fact_key": "export_link_validity",
    "fact_value": "48 hours"
  }
]
```

IDs use lowercase letters, digits, and hyphens, start with a letter or digit, and are at most 80 characters. Titles have 3–160 characters; text has 10–6,000. Separate paragraphs with a blank line. Each returned reference identifies the document, revision, and paragraph, for example `export-links@v1#p1`.

Both policy fields may be empty. If used, the key contains lowercase letters, digits, or underscores; the value must also occur in the article text. Use the same key only when two statements concern the same policy and audience. These tags identify disagreements between documents; they do not resolve them for you.

JSON imports only initialize an empty database. Subsequent changes are made in **Documents**. Use **New document** for another article; use **Save new version** to update one. A stale browser form gets a conflict response instead of overwriting a newer revision. Existing handoffs retain their old source excerpts.

## Answer mode

Set `SUPPORT_MODEL`, `SUPPORT_API_KEY`, and optionally `SUPPORT_API_BASE` in the environment of the Python process. The documented API root is `https://api.deepseek.com`; do not include `/chat/completions` in it. An HTTPS chat-completions endpoint can be configured. No real provider request has been made in the current validation; simulated transport checks are reported separately. HTTP is allowed only for a local endpoint.

The request uses JSON output, `max_tokens=1200`, no tool definitions, and `thinking.type=disabled` for DeepSeek. The complete request JSON is limited to 9,000 UTF-8 bytes. `MODEL_MAX_CALLS` defaults to 10 per process; restarting resets it. This is a request allowance, not a persistent billing account limit. No automatic retry is made after timeout or error.

The model proposes individual claims with exact evidence quotes. The application checks response format, source IDs, and whether each quote occurs in its cited paragraph. It does **not** decide that a paraphrased claim is entailed by the quote. That separate judgment belongs to the operator.

Open every claim's source, check scope and qualifiers, then approve with a note or reject. Approval only unlocks copying; it does not send a message. If cited revisions change or a relevant tagged conflict appears before approval or copying, reconcile the documents and ask again. A rejected draft cannot be copied as an approved reply. Both document evidence and model input are untrusted text; no model tools or account actions are enabled.

## When something does not work

| What you see | What to do |
| --- | --- |
| Sources found, but no draft | This is normal without `SUPPORT_MODEL`. Search mode makes no API requests. |
| Insufficient information | Check the requested feature or deadline is documented. Try the product's wording, or create a handoff; do not promise an undocumented feature. |
| Conflicting sources | Ask the policy owner to reconcile the tagged documents, save the edits, then ask again. |
| Model unavailable / timeout / rate limited | Check the API root, installed configuration, connectivity, and provider account. Existing sources and local tickets still work. An error is not a completed reply. |
| Request allowance used up | A person should decide whether to permit another run. Changing `MODEL_MAX_CALLS` takes effect after restart. |
| Model output withheld | The JSON was invalid, truncated, or its evidence references could not be checked. Hand off; no malformed draft is accepted. |
| Document changed | Refresh the document editor, or regenerate the answer if its sources changed. |
| New JSON file has no effect | You are reopening an existing database. Edit through Documents or choose a new `SUPPORT_DB` for a separate corpus. |

Model-enabled questions send the question and retrieved paragraphs to the configured provider. Do not include secrets or unauthorized customer data. Database files and environment files are ignored by Git. Back up a database before replacing your working environment; the app has no deletion or automatic retention policy.

## Where to customize

- Documents and policy tags: your JSON file and the browser editor.
- Product terminology and explicit paraphrases: `support_app/retrieval.py`; add paired supported/unsupported questions before changing these rules. The unknown-term check deliberately remains conservative.
- Escalation handling: `support_app/store.py` and the Handoffs view. The supplied queue is local; no external tracker is connected.
- Draft format and provider transport: `support_app/model.py`. Keep citation existence separate from semantic support and keep operator approval in the flow.

For a proposed client adaptation, start with 10–20 representative questions, permitted product documents, and an agreed escalation policy. Check the vocabulary and failure examples against that material before making accuracy or production claims.
