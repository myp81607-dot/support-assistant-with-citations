# References and implementation ownership

Reviewed 2026-09-19. These are design references, not clients or evidence of this project's performance. No code, prompts, datasets, screenshots, or assets were copied from either repository.

| Source | License / provenance | Concrete influence |
| --- | --- | --- |
| [RaphaelBudin/rag-support-agent](https://github.com/RaphaelBudin/rag-support-agent) | [GPL-3.0](https://github.com/RaphaelBudin/rag-support-agent/blob/main/LICENSE) | Separate retrieval diagnostics, source attribution, abstention. Here these use a small lexical ranker, tagged policy conflicts, and local tickets, without the upstream hybrid retrieval code. |
| [rahulmahadik/kai-rag](https://github.com/rahulmahadik/kai-rag) | [MIT, Rahul Mahadik](https://github.com/rahulmahadik/kai-rag/blob/main/LICENSE) | Question-to-human-review loop and visible source context. Here the queue uses local SQLite; no upstream code, bots, trackers, or automatic learning. |
| [DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion) | Official interface documentation | The configurable adapter posts to `/chat/completions`, reads `choices[].message.content` and token usage, and rejects incomplete responses. It sends no tools or business actions. |
| [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode) | Official interface documentation | JSON response mode, a prompt with the expected structure, and a bounded output. The app validates claim/citation fields and exact quoted text; JSON validity and quote existence do not establish that a claim is supported. A person reviews that separately. |
| [DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode) | Official interface documentation | Explicitly disables thinking for the documented DeepSeek endpoint instead of relying on the provider default. |
| [DeepSeek models and pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing) | Official provider documentation | Current `deepseek-flash` model name and token rates used to plan bounded verification. Prices can change; estimates are not measured spending. |
| [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/) | Official framework documentation | TestClient checks through real routes for validation, persistence, and failures. |

The model adapter has been checked with local HTTP transport fixtures. Live DeepSeek answer validation is still pending authorization for paid requests; interface compliance is not a claim of answer accuracy.

The original TF-IDF baseline and Git history remain. New work consists of the FastAPI app, lexical paragraph ranker and phrase aliases, tagged conflict checks, versioned SQLite documents and tickets, chat-completions adapter, claim review and approval flow, browser UI, synthetic HarborDesk documents, evaluation and tests. Development and independent diagnostic review used AI assistance; no external customer or data is represented.

Dependency licenses remain those of their packages. Reference licenses above preserve authorship and source attribution; this repository does not distribute or relicense their code.
