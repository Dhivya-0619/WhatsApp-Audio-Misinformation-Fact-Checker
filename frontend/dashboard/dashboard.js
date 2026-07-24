let verdictChart;
let languageChart;
let categoryChart;

function byId(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  byId(id).textContent = value;
}

function toLabelsAndValues(obj) {
  const labels = Object.keys(obj || {});
  const values = labels.map((k) => obj[k] || 0);
  return { labels, values };
}

async function fetchJson(path) {
  const res = await fetch(path, { headers: { "Accept": "application/json" } });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return await res.json();
}

function renderTopViral(rows) {
  const tbody = byId("topViralTable");
  tbody.innerHTML = "";
  (rows || []).forEach((r) => {
    const tr = document.createElement("tr");
    tr.className = "border-t border-slate-800";

    const tdClaim = document.createElement("td");
    tdClaim.className = "py-2 pr-2 text-slate-100";
    tdClaim.textContent = r.claim_text || "";

    const tdScore = document.createElement("td");
    tdScore.className = "py-2 px-2 text-right text-indigo-300";
    tdScore.textContent = String(r.virality_score ?? "—");

    const tdOcc = document.createElement("td");
    tdOcc.className = "py-2 pl-2 text-right text-slate-200";
    tdOcc.textContent = String(r.occurrences ?? 0);

    tr.appendChild(tdClaim);
    tr.appendChild(tdScore);
    tr.appendChild(tdOcc);
    tbody.appendChild(tr);
  });
}

function makeOrUpdateChart(existing, ctx, type, labels, values, label, colors) {
  if (existing) {
    existing.data.labels = labels;
    existing.data.datasets[0].data = values;
    existing.update();
    return existing;
  }
  return new Chart(ctx, {
    type,
    data: {
      labels,
      datasets: [
        {
          label,
          data: values,
          backgroundColor: colors,
          borderColor: "rgba(148,163,184,0.25)",
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#cbd5e1" } },
      },
      scales: {
        x: { ticks: { color: "#cbd5e1" }, grid: { color: "rgba(148,163,184,0.1)" } },
        y: { ticks: { color: "#cbd5e1" }, grid: { color: "rgba(148,163,184,0.1)" } },
      },
    },
  });
}

async function refresh() {
  const stats = await fetchJson("/dashboard/stats");

  setText("totalMessages", stats.total_messages ?? 0);
  setText("falseCount", stats.false_vs_true?.false ?? 0);
  setText("trueCount", stats.false_vs_true?.true ?? 0);
  setText("uncertainCount", stats.false_vs_true?.uncertain ?? 0);

  const v = toLabelsAndValues(stats.verdict_counts);
  verdictChart = makeOrUpdateChart(
    verdictChart,
    byId("verdictChart"),
    "bar",
    v.labels,
    v.values,
    "Verdicts",
    ["#22c55e", "#f43f5e", "#fbbf24", "#94a3b8"]
  );

  const l = toLabelsAndValues(stats.language_distribution);
  languageChart = makeOrUpdateChart(
    languageChart,
    byId("languageChart"),
    "doughnut",
    l.labels,
    l.values,
    "Languages",
    ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#f87171", "#cbd5e1"]
  );

  const c = toLabelsAndValues(stats.trending_categories);
  categoryChart = makeOrUpdateChart(
    categoryChart,
    byId("categoryChart"),
    "bar",
    c.labels,
    c.values,
    "Categories",
    ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24"]
  );

  renderTopViral(stats.top_viral_claims || []);
}

byId("refreshBtn").addEventListener("click", () => refresh().catch((e) => alert(e.message)));

refresh().catch((e) => {
  console.error(e);
  alert("Failed to load dashboard stats. Is the backend running on the same origin?");
});

