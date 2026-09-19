/* HarborDesk: local, dependency-free UI. Untrusted content is inserted as text. */
"use strict";

const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
const state = {view: "questions", result: null, tickets: [], documents: [], selectedTicket: null, selectedDocument: null, asking: false};

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
  $("#ticket-count").textContent = data.open_tickets;
  $("#queue-count").textContent = data.open_tickets;
  $("#mode-label").textContent = data.mode === "ollama" ? "Local model mode" : "Evidence mode";
  $("#model-status").textContent = data.model_verified ? "Verified connection" : "Not verified";
}

function sourceCard(source, index) {
  const card = el("article", "source-card");
  const top = el("div", "source-top");
  append(top, el("span", "source-letter", source.source_id || `S${index + 1}`), el("h3", "", source.title || source.doc_id || "Source document"), el("span", "version", versionLabel(source.version)));
  append(card, top, el("blockquote", "", source.text || "No excerpt is available."));
  const footer = el("div", "source-footer");
  append(footer, el("span", "", source.doc_id || source.source_id || "Source"));
  if (source.score !== undefined && source.score !== null) {
    const score = Number(source.score);
    append(footer, el("span", "", `Ranking score ${Number.isFinite(score) ? score.toFixed(3) : source.score}`));
  }
  append(card, footer);
  return card;
}

function sectionHeading(title, note) {
  return append(el("div", "subheading"), el("span", "", title), note ? el("small", "", note) : null);
}

function renderResult(result) {
  const body = el("div", "result-body");
  const isEvidence = result.status === "evidence_found";
  const titles = {evidence_found: "Relevant evidence found", needs_review: "A person should review this", conflict: "The sources disagree", unsafe_request: "This request needs a safe handoff", model_quotes: "Model-selected quotations — review required", model_timeout: "Model timed out — evidence retained", model_budget_exhausted: "Model allowance reached", model_insufficient: "The model found insufficient evidence", model_rejected: "Model output withheld", model_error: "Model unavailable — evidence retained", model_unavailable: "Model unavailable — evidence retained", model_invalid: "Model answer needs review", model_unsupported: "Model answer could not be verified"};
  const banner = el("div", `result-banner${isEvidence ? "" : " warning"}`);
  append(banner, el("h2", "", `${isEvidence ? "✓" : "!"}  ${titles[result.status] || "Review required"}`), el("p", "", result.reason || "Review the original sources before responding to your customer."));
  const meta = el("div", "result-meta");
  append(meta, tag(result.mode === "ollama" ? "Local model requested" : "No model called"), el("span", "", result.revision_label || "Current document versions"));
  append(banner, meta);
  append(body, banner, el("p", "result-question", `Question: ${result.question}`));
  if (result.generated_answer) {
    append(body, sectionHeading("Model-selected answer", "Review against the sources below"), el("div", "generated-answer", result.generated_answer), el("p", "model-disclaimer", "The model selects source quotations. Exact matching does not prove relevance; review before responding."));
  } else {
    append(body, el("p", "micro muted", result.mode === "ollama" ? "No verified model answer is displayed. Retrieved text remains available for review." : "Source excerpts only. No generated answer or resolution is implied."));
  }
  if (Array.isArray(result.conflicts) && result.conflicts.length) {
    append(body, sectionHeading("Conflicting policy facts"));
    for (const conflict of result.conflicts) append(body, el("div", "conflict-line", `${conflict.key}: ${(conflict.values || []).map(value => typeof value === "object" ? JSON.stringify(value) : value).join(" ↔ ")}`));
  }
  if (!result.generated_answer && Array.isArray(result.claims) && result.claims.length) {
    append(body, sectionHeading("Extracted evidence", "Check the cited passage"));
    for (const claim of result.claims) {
      const quote = el("div", "evidence-claim");
      append(quote, el("span", "", claim.text), tag(claim.source_id || "Source"));
      append(body, quote);
    }
  }
  const retrieval = Array.isArray(result.retrieval) ? result.retrieval : [];
  append(body, sectionHeading(`Retrieved documents (${retrieval.length})`, "Ranking scores are not confidence"));
  if (retrieval.length) retrieval.forEach((source, index) => body.append(sourceCard(source, index)));
  else append(body, el("p", "empty-detail-message", "No supporting passage is available for this question. Pass it to an operator instead of guessing."));
  const handoff = el("div", "handoff-bar");
  const explanation = append(el("p"), el("strong", "", isEvidence ? "Need a second look?" : "Keep the question moving."), el("span", "", "Save the question and its evidence in the local queue."));
  const button = el("button", "secondary", "Create local handoff  ↗");
  button.type = "button";
  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Creating handoff…";
    try {
      const ticket = await api("/api/tickets", {method: "POST", body: JSON.stringify({query_id: result.id})});
      button.textContent = "Open handoff  ↗";
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
  button.textContent = "Finding evidence…";
  $("#response-time").textContent = "";
  setLoading($("#response-content"), "Searching the current document versions…");
  try {
    state.result = await api("/api/ask", {method: "POST", body: JSON.stringify({question})});
    renderResult(state.result);
  } catch (error) {
    const message = append(el("div", "result-body"), el("div", "notice error", error.message), el("p", "muted", "No answer was produced. Your question is still in the editor; try again when the service is available."));
    $("#response-content").replaceChildren(message);
  } finally {
    state.asking = false;
    $$("[data-question]").forEach(item => { item.disabled = false; });
    button.disabled = false;
    button.replaceChildren(el("span", "", "Find supporting evidence"), el("span", "", "↗"));
    button.firstChild.style.marginLeft = "0";
    button.firstChild.style.fontSize = "inherit";
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

async function navigate(view) {
  if (!["questions", "tickets", "knowledge"].includes(view)) view = "questions";
  state.view = view; clearError();
  $$(".view").forEach(node => node.classList.toggle("hidden", node.id !== `view-${view}`));
  $$("[data-view]").forEach(button => { button.classList.toggle("active", button.dataset.view === view); button.setAttribute("aria-current", button.dataset.view === view ? "page" : "false"); });
  $("#breadcrumb").textContent = {questions: "Questions", tickets: "Handoff queue", knowledge: "Knowledge"}[view];
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
window.addEventListener("hashchange", () => navigate(location.hash.slice(1)));
navigate(location.hash.slice(1) || "questions");
