const $ = (s) => document.querySelector(s);
const api = (path, opts) => fetch(path, opts).then((r) => r.json());

// ---- navigation onglets ----
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    tab.classList.add("active");
    $("#view-" + tab.dataset.view).classList.add("active");
    if (tab.dataset.view === "settings") loadSettings();
  });
});

// ---- start / stop ----
$("#btn-start").addEventListener("click", async () => {
  $("#btn-start").disabled = true;
  await api("/api/agent/start", { method: "POST" });
  $("#btn-start").disabled = false;
  refresh();
});
$("#btn-stop").addEventListener("click", async () => {
  await api("/api/agent/stop", { method: "POST" });
  refresh();
});

// ---- helpers rendu ----
function fmtUsd(n) {
  if (!n) return "0";
  return "$" + Math.round(n).toLocaleString("en-US");
}

function coinHtml(c) {
  const age = c.age_minutes != null ? Math.round(c.age_minutes) + " min" : "?";
  let flags = "";
  if (c.is_known_dev) flags += ` <span class="flag-good">⭐ ${c.known_dev_label || "dev connu"}</span>`;
  if (c.top10_holder_pct) {
    const cls = c.top10_holder_pct > 50 ? "flag-warn" : "";
    flags += ` <span class="${cls}">top10 ${c.top10_holder_pct}%</span>`;
  }
  if (c.mint_authority) flags += ` <span class="flag-warn">⚠ mint authority</span>`;
  const link = c.dex_url ? ` · <a href="${c.dex_url}" target="_blank">DexScreener</a>` : "";
  return `<div class="coin">
    <div class="h"><span class="sym">${c.symbol || "?"}</span><span class="nm">${c.name || ""}</span></div>
    <div class="mint">${c.mint}</div>
    <div class="meta">Liq ${fmtUsd(c.liquidity_usd)} · FDV ${fmtUsd(c.fdv)} · âge ${age}${flags}${link}</div>
  </div>`;
}

function alertHtml(a) {
  const s = a.signal;
  const high = s.buzz_score >= 75 ? "high" : "";
  const tickers = (s.tickers || []).map((t) => `<span class="tick">$${t}</span>`).join("");
  const coins = (a.coins && a.coins.length)
    ? a.coins.map(coinHtml).join("")
    : `<div class="coin empty">Aucun coin correspondant trouvé.</div>`;
  const link = s.url ? `<a href="${s.url}" target="_blank">voir</a>` : "";
  return `<div class="card">
    <div class="top">
      <span class="score ${high}">${s.buzz_score}/100</span>
      <span class="src">${s.source} · @${s.author} · ${link}</span>
    </div>
    <div class="txt">${escapeHtml(s.text || "")}</div>
    ${s.reason ? `<div class="src">🧠 ${escapeHtml(s.reason)}</div>` : ""}
    ${tickers ? `<div class="tickers">${tickers}</div>` : ""}
    ${coins}
  </div>`;
}

function escapeHtml(t) {
  const d = document.createElement("div");
  d.textContent = t;
  return d.innerHTML;
}

// ---- état (flux + statut + logs) ----
async function refresh() {
  let state;
  try {
    state = await api("/api/state");
  } catch {
    return;
  }
  const st = state.status;
  $("#status-dot").className = "dot " + (st.running ? "on" : "off");
  $("#status-text").textContent = st.running ? "Actif" : "Arrêté";

  $("#stats").innerHTML = `
    <div class="stat"><div class="v">${st.signals_seen}</div><div class="k">signaux vus</div></div>
    <div class="stat"><div class="v">${st.alerts_count}</div><div class="k">alertes</div></div>
    <div class="stat"><div class="v">${st.analysis}</div><div class="k">analyse</div></div>
    <div class="stat"><div class="v">${st.source_status}</div><div class="k">source X</div></div>`;

  $("#alerts").innerHTML = state.alerts.length
    ? state.alerts.map(alertHtml).join("")
    : `<div class="empty">Aucune alerte pour l'instant. Démarre l'agent ou fais une recherche manuelle.</div>`;

  $("#logs").textContent = (state.logs || []).join("\n");
}

// ---- recherche manuelle ----
async function doScan() {
  const q = $("#scan-input").value.trim();
  if (!q) return;
  $("#scan-results").innerHTML = `<div class="empty">Recherche…</div>`;
  const res = await api("/api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: q }),
  });
  if (!res.coins || !res.coins.length) {
    $("#scan-results").innerHTML = `<div class="empty">Aucun coin trouvé pour « ${escapeHtml(q)} ».</div>`;
    return;
  }
  $("#scan-results").innerHTML = `<div class="card">
    <div class="top"><span class="src">${res.coins.length} coin(s) pour « ${escapeHtml(q)} » (du plus vieux / dev connu en premier)</span></div>
    ${res.coins.map(coinHtml).join("")}
  </div>`;
}
$("#btn-scan").addEventListener("click", doScan);
$("#scan-input").addEventListener("keydown", (e) => { if (e.key === "Enter") doScan(); });

// ---- réglages ----
async function loadSettings() {
  const s = await api("/api/settings");
  const f = $("#settings-form");
  f.x_queries.value = (s.x_queries || []).join("; ");
  f.anthropic_model.value = s.anthropic_model || "";
  f.poll_interval.value = s.poll_interval;
  f.min_buzz_score.value = s.min_buzz_score;
  f.min_liquidity_usd.value = s.min_liquidity_usd;
  f.known_devs.value = JSON.stringify(s.known_devs || { wallets: {}, handles: {} }, null, 2);
  // badges secrets
  [["x_accounts", s.x_accounts_is_set], ["helius_api_key", s.helius_api_key_is_set],
   ["anthropic_api_key", s.anthropic_api_key_is_set], ["discord_webhook_url", s.discord_webhook_url_is_set]]
    .forEach(([k, set]) => {
      const el = $("#" + k + "_set");
      if (el) { el.textContent = set ? "configuré ✓" : "non configuré"; el.className = "badge" + (set ? " set" : ""); }
    });
}

$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = {
    x_queries: f.x_queries.value.split(";").map((x) => x.trim()).filter(Boolean),
    anthropic_model: f.anthropic_model.value.trim(),
    poll_interval: parseInt(f.poll_interval.value) || 30,
    min_buzz_score: parseInt(f.min_buzz_score.value) || 55,
    min_liquidity_usd: parseFloat(f.min_liquidity_usd.value) || 0,
  };
  // secrets : uniquement si remplis
  ["x_accounts", "helius_api_key", "anthropic_api_key", "discord_webhook_url"].forEach((k) => {
    if (f[k].value.trim()) payload[k] = f[k].value.trim();
  });
  // devs connus (JSON)
  try {
    payload.known_devs = JSON.parse(f.known_devs.value || "{}");
  } catch {
    $("#save-msg").textContent = "JSON 'devs connus' invalide";
    $("#save-msg").style.color = "var(--danger)";
    return;
  }
  await api("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  $("#save-msg").style.color = "var(--accent)";
  $("#save-msg").textContent = "Enregistré ✓";
  setTimeout(() => ($("#save-msg").textContent = ""), 2500);
  loadSettings();
});

// ---- boucle de rafraichissement ----
refresh();
setInterval(refresh, 2500);
