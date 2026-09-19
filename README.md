# Support Assistant with Citations

For a small software support team that answers the same product questions from scattered documents. Paste a customer's question, check a draft against its sources, then approve it for copying or leave a local handoff for a colleague.

[Watch the 35-second search and handoff demo](docs/demo.webm) · [中文](README.zh-CN.md) · [What was tested](docs/validation.md)

Question → sources → draft → operator review → copy or handoff.

This is a personal project using a fictional company and synthetic policies. It runs without a model as a document-search tool. The DeepSeek adapter and approval flow have been tested with simulated HTTP responses; live model answers have not yet been tested. It never sends a customer message or changes an account.

![Support question with its sources](docs/screenshots/01-evidence.jpg)

## Run it

Python 3.11 or newer. The tested environment is Windows with Python 3.14.

~~~bash
git clone https://github.com/myp81607-dot/support-assistant-with-citations.git
cd support-assistant-with-citations
python -m venv .venv
~~~

Activate the environment with `.venv\Scripts\Activate.ps1` on PowerShell, or `source .venv/bin/activate` on macOS/Linux. Then:

~~~bash
python -m pip install -r requirements-app.txt
python -m uvicorn support_app.main:create_app --factory --host 127.0.0.1 --port 8123
~~~

Open [localhost:8123](http://127.0.0.1:8123). The default mode needs no API key. It starts with 13 HarborDesk documents and saves edits and tickets in `runtime/support.db`.

Try “How long do export download links last?” and compare it with “Can I export tickets as a JSON archive?” The first has a 24-hour source. The second has no documented JSON capability and goes to review. “Is customer data retained for 30 days or 90 days?” exposes an intentional conflict.

In answer mode, open each citation and compare the claim with the quoted passage. A checked source ID is not proof that a claim follows from that source. The operator must confirm support and add a note before **Copy approved reply** becomes available. If a cited document changes or a relevant tagged conflict appears, the old draft cannot be copied; reconcile the documents and ask again.

## Put your own documents in it

For a first trial, copy [examples/documents.json](examples/documents.json), replace the text with material you are allowed to use, and start a separate database:

~~~powershell
$env:SUPPORT_DOCUMENTS = 'examples/documents.json'
$env:SUPPORT_DB = 'runtime/my-support.db'
python -m uvicorn support_app.main:create_app --factory --host 127.0.0.1 --port 8123
~~~

This example contains two documents and a 48-hour export-link policy. It does not mix in the HarborDesk demo. Import runs only when the database has no documents; after that, use **Documents** to add text or save a new version. Changing the JSON file does not overwrite an existing database.

Use one short article per record. Keep a stable `id`, a descriptive `title`, and the original `text`. Optional `fact_key` / `fact_value` identify policies that should agree across documents. For example, two articles with `export_link_validity` but different durations are flagged. This is an editor-maintained check, not a general contradiction detector.

[Setup and operating notes](docs/usage.md) cover the file format, configuration, common errors, and the small places to customize.

## Enable draft answers

The documented provider is DeepSeek through its chat-completions API. Configure the key in the server environment, never in browser code or a committed file:

~~~powershell
$env:SUPPORT_API_KEY = '<your API key>'
$env:SUPPORT_MODEL = 'deepseek-flash'
$env:SUPPORT_API_BASE = 'https://api.deepseek.com'
$env:MODEL_MAX_CALLS = '10'
~~~

Then start the server as above. API use can incur charges. The app disables thinking, limits output to 1,200 tokens, caps request size, and makes no automatic retries. Unset `SUPPORT_MODEL` to return to search-only mode. The former exact-paragraph model selector has been replaced by concise, cited drafts; the no-model evidence baseline remains.

An unavailable model, quota/rate-limit response, malformed output, unknown citation, or quote not present in the source leaves the question open for review. The retrieved text and handoff remain available. No external tools are given to the model.

## Checks and boundaries

~~~bash
python -m pytest -q
python -m evaluation.run
~~~

The original 29 questions and their labels are retained. Six previously failing paraphrases are now covered by explicit vocabulary rules, with additional paired cases for supported and unsupported requests. These are regression results, not an unseen accuracy benchmark. [Validation](docs/validation.md) separates retrieval, source-reference checks, answer support, operator approval, live integration, timing, and cost.

This remains a local, single-workspace application without authentication or document permissions. Bind it to loopback. English lexical retrieval still needs a question set for your product; it does not understand every paraphrase. Policy tags require maintenance. Human review is part of the reply workflow, not a claim that generated answers are automatically correct.

The useful customization scope is a small product knowledge base, cited draft replies, document revisions, or an existing support team's handoff process. Start with permitted documents, representative customer questions, and clear rules for escalation. Public hosting, tenant permissions, CRM delivery, and automatic refunds are outside this version.

The original learning script, `src/mini_rag_demo.py`, its CSV data, and its Git history are unchanged. That script's string-presence checks are not answer-quality measurements. The working app is in `support_app/`; [reference notes](docs/references.md) explain the open-source design references and licenses. Implementation and diagnostic review used AI assistance.
