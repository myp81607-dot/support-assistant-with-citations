# HarborDesk · 可以核对来源的客服工作台

[English](README.md) · [逐题评测结果](docs/evaluation-results.json) · [参考说明](docs/references.md)

小型 B2B 软件公司的客服经常需要翻文档回答客户，遇到没有写清楚的政策容易误答。**HarborDesk 接收问题，返回带文档版本和原文的检索结果；资料不足或冲突时，生成可由人工处理的本地工单。** 编辑人员更新政策后，下一次检索立即使用新版本。

**这是合成资料的个人演示，不是付费客户项目。** HarborDesk 为虚构公司。默认已实现的是**检索、原文引文和人工交接**，不调用大语言模型，不冒充生成式回答。可选本地 Ollama 接口完成传输模拟测试，**尚未验证真实模型**。

![真实运行：问题、原文与版本](docs/screenshots/01-evidence.png)

## 五分钟启动

Python 3.11+，本次在 Windows / Python 3.14 实测。默认无需密钥、Docker、向量库或下载模型。

~~~bash
git clone https://github.com/myp81607-dot/ai-assistant-evaluation-demo.git
cd ai-assistant-evaluation-demo
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell 改用：
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements-app.txt
python -m uvicorn support_app.main:create_app --factory --host 127.0.0.1 --port 8123
~~~

打开 **http://127.0.0.1:8123**。首次启动向 `runtime/support.db` 写入 13 篇合成文档，后续修改和工单持续保留。通过 `SUPPORT_DB` 指定新文件可启动另一份独立演示，不会重新覆盖已有数据库。

| 输入或操作 | 可核对结果 |
| --- | --- |
| How do I rotate an API key? | 轮换密钥的原文与 `api-keys@v1#p1` 来源。 |
| How do I export data and close my workspace? | 导出与关闭工作区两份资料。 |
| Can I get a refund after 30 days? | 资料覆盖不足，交给人工，不编造退款政策。 |
| What is the data retention period? | 故意设置的 30 天 / 90 天政策冲突。 |
| Knowledge → API rate limits | 正文与政策值中的 **100** 改成 **200 requests per minute**，保存后重新提问，引用变成 `api-limits@v2#p1`。 |

在 **Handoff queue** 中填写调查说明、改为 In progress，最后填写处理结果并标为 Resolved。不会发邮件或写 CRM。对同一条查询重复创建工单会返回同一工单；旧工单保留当时的来源版本。

![真实运行：冲突需要人工判断](docs/screenshots/02-conflict.png)

![真实运行：本地工单及处理记录](docs/screenshots/03-handoff.png)

## 工作原理

~~~mermaid
flowchart LR
    Q[用户问题] --> R[检索当前文档段落]
    D[SQLite 文档版本] --> R
    R --> G{覆盖度与政策标签检查}
    G --> E[可核对的原文摘录]
    G --> H[人工复核]
    E --> H
    H --> T[本地工单与处理说明]
    R -. 可选 .-> M[本地 Ollama 选择引文]
    M --> V[原文及来源 ID 精确校验]
    V --> E
    V --> H
~~~

- **可解释检索：** 英文词元、少量显式归一化、逆文档频率加权、最多四个初始段落候选及覆盖度门槛。知识库未出现的词会触发人工复核。分数不是准确率或置信概率，检索与模型输出在 UI 中分开。
- **来源可核对：** 文档 ID、版本、段落及原文。默认不产生回答断言；可选模型只能返回与被引用的完整段落完全一致的文本，否则不显示。这只证明引文一致，不能证明完整回答了问题。
- **人工交接：** 资料不足、标签政策冲突、可识别指令攻击和模型错误均有明确状态。任何检索都可交给人工，SQLite 保存问题、原因、来源、状态及备注。
- **版本更新：** 追加版本，只检索每篇文档的最新版，保留历史。保存时检查旧版本号，避免无提示覆盖其他编辑。无需维护另一个向量索引。
- **模型边界：** 仅连接本地 Ollama HTTP，无工具执行能力，限制输出 token、超时和每个进程的调用次数。默认调用为零。

范围为一个业务场景、一个文档集合的小型助手，或已有 RAG 系统的来源与交接流程改进，不能承诺替代客服团队。

## 验证与复现

~~~bash
python -m pytest -q
python -m evaluation.run
~~~

评测使用新临时数据库，写入[逐题结果](docs/evaluation-results.json)，标签见 [evaluation/questions.json](evaluation/questions.json)。题目在首版实现后由独立 agent 编写，最初包含留出子集；后来已查看其中失败并修复代码，最终结果不再是盲测估计。这些标签未经领域专家确认，不是生产基准。

本地实测：**15 个功能测试通过；29 个诊断案例中 23 个符合固定标签；23 个指定来源的问题中 22 个找到全部必需文档；47 条展示引文均与原文、版本及段落一致。** 仍有 6 个措辞敏感的问题保守转人工，诊断命令因此有意返回退出码 1。

[验证说明](docs/validation.md)记录实际数量、已知失败、指标口径与浏览器流程。检索命中、应转人工处理和原文一致性分开统计。**没有测量生成式回答正确率、真实模型延迟或费用；复制原文不能直接计为回答正确。**

## 可选本地模型接口

项目不下载或启动模型。已有获授权的本地 Ollama 模型时，指定已安装名称：

~~~powershell
$env:SUPPORT_MODEL = 'your-installed-local-model'
$env:OLLAMA_URL = 'http://127.0.0.1:11434'
$env:MODEL_MAX_CALLS = '10'
python -m uvicorn support_app.main:create_app --factory --host 127.0.0.1 --port 8123
~~~

macOS/Linux 使用 `export NAME=value`；取消 `SUPPORT_MODEL` 回到纯检索。接口调用 `/api/chat`，要求 JSON、关闭流式输出，仅接受模型选择的完整原文段落，不接受自由生成政策。超时、服务不可用、进程调用额度耗尽、空结果和无依据输出都会进入可人工处理的失败状态。重启重置调用额度，这不是费用计量器。

**实连状态：** 仅通过明确标注的 HTTP 测试替身验证接口与失败响应；截图和指标不代表真实模型表现。未接入付费 API、CRM、邮件或外部工单平台。

## 重要限制

- 英文关键词检索会漏掉同义改写，也可能找到看似相关却没有回答问题的段落。覆盖度不等于语义支持，“Evidence found”仍需人工核对。
- 冲突检查依赖**编辑维护的政策键和值**，不是任意自然语言矛盾检测。正文与标签需同步修改；未标记事实不进行语义冲突检查。
- 正则只识别部分注入模式。更实际的边界是无工具执行能力、接受的模型输出必须是完整原文。知识库不应存秘密。
- 单用户、单工作区本地演示，无鉴权、多租户隔离、远程上传或公开部署。按示例仅监听回环地址，公开部署需另行设计访问与数据留存规则。
- 不含 PDF 抓取、向量嵌入、多语言、流式回答或自动业务动作。

## 代码位置与旧学习基线

| 路径 | 用途 |
| --- | --- |
| `support_app/` | FastAPI、SQLite、检索、本地模型接口 |
| `support_app/static/` | 无前端依赖的英文界面 |
| `support_app/sample_docs.json` | 合成资料及故意设置的政策冲突 |
| `evaluation/`、`tests/` | 问答诊断与功能验证 |
| `docs/` | 真实截图、测试结果、来源 |
| `src/mini_rag_demo.py`、`data/`、`outputs/evaluation_results.csv` | **保持不变的原学习基线** |

原版用字符 TF-IDF 检索，将首条结果拼入固定中文文本。`grounded`、`has_context`只是字符串存在性检查，**不是回答质量评测**。原代码及 Git 历史保留。单独运行时安装 `requirements.txt`，在根目录执行 `python src/mini_rag_demo.py` 会重新生成旧 CSV；新应用使用 `requirements-app.txt`，不依赖 pandas 或 scikit-learn。

## 参考与开发归属

新应用、资料、界面和测试使用 AI 辅助独立开发，未复制参考项目代码、提示词、资料或资源。[参考说明](docs/references.md)保留上游许可证信息与实际借鉴点：可检查引文、显式拒答和人工升级处理。

**作品介绍一句话：** 将产品文档问题转化为版本可追溯的原文证据及可处理的人工工单，提供可复现失败案例和尚未实连的本地模型接口。
