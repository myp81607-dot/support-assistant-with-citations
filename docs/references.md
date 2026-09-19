# References and implementation ownership

Reviewed 2026-09-19. These are design references, not clients or evidence of this project's performance. No code, prompts, datasets, screenshots, or assets were copied from either repository.

| Source | License / provenance | Concrete influence |
| --- | --- | --- |
| [RaphaelBudin/rag-support-agent](https://github.com/RaphaelBudin/rag-support-agent) | [GPL-3.0](https://github.com/RaphaelBudin/rag-support-agent/blob/main/LICENSE) | Separate retrieval diagnostics, source attribution, abstention. Here these use a small lexical ranker, tagged policy conflicts, and local tickets, without the upstream hybrid retrieval code. |
| [rahulmahadik/kai-rag](https://github.com/rahulmahadik/kai-rag) | [MIT, Rahul Mahadik](https://github.com/rahulmahadik/kai-rag/blob/main/LICENSE) | Question-to-human-review loop and visible source context. Here the queue uses local SQLite; no upstream code, bots, trackers, or automatic learning. |
| [Ollama chat API](https://docs.ollama.com/api/chat) | Official interface documentation | POST /api/chat, messages, format, stream:false, and message.content. HTTP contract tested with explicit test doubles; live model unverified. |
| [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/) | Official framework documentation | TestClient checks through real routes for validation, persistence, and failures. |

The original TF-IDF baseline and Git history remain. New work consists of the FastAPI app, paragraph ranker, tagged conflict checks, revisioned SQLite store, constrained Ollama adapter, browser UI, synthetic HarborDesk documents, evaluation and tests. Development and independent diagnostic review used AI assistance; no external customer or data is represented.

Dependency licenses remain those of their packages. Reference licenses above preserve authorship and source attribution; this repository does not distribute or relicense their code.

