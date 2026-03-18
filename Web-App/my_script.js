const BASE_URL = "http://127.0.0.1:5000/api/v1/indexer";

// ── DOM refs ──────────────────────────────────────────────────────
const userInput      = () => document.getElementById("UserInput").value.trim();
const resultsList    = document.getElementById("resultsList");
const resultsSection = document.getElementById("resultsSection");
const compareSection = document.getElementById("compareSection");
const expandedQuery  = document.getElementById("expandedQuery");
const searchBtn      = document.getElementById("searchBtn");

// ── Helpers ───────────────────────────────────────────────────────

function selectedType() {
  const checked = document.querySelector('input[name="type"]:checked');
  return checked ? checked.value : "page_rank";
}

function setLoading(on) {
  searchBtn.disabled = on;
  searchBtn.textContent = on ? "Searching…" : "Search";
  if (on) {
    resultsList.innerHTML = `
      <div class="state-msg">
        <div class="spinner"></div>
        Searching…
      </div>`;
    resultsSection.hidden = false;
  }
}

function renderResults(results, query) {
  expandedQuery.textContent = query ? `— expanded: "${query}"` : "";

  if (!results || results.length === 0) {
    resultsList.innerHTML = `<div class="state-msg">No results found. Try a different query.</div>`;
    return;
  }

  resultsList.innerHTML = results.map((r, i) => `
    <div class="result-card">
      <div class="result-rank">#${r.rank || i + 1}</div>
      <div class="result-title">
        <a href="${escHtml(r.url)}" target="_blank" rel="noopener">${escHtml(r.title) || "Untitled"}</a>
      </div>
      <div class="result-url">${escHtml(r.url)}</div>
      ${r.meta_info ? `<div class="result-snippet">${escHtml(r.meta_info)}</div>` : ""}
    </div>
  `).join("");
}

function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Main search ───────────────────────────────────────────────────

function search() {
  const raw = userInput();
  if (!raw) return;

  const query = "content:" + raw;
  const type  = selectedType();

  setLoading(true);

  $.get(BASE_URL, { query, type })
    .done(function (resp) {
      // For query-expansion types the backend returns the expanded query text;
      // for others it echoes back the display query (strip "content:" prefix).
      const displayQuery = (resp.query || "").replace(/^content:/, "");
      const isExpanded   = displayQuery.toLowerCase() !== raw.toLowerCase();

      renderResults(resp.results, isExpanded ? displayQuery : "");
      resultsSection.hidden = false;
    })
    .fail(function (xhr) {
      resultsList.innerHTML = `
        <div class="state-msg">
          Error: could not reach the backend (is <code>python3 app.py</code> running?)<br>
          <small>${xhr.status} ${xhr.statusText}</small>
        </div>`;
      resultsSection.hidden = false;
    })
    .always(function () {
      setLoading(false);
    });
}

// ── Google / Bing comparison ──────────────────────────────────────

function queryToGoogleBing() {
  const q = userInput();
  if (!q) return;
  document.getElementById("google").src = `https://www.google.com/search?igu=1&q=${encodeURIComponent(q)}`;
  document.getElementById("bing").src   = `https://www.bing.com/search?q=${encodeURIComponent(q)}`;
  compareSection.hidden = false;
}
