/* HarborDesk: local, dependency-free UI. Untrusted content is inserted as text. */
"use strict";

const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
const state = {view: "questions", result: null, tickets: [], documents: [], selectedTicket: null, selectedDocument: null, asking: false, answerMode: false};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function append(parent, ...children) {
  for (const child of children) if (child) parent.append(child);
  return parent;
}

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  let body;
  try { body = await response.json(); } catch { body = null; }
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : Array.isArray(body?.detail) ? body.detail.map(item => item.msg.replace(/^Value error, /, "")).join(" ") : (response.status === 409 ? "This document changed while you were editing. Reload it before saving again." : `Request failed (${response.status}). Please try again.`);
    throw new Error(detail);
  }
  return body;
}

function globalError(error) {
  const node = $("#global-error");
  node.textContent = error?.message || String(error);
  node.classList.remove("hidden");
}

function clearError() { $("#global-error").classList.add("hidden"); }
function dateLabel(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("en-US", {month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"});
}
function versionLabel(value) { return `v${String(value ?? "—").replace(/^v/i, "")}`; }
function tag(text) { return el("span", "tag", text); }
function statusLabel(value) { return String(value || "open").replaceAll("_", " "); }
function setLoading(target, message) {
  target.replaceChildren(append(el("div", "loading"), el("span", "spinner"), el("span", "", message)));
}

async function refreshOverview() {
  const data = await api("/api/overview");
  $("#document-count").textContent = data.documents;
  $("#queue-count").textContent = data.open_tickets;
  state.answerMode = data.mode !== "evidence";
  $("#mode-label").textContent = state.answerMode ? "Answer mode" : "Evidence mode";
  $("#model-status").textContent = state.answerMode ? `${data.model_name || "Configured model"} · ${data.model_requests || 0} requests` : "No model calls";
  $("#mode-note").textContent = state.answerMode ? "Model drafts require your source review and approval before copying a customer reply. No reply is sent by this app." : "Evidence mode finds passages without calling a model. Review the text before writing a reply.";
  if (!state.asking) $("#ask-button").textContent = state.answerMode ? "Draft reply" : "Find sources";
}

function sourceCard(source, index, sourceMap) {
  const card = el("article", "source-card");
  card.tabIndex = -1;
  const top = el("div", "source-top");
  append(top, el("span", "source-letter", source.source_id || `S${index + 1}`), el("h3", "", source.title || source.doc_id || "Source document"), el("span", "version", versionLabel(source.version)));
  append(card, top, el("blockquote", "", source.text || "No excerpt is available."));
  const quotedEvidence = el("div", "quoted-evidence hidden");
  append(card, quotedEvidence);
  if (sourceMap) sourceMap.set(source.source_id || `S${index + 1}`, {card, quotedEvidence});
  const footer = el("div", "source-footer");
  append(footer, el("span", "", source.doc_id || source.source_id || "Source"));
  if (source.score !== undefined && source.score !== null) {
    const score = Number(source.score);
    append(footer, el("span", "", `Ranking score ${Number.isFinite(score) ? score.toFixed(3) : source.score}`));
  }
  append(card, footer);
  return card;
}

function citationButton(citation, sourceMap) {
  const button = el("button", "citation-button", citation.source_id || "Source");
  button.type = "button";
  button.addEventListener("click", () => {
    const target = sourceMap.get(citation.source_id);
    if (!target) { globalError(new Error("This source is missing from the saved result. Do not approve this draft.")); return; }
    for (const source of sourceMap.values()) { source.card.classList.remove("source-selected"); source.quotedEvidence.classList.add("hidden"); }
    target.quotedEvidence.replaceChildren(el("strong", "", "Evidence cited for this claim"), el("p", "", citation.quote || "No quotation supplied."));
    target.quotedEvidence.classList.remove("hidden");
    target.card.classList.add("source-selected");
    target.card.scrollIntoView({behavior: "smooth", block: "center"});
    target.card.focus({preventScroll: true});
  });
  return button;
}

function renderReview(result) {
  const panel = el("section", "review-panel");
  const review = result.review || {status: "pending"};
  const status = el("p", "form-status"); status.setAttribute("role", "status");
  if (review.status === "approved") {
    append(panel, el("h3", "", "Reply approved"), el("p", "muted", "You approved this draft after reviewing its sources. Nothing has been sent."));
    if (review.note) panel.append(el("p", "review-note", review.note));
    const copy = el("button", "primary", "Copy approved reply"); copy.type = "button";
    copy.addEventListener("click", async () => {
      copy.disabled = true; status.className = "form-status"; status.textContent = "Checking document versions…";
      try {
        const current = await api(`/api/queries/${encodeURIComponent(result.id)}/reply`);
        await navigator.clipboard.writeText(current.reply);
        status.textContent = "Copied. Paste it into your support tool when ready.";
      } catch (error) { status.textContent = error.message; status.className = "form-status error"; }
      finally { copy.disabled = false; }
    });
    append(panel, append(el("div", "form-actions"), copy), status);
    return panel;
  }
  if (review.status === "rejected") {
    append(panel, el("h3", "", "Draft rejected"), el("p", "muted", "Use a handoff below if a person needs to investigate."));
    if (review.note) panel.append(el("p", "review-note", review.note));
    return panel;
  }
  const form = el("form");
  append(form, el("h3", "", "Review before use"), el("p", "review-explanation", "Source references checked. Whether the evidence supports each claim still needs your review."));
  const checked = el("input"); checked.type = "checkbox"; checked.id = "support-checked";
  const checkedLabel = el("label", "checkbox-label");
  append(checkedLabel, checked, el("span", "", "I checked each claim against the quoted evidence and it is supported."));
  const noteLabel = el("label", "", "Review note"); noteLabel.htmlFor = "review-note";
  const note = el("textarea"); note.id = "review-note"; note.rows = 2; note.maxLength = 2000; note.minLength = 3; note.required = true; note.placeholder = "Record what you checked, a caveat, or why this draft should not be used.";
  const approve = el("button", "primary", "Approve reply"); approve.type = "submit"; approve.disabled = true;
  const reject = el("button", "secondary", "Reject draft"); reject.type = "button";
  checked.addEventListener("change", () => { approve.disabled = !checked.checked; });
  const decide = async decision => {
    if (decision === "approved" && !checked.checked) return;
    if (note.value.trim().length < 3) { status.textContent = "Add a review note of at least 3 characters."; status.className = "form-status error"; note.focus(); return; }
    approve.disabled = true; reject.disabled = true; status.className = "form-status"; status.textContent = "Saving review…";
    try {
      const updated = await api(`/api/queries/${encodeURIComponent(result.id)}/review`, {method: "POST", body: JSON.stringify({decision, note: note.value.trim(), support_checked: checked.checked})});
      if (state.result?.id === result.id) { state.result = updated; renderResult(updated); }
    } catch (error) { status.textContent = error.message; status.className = "form-status error"; approve.disabled = !checked.checked; reject.disabled = false; }
  };
  form.addEventListener("submit", event => { event.preventDefault(); decide("approved"); });
  reject.addEventListener("click", () => decide("rejected"));
  append(form, checkedLabel, noteLabel, note, append(el("div", "form-actions"), approve, reject), status);
  panel.append(form);
  return panel;
}

function sectionHeading(title, note) {
  return append(el("div", "subheading"), el("span", "", title), note ? el("small", "", note) : null);
}

function renderResult(result) {
  const body = el("div", "result-body");
  const isEvidence = result.status === "evidence_found";
  const isDraft = result.status === "draft_ready";
  const sourceMap = new Map();
  const titles = {evidence_found: "Sources found", draft_ready: "Draft ready for review", needs_review: "More information needed", conflict: "The sources disagree", unsafe_request: "Request needs review", model_quotes: "Source quotations need review", model_timeout: "Model timed out", model_budget_exhausted: "Model request limit reached", model_insufficient: "Not enough evidence for a draft", model_rejected: "Model output withheld", model_error: "Model unavailable", model_unavailable: "Model unavailable", model_invalid: "Model output could not be used", model_unsupported: "Model output could not be used"};
  const banner = el("div", `result-banner${isEvidence || isDraft ? "" : " warning"}`);
  const reviewedTitle = isDraft && result.review?.status === "approved" ? "Draft approved" : isDraft && result.review?.status === "rejected" ? "Draft rejected" : null;
  const reviewedReason = reviewedTitle ? (result.review.status === "approved" ? "Ready to copy after a document-version check. No reply has been sent." : "This draft was rejected. Create a handoff if a person needs to investigate.") : null;
  append(banner, el("h2", "", reviewedTitle || titles[result.status] || "Review required"), el("p", "", reviewedReason || result.reason || "Review the original sources before responding to your customer."));
  const meta = el("div", "result-meta");
  append(meta, el("span", "", result.revision_label || "Current document versions"));
  append(banner, meta);
  append(body, banner, el("p", "result-question", `Question: ${result.question}`));
  if (result.generated_answer) {
    const draft = el("section", "draft-answer");
    append(draft, el("h2", "", "Draft answer"), el("div", "generated-answer", result.generated_answer));
    if (Array.isArray(result.claims) && result.claims.length) {
      append(draft, sectionHeading("Check the claims", "Open each cited passage"));
      for (const claim of result.claims) {
        const item = el("div", "claim-item");
        append(item, el("p", "", claim.text));
        const citations = el("div", "claim-citations");
        for (const citation of claim.citations || []) citations.append(citationButton(citation, sourceMap));
        if (!citations.childElementCount) citations.append(el("span", "form-status error", "No source attached"));
        item.append(citations); draft.append(item);
      }
    }
    append(body, draft);
    if (isDraft) body.append(renderReview(result));
  } else {
    append(body, el("p", "section-note", result.mode !== "evidence" ? "No draft is available. Review the retrieved passages or create a handoff." : "These are source excerpts, not a generated answer."));
  }
  if (Array.isArray(result.conflicts) && result.conflicts.length) {
    append(body, sectionHeading("Conflicting policy facts"));
    for (const conflict of result.conflicts) append(body, el("div", "conflict-line", `${conflict.key}: ${(conflict.values || []).map(value => typeof value === "object" ? JSON.stringify(value) : value).join(" ↔ ")}`));
  }
  const retrieval = Array.isArray(result.retrieval) ? result.retrieval : [];
  append(body, sectionHeading(`Source passages (${retrieval.length})`, "Retrieval rank is not answer confidence"));
  if (retrieval.length) retrieval.forEach((source, index) => body.append(sourceCard(source, index, sourceMap)));
  else append(body, el("p", "empty-detail-message", "No supporting passage is available for this question. Pass it to an operator instead of guessing."));
  const handoff = el("div", "handoff-bar");
  const explanation = append(el("p"), el("strong", "", "Need someone to investigate?"), el("span", "", "Save this question and its sources as a local ticket."));
  const button = el("button", "secondary", "Create handoff");
  button.type = "button";
  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Creating handoff…";
    try {
      const ticket = await api("/api/tickets", {method: "POST", body: JSON.stringify({query_id: result.id})});
      button.textContent = "Open handoff";
      button.disabled = false;
      const openButton = button.cloneNode(true);
      button.replaceWith(openButton);
      openButton.addEventListener("click", async () => { state.selectedTicket = ticket.id; await navigate("tickets"); });
      explanation.replaceChildren(el("strong", "", `Handoff ${ticket.id} created`), el("span", "", "Saved locally with the evidence used for this question."));
      await refreshOverview();
    } catch (error) { globalError(error); button.disabled = false; button.textContent = "Try creating handoff again"; }
  });
  append(body, append(handoff, explanation, button));
  $("#response-content").replaceChildren(body);
  $("#response-time").textContent = Number.isFinite(Number(result.elapsed_ms)) ? `${Math.round(Number(result.elapsed_ms))} ms` : "";
}

$("#ask-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (state.asking) return;
  const question = $("#question").value.trim();
  if (!question) { $("#question").focus(); return; }
  clearError();
  state.asking = true;
  $$("[data-question]").forEach(item => { item.disabled = true; });
  const button = $("#ask-button");
  button.disabled = true;
  button.textContent = state.answerMode ? "Preparing draft…" : "Finding sources…";
  $("#response-time").textContent = "Working…";
  if (!state.result) setLoading($("#response-content"), "Searching the current document versions…");
  try {
    state.result = await api("/api/ask", {method: "POST", body: JSON.stringify({question})});
    renderResult(state.result);
    await refreshOverview().catch(globalError);
  } catch (error) {
    globalError(error);
    if (!state.result) $("#response-content").replaceChildren(append(el("div", "result-body"), el("p", "muted", "No result was received. Your question is still in the editor; try again when the service is available.")));
    $("#response-time").textContent = state.result ? "Previous result retained" : "Request failed";
  } finally {
    state.asking = false;
    $$("[data-question]").forEach(item => { item.disabled = false; });
    button.disabled = false;
    button.textContent = state.answerMode ? "Draft reply" : "Find sources";
  }
});

$$('[data-question]').forEach(button => button.addEventListener("click", () => {
  $("#question").value = button.dataset.question;
  $("#ask-form").requestSubmit();
}));

function renderTicketList() {
  const target = $("#ticket-list");
  target.replaceChildren();
  $("#ticket-total").textContent = `${state.tickets.length} total`;
  if (!state.tickets.length) target.append(el("p", "record-empty", "No handoffs yet. Ask a question, then create a local handoff from its evidence panel."));
  for (const ticket of state.tickets) {
    const button = el("button", `record-button${state.selectedTicket === ticket.id ? " selected" : ""}`);
    append(button, el("strong", "", ticket.question), append(el("small"), tag(statusLabel(ticket.status)), el("span", "", ticket.id)));
    button.addEventListener("click", () => { state.selectedTicket = ticket.id; renderTicketList(); renderTicket(ticket); });
    target.append(button);
  }
}

function renderTicket(ticket) {
  const target = $("#ticket-detail");
  target.replaceChildren(el("h2", "", "Review handoff"), append(el("div", "detail-meta"), tag(ticket.id), el("span", "", `Created ${dateLabel(ticket.created_at)}`)), el("p", "ticket-question", ticket.question), el("p", "detail-reason", ticket.reason || "Operator review requested."));
  const form = el("form");
  const label = el("label", "", "Ticket status");
  label.htmlFor = "ticket-status";
  const select = el("select"); select.id = "ticket-status";
  for (const value of ["open", "in_progress", "resolved"]) { const option = el("option", "", statusLabel(value)); option.value = value; select.append(option); }
  select.value = ticket.status;
  const notesLabel = el("label", "", "Operator notes"); notesLabel.htmlFor = "ticket-notes";
  const notes = el("textarea"); notes.id = "ticket-notes"; notes.rows = 4; notes.value = ticket.notes || ""; notes.maxLength = 4000; notes.placeholder = "Record the decision or the information you still need. A note is required to resolve a ticket.";
  const save = el("button", "primary", "Save ticket"); save.type = "submit";
  const status = el("span", "form-status"); status.setAttribute("role", "status");
  append(form, label, select, notesLabel, notes, append(el("div", "form-actions"), save, status));
  form.addEventListener("submit", async event => {
    event.preventDefault(); save.disabled = true; status.textContent = "Saving…"; status.className = "form-status";
    try {
      const updated = await api(`/api/tickets/${encodeURIComponent(ticket.id)}`, {method: "PATCH", body: JSON.stringify({status: select.value, notes: notes.value})});
      state.tickets = state.tickets.map(item => item.id === ticket.id ? updated : item);
      renderTicketList(); status.textContent = "Saved locally.";
      await refreshOverview();
    } catch (error) { status.textContent = error.message; status.className = "form-status error"; }
    finally { save.disabled = false; }
  });
  target.append(form, sectionHeading("Evidence preserved at handoff", "Original document versions"));
  const sources = Array.isArray(ticket.sources) ? ticket.sources : [];
  sources.forEach((source, index) => target.append(sourceCard(source, index)));
  if (!sources.length) target.append(el("p", "empty-detail-message", "No supporting sources were found for this question."));
}

async function loadTickets() {
  state.tickets = await api("/api/tickets");
  renderTicketList();
  const selected = state.tickets.find(ticket => ticket.id === state.selectedTicket);
  if (selected) renderTicket(selected);
  else if (state.tickets.length) { state.selectedTicket = state.tickets[0].id; renderTicketList(); renderTicket(state.tickets[0]); }
}

function renderDocumentList() {
  const target = $("#document-list"); target.replaceChildren();
  $("#knowledge-total").textContent = `${state.documents.length} documents`;
  if (!state.documents.length) target.append(el("p", "record-empty", "No documents are available."));
  for (const doc of state.documents) {
    const button = el("button", `record-button${state.selectedDocument === doc.id ? " selected" : ""}`);
    append(button, el("strong", "", doc.title), append(el("small"), tag(versionLabel(doc.version)), el("span", "", doc.id)));
    button.addEventListener("click", async () => { state.selectedDocument = doc.id; renderDocumentList(); await renderDocument(doc); });
    target.append(button);
  }
}

async function renderDocument(doc, message = "") {
  const target = $("#document-detail");
  target.replaceChildren(el("h2", "", doc.title), append(el("div", "detail-meta"), tag(versionLabel(doc.version)), el("span", "", doc.id), el("span", "", doc.updated_at ? `Updated ${dateLabel(doc.updated_at)}` : "")));
  const form = el("form");
  const textLabel = el("label", "", "Document text"); textLabel.htmlFor = "document-text";
  const text = el("textarea"); text.id = "document-text"; text.rows = 9; text.value = doc.text; text.required = true; text.minLength = 10; text.maxLength = 6000;
  const fields = el("div", "form-row");
  const factKeyLabel = el("label", "", "Policy fact key (optional)"); factKeyLabel.htmlFor = "fact-key";
  const factKey = el("input"); factKey.id = "fact-key"; factKey.value = doc.fact_key || ""; factKey.placeholder = "e.g. retention_days"; factKey.maxLength = 80; factKey.pattern = "[a-z0-9_]*"; factKey.title = "Use lowercase letters, numbers and underscores.";
  const factValueLabel = el("label", "", "Policy fact value (optional)"); factValueLabel.htmlFor = "fact-value";
  const factValue = el("input"); factValue.id = "fact-value"; factValue.value = doc.fact_value || ""; factValue.placeholder = "e.g. 30"; factValue.maxLength = 120;
  append(fields, append(el("div"), factKeyLabel, factKey), append(el("div"), factValueLabel, factValue));
  const save = el("button", "primary", "Save new version"); save.type = "submit";
  const status = el("span", "form-status", message); status.setAttribute("role", "status");
  append(form, textLabel, text, fields, el("p", "micro muted", "Matching fact keys with different values flag a policy conflict. Keep these fields consistent with the text."), append(el("div", "form-actions"), save, status));
  form.addEventListener("submit", async event => {
    event.preventDefault(); save.disabled = true; status.textContent = "Saving…"; status.className = "form-status";
    try {
      const updated = await api(`/api/documents/${encodeURIComponent(doc.id)}`, {method: "PUT", body: JSON.stringify({text: text.value, fact_key: factKey.value.trim(), fact_value: factValue.value.trim(), expected_version: doc.version})});
      state.documents = state.documents.map(item => item.id === doc.id ? updated : item);
      renderDocumentList(); await renderDocument(updated, `Saved ${versionLabel(updated.version)}. New questions use this version.`);
    } catch (error) { status.textContent = error.message; status.className = "form-status error"; save.disabled = false; }
  });
  target.append(form);
  const historyPanel = el("section", "history-list");
  historyPanel.append(el("h3", "", "Version history"), el("p", "micro muted", "Loading document versions…"));
  target.append(historyPanel);
  try {
    const history = await api(`/api/documents/${encodeURIComponent(doc.id)}/history`);
    if (state.selectedDocument !== doc.id || !historyPanel.isConnected) return;
    historyPanel.replaceChildren(el("h3", "", "Version history"));
    const revisions = Array.isArray(history) ? history : (history.revisions || []);
    for (const revision of revisions) {
      const detail = el("details");
      append(detail, el("summary", "", `${versionLabel(revision.version)}${revision.updated_at ? ` · ${dateLabel(revision.updated_at)}` : ""}`), el("div", "history-text", revision.text));
      historyPanel.append(detail);
    }
    if (!revisions.length) historyPanel.append(el("p", "micro muted", "No earlier versions are available."));
  } catch (error) { historyPanel.replaceChildren(el("h3", "", "Version history"), el("p", "form-status error", error.message)); }
}

async function loadDocuments() {
  state.documents = await api("/api/documents");
  if (!state.selectedDocument && state.documents.length) state.selectedDocument = state.documents[0].id;
  renderDocumentList();
  const selected = state.documents.find(doc => doc.id === state.selectedDocument);
  if (selected) await renderDocument(selected);
}

function renderNewDocument() {
  state.selectedDocument = null;
  renderDocumentList();
  const target = $("#document-detail");
  target.replaceChildren(el("h2", "", "New document"), el("p", "section-note", "Use a short, approved support policy. Split unrelated topics into separate documents."));
  const form = el("form");
  const inputs = {};
  const fields = [
    ["id", "Document ID", "input", "e.g. export-policy"],
    ["title", "Title", "input", "e.g. Data export policy"],
    ["text", "Document text", "textarea", "Write the policy in plain English."],
    ["fact_key", "Policy fact key (optional)", "input", "e.g. export_link_hours"],
    ["fact_value", "Policy fact value (optional)", "input", "e.g. 24"]
  ];
  for (const [name, labelText, type, placeholder] of fields) {
    const label = el("label", "", labelText); label.htmlFor = `new-${name}`;
    const input = el(type); input.id = `new-${name}`; input.placeholder = placeholder;
    input.required = ["id", "title", "text"].includes(name);
    input.maxLength = {id: 80, title: 160, text: 6000, fact_key: 80, fact_value: 120}[name];
    if (name === "id") { input.pattern = "[a-z0-9][a-z0-9\\-]*"; input.title = "Use lowercase letters, numbers and hyphens; start with a letter or number."; }
    if (name === "title") input.minLength = 3;
    if (name === "text") { input.rows = 7; input.minLength = 10; }
    if (name === "fact_key") { input.pattern = "[a-z0-9_]*"; input.title = "Use lowercase letters, numbers and underscores."; }
    inputs[name] = input;
    append(form, label, input);
  }
  append(form, el("p", "micro muted", "Optional fact fields flag conflicts between documents with the same key. The value must also appear in the text."));
  const save = el("button", "primary", "Add document"); save.type = "submit";
  const cancel = el("button", "secondary", "Cancel"); cancel.type = "button";
  cancel.addEventListener("click", () => navigate("knowledge"));
  const status = el("p", "form-status"); status.setAttribute("role", "status");
  append(form, append(el("div", "form-actions"), save, cancel), status);
  form.addEventListener("submit", async event => {
    event.preventDefault(); save.disabled = true; status.className = "form-status"; status.textContent = "Adding document…";
    try {
      const body = Object.fromEntries(Object.entries(inputs).map(([name, input]) => [name, input.value.trim()]));
      const created = await api("/api/documents", {method: "POST", body: JSON.stringify(body)});
      state.documents.push(created); state.selectedDocument = created.id;
      renderDocumentList(); await renderDocument(created, "Document added. New questions can use it."); await refreshOverview();
    } catch (error) { status.textContent = error.message; status.className = "form-status error"; save.disabled = false; }
  });
  target.append(form); inputs.id.focus();
}

async function navigate(view) {
  if (!["questions", "tickets", "knowledge"].includes(view)) view = "questions";
  state.view = view; clearError();
  $$(".view").forEach(node => node.classList.toggle("hidden", node.id !== `view-${view}`));
  $$("[data-view]").forEach(button => { button.classList.toggle("active", button.dataset.view === view); button.setAttribute("aria-current", button.dataset.view === view ? "page" : "false"); });
  $("#breadcrumb").textContent = {questions: "Questions", tickets: "Handoffs", knowledge: "Documents"}[view];
  history.replaceState(null, "", `#${view}`);
  try {
    if (view === "tickets") await loadTickets();
    if (view === "knowledge") await loadDocuments();
    await refreshOverview();
  } catch (error) { globalError(error); }
}

$$('[data-view]').forEach(button => button.addEventListener("click", () => navigate(button.dataset.view)));
$(".brand").addEventListener("click", event => { event.preventDefault(); navigate("questions"); });
$("#refresh-tickets").addEventListener("click", () => navigate("tickets"));
$("#refresh-documents").addEventListener("click", () => navigate("knowledge"));
$("#new-document").addEventListener("click", renderNewDocument);
window.addEventListener("hashchange", () => navigate(location.hash.slice(1)));
navigate(location.hash.slice(1) || "questions");
