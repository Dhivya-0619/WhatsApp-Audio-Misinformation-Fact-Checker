let allClaims = [];
let selected = null;

function byId(id) {
  return document.getElementById(id);
}

async function fetchJson(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

function renderTable(claims) {
  const tbody = byId("claimsTbody");
  tbody.innerHTML = "";

  (claims || []).forEach((c) => {
    const tr = document.createElement("tr");
    tr.className = "border-b border-slate-800 hover:bg-slate-800/40 cursor-pointer";
    tr.addEventListener("click", () => openEditor(c));

    const cells = [
      { v: c.claim_text, cls: "p-3 text-slate-100 max-w-xl" },
      { v: c.language || "unknown", cls: "p-3 text-slate-200" },
      { v: c.verdict || "unknown", cls: "p-3" },
      { v: c.confidence ?? "—", cls: "p-3" },
      { v: c.virality_score ?? "—", cls: "p-3" },
      { v: c.disputed ? "yes" : "no", cls: "p-3" },
      { v: c.timestamp, cls: "p-3 text-slate-300" },
    ];

    cells.forEach((cell) => {
      const td = document.createElement("td");
      td.className = cell.cls;
      td.textContent = String(cell.v ?? "");
      tr.appendChild(td);
    });

    const tdActions = document.createElement("td");
    tdActions.className = "p-3 text-right";
    const btn = document.createElement("button");
    btn.className = "px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-xs";
    btn.textContent = "Edit";
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openEditor(c);
    });
    tdActions.appendChild(btn);
    tr.appendChild(tdActions);

    tbody.appendChild(tr);
  });
}

function openEditor(claim) {
  selected = claim;
  byId("editor").classList.remove("hidden");
  byId("editClaimText").textContent = `#${claim.id} — ${claim.claim_text}`;
  byId("editVerdict").value = (claim.verdict || "uncertain").toLowerCase();
  byId("editConfidence").value = claim.confidence ?? 50;
  byId("editExplanation").value = claim.explanation || "";
  byId("editSources").value = (claim.sources || []).join("\n");
  byId("editDisputed").checked = !!claim.disputed;
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

function closeEditor() {
  byId("editor").classList.add("hidden");
  selected = null;
}

async function loadClaims() {
  allClaims = await fetchJson("/claims");
  applyFilter();
}

function applyFilter() {
  const q = (byId("filterInput").value || "").trim().toLowerCase();
  if (!q) return renderTable(allClaims);
  const filtered = allClaims.filter((c) => {
    const hay = `${c.claim_text || ""} ${c.explanation || ""}`.toLowerCase();
    return hay.includes(q);
  });
  renderTable(filtered);
}

async function save() {
  if (!selected) return;
  const payload = {
    id: selected.id,
    verdict: byId("editVerdict").value,
    confidence: Number(byId("editConfidence").value || 0),
    explanation: byId("editExplanation").value,
    sources: (byId("editSources").value || "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
    disputed: byId("editDisputed").checked,
  };

  await fetchJson("/claims/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadClaims();
  closeEditor();
}

byId("reloadBtn").addEventListener("click", () => loadClaims().catch((e) => alert(e.message)));
byId("filterInput").addEventListener("input", () => applyFilter());
byId("closeEditorBtn").addEventListener("click", () => closeEditor());
byId("discardBtn").addEventListener("click", () => closeEditor());
byId("saveBtn").addEventListener("click", () => save().catch((e) => alert(e.message)));

loadClaims().catch((e) => {
  console.error(e);
  alert("Failed to load claims. Is the backend running on the same origin?");
});

