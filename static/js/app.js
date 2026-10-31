"use strict";

// ----- helper -------------------------------------------------------------
async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (res.status === 401) { window.location = "/login"; throw new Error("unauth"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || ("Errore " + res.status));
  return data;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function money(p, cur) { return Math.round(p) + " " + esc(cur || "EUR"); }

// ----- DASHBOARD (ricerca) ------------------------------------------------
function initDashboard() {
  const form = document.getElementById("searchForm");
  const mode = document.getElementById("mode");
  const results = document.getElementById("results");
  const status = document.getElementById("searchStatus");

  const show = (name, on) => {
    const el = document.querySelector('[data-field="' + name + '"]');
    if (el) el.hidden = !on;
  };
  const applyMode = () => {
    const m = mode.value;
    show("destination", m !== "explore");
    show("departDate", m === "search");
    show("returnDate", m === "search");
    show("adults", m === "search");
    show("maxPrice", m === "explore");
  };
  mode.addEventListener("change", applyMode);
  applyMode();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const origin = document.getElementById("origin").value.trim().toUpperCase();
    const dest = document.getElementById("destination").value.trim().toUpperCase();
    const m = mode.value;
    results.innerHTML = "";
    status.textContent = "Ricerca in corso…";
    try {
      let html = "";
      if (m === "search") {
        const q = new URLSearchParams({ origin, destination: dest,
          departDate: document.getElementById("departDate").value,
          adults: document.getElementById("adults").value });
        const rd = document.getElementById("returnDate").value;
        if (rd) q.set("returnDate", rd);
        const data = await api("GET", "/api/search?" + q.toString());
        html = (data.offers || []).map(offerCard).join("");
        status.textContent = (data.offers || []).length + " risultati · fonti: " + (data.providers || []).join(", ");
      } else if (m === "explore") {
        const q = new URLSearchParams({ origin });
        const mp = document.getElementById("maxPrice").value;
        if (mp) q.set("maxPrice", mp);
        const data = await api("GET", "/api/explore?" + q.toString());
        html = (data.destinations || []).map(destCard).join("");
        status.textContent = (data.destinations || []).length + " mete trovate";
      } else {
        const q = new URLSearchParams({ origin, destination: dest });
        const data = await api("GET", "/api/cheapest-dates?" + q.toString());
        html = (data.dates || []).map(dateCard).join("");
        status.textContent = (data.dates || []).length + " date trovate";
      }
      results.innerHTML = html || '<p class="text-muted">Nessun risultato. Con le chiavi API in ambiente di test la copertura è limitata.</p>';
    } catch (err) {
      status.textContent = "";
      results.innerHTML = '<div class="alert alert-danger">' + esc(err.message) + "</div>";
    }
  });
}

function sourceBadge(src) {
  if (!src) return "";
  const prov = esc(src.provider || "");
  const car = src.carrier ? " · " + esc(src.carrier) : "";
  return '<span class="badge text-bg-light badge-source">Fonte: ' + prov + car + "</span>";
}

function offerCard(o) {
  return '<div class="col-12 col-md-6 col-lg-4"><div class="card shadow-sm h-100"><div class="card-body">'
    + '<h5 class="card-title">' + esc(o.origin) + " → " + esc(o.destination) + "</h5>"
    + '<div class="price">' + money(o.price, o.currency) + "</div>"
    + '<div class="small text-muted mb-2">' + esc(o.depart_date)
    + (o.return_date ? " → " + esc(o.return_date) : "")
    + (o.stops != null ? " · " + o.stops + " scali" : "") + "</div>"
    + sourceBadge(o.source) + "</div></div></div>";
}

function destCard(d) {
  return '<div class="col-12 col-md-6 col-lg-4"><div class="card shadow-sm h-100"><div class="card-body">'
    + '<h5 class="card-title">' + esc(d.origin) + " → " + esc(d.destination) + "</h5>"
    + '<div class="price">da ' + money(d.price, d.currency) + "</div>"
    + '<div class="small text-muted mb-2">' + esc(d.depart_date || "")
    + (d.return_date ? " → " + esc(d.return_date) : "") + (d.indicative ? " · prezzo indicativo" : "") + "</div>"
    + sourceBadge(d.source) + "</div></div></div>";
}

function dateCard(d) {
  return '<div class="col-6 col-md-4 col-lg-3"><div class="card shadow-sm h-100"><div class="card-body">'
    + '<div class="fw-bold">' + esc(d.depart_date) + "</div>"
    + '<div class="price">' + money(d.price, d.currency) + "</div>"
    + sourceBadge(d.source) + "</div></div></div>";
}

// ----- ALERTS -------------------------------------------------------------
function initAlerts() {
  const list = document.getElementById("alertsList");
  const form = document.getElementById("alertForm");
  const errBox = document.getElementById("alertFormError");

  async function load() {
    const data = await api("GET", "/api/alerts");
    const rows = data.alerts || [];
    list.innerHTML = rows.length
      ? rows.map(alertCard).join("")
      : '<p class="text-muted">Nessun alert. Creane uno con “+ Nuovo alert”.</p>';
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errBox.textContent = "";
    const anywhere = document.getElementById("a_anywhere").checked;
    const body = {
      origin: document.getElementById("a_origin").value.trim().toUpperCase(),
      destination: anywhere ? "ANY" : document.getElementById("a_destination").value.trim().toUpperCase(),
      depart_from: document.getElementById("a_depart_from").value,
      depart_to: document.getElementById("a_depart_to").value || null,
      return_from: document.getElementById("a_return_from").value || null,
      strategy: document.getElementById("a_strategy").value,
      currency: (document.getElementById("a_currency").value || "EUR").toUpperCase(),
    };
    const tp = document.getElementById("a_target_price").value;
    if (tp) body.target_price = parseFloat(tp);
    try {
      await api("POST", "/api/alerts", body);
      form.reset();
      await load();
    } catch (err) { errBox.textContent = err.message; }
  });

  list.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = btn.dataset.id, action = btn.dataset.action;
    try {
      if (action === "delete") {
        if (!confirm("Eliminare questo alert?")) return;
        await api("DELETE", "/api/alerts/" + id);
      } else {
        await api("POST", "/api/alerts/" + id + "/" + action);
      }
      await load();
    } catch (err) { alert(err.message); }
  });

  load();
}

function alertCard(a) {
  const paused = a.status === "paused";
  const badge = paused
    ? '<span class="badge text-bg-secondary">Sospeso</span>'
    : '<span class="badge text-bg-success">Attivo</span>';
  const price = a.last_price != null
    ? '<div class="price">' + money(a.last_price, a.currency) + "</div>"
    : '<div class="text-muted small">prezzo non ancora rilevato</div>';
  const toggle = paused
    ? '<button class="btn btn-sm btn-outline-success" data-action="resume" data-id="' + a.id + '">Riprendi</button>'
    : '<button class="btn btn-sm btn-outline-secondary" data-action="suspend" data-id="' + a.id + '">Sospendi</button>';
  const target = a.target_price != null ? " · soglia " + money(a.target_price, a.currency) : "";
  return '<div class="col-12 col-md-6"><div class="card shadow-sm h-100 alert-card ' + (paused ? "status-paused" : "") + '">'
    + '<div class="card-body">'
    + '<div class="d-flex justify-content-between align-items-start">'
    + '<h5 class="card-title mb-1">' + esc(a.origin) + " → " + esc(a.destination) + "</h5>" + badge + "</div>"
    + '<div class="small text-muted mb-1">' + esc(a.depart_from)
    + (a.return_from ? " · ritorno " + esc(a.return_from) : "")
    + " · " + esc(a.strategy) + target + "</div>"
    + price
    + '<div class="d-flex gap-2 mt-3">' + toggle
    + '<button class="btn btn-sm btn-outline-danger" data-action="delete" data-id="' + a.id + '">Elimina</button>'
    + "</div></div></div></div>";
}

// ----- PREFERENCES --------------------------------------------------------
function initPreferences() {
  const form = document.getElementById("prefsForm");
  const msg = document.getElementById("prefsMsg");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.textContent = "";
    try {
      await api("PUT", "/api/me/preferences", {
        poll_interval_hours: parseInt(document.getElementById("p_interval").value, 10),
        currency: document.getElementById("p_currency").value.toUpperCase(),
        timezone: document.getElementById("p_timezone").value,
      });
      msg.className = "small mt-2 text-success";
      msg.textContent = "Preferenze salvate.";
    } catch (err) {
      msg.className = "small mt-2 text-danger";
      msg.textContent = err.message;
    }
  });
}

// ----- ADMIN --------------------------------------------------------------
function initAdmin() {
  const statsBox = document.getElementById("stats");
  const body = document.getElementById("usersBody");
  const isSuper = window.__IS_SUPERADMIN__ === true;

  async function loadStats() {
    const s = await api("GET", "/api/admin/stats");
    const tile = (t, v) => '<div class="col-6 col-md-3"><div class="card shadow-sm"><div class="card-body text-center">'
      + '<div class="h3 mb-0">' + esc(v) + "</div><div class=\"small text-muted\">" + esc(t) + "</div></div></div></div>";
    statsBox.innerHTML = tile("Utenti", s.users) + tile("Alert attivi", s.alerts_active)
      + tile("Email inviate", s.emails_sent)
      + tile("Ultimo run", s.last_run ? (s.last_run.status || "-") : "mai");
  }

  async function loadUsers() {
    const data = await api("GET", "/api/admin/users");
    body.innerHTML = (data.users || []).map(u => {
      let roleCell = esc(u.role);
      if (isSuper) {
        roleCell = '<select class="form-select form-select-sm" data-role-for="' + u.id + '">'
          + ["user", "admin", "superadmin"].map(r =>
            '<option value="' + r + '"' + (r === u.role ? " selected" : "") + ">" + r + "</option>").join("")
          + "</select>";
      }
      const act = u.status === "suspended"
        ? '<button class="btn btn-sm btn-outline-success" data-uaction="resume" data-id="' + u.id + '">Riattiva</button>'
        : '<button class="btn btn-sm btn-outline-secondary" data-uaction="suspend" data-id="' + u.id + '">Sospendi</button>';
      return "<tr><td>" + esc(u.email) + "</td><td>" + roleCell + "</td><td>" + esc(u.status)
        + '</td><td class="text-end">' + act + "</td></tr>";
    }).join("");
  }

  body.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-uaction]");
    if (!btn) return;
    try { await api("POST", "/api/admin/users/" + btn.dataset.id + "/" + btn.dataset.uaction); await loadUsers(); }
    catch (err) { alert(err.message); }
  });

  body.addEventListener("change", async (e) => {
    const sel = e.target.closest("select[data-role-for]");
    if (!sel) return;
    try { await api("PATCH", "/api/admin/users/" + sel.dataset.roleFor + "/role", { role: sel.value }); }
    catch (err) { alert(err.message); await loadUsers(); }
  });

  loadStats().catch(() => {});
  loadUsers().catch(() => {});
}

// ----- bootstrap ----------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  switch (window.__PAGE__) {
    case "dashboard": initDashboard(); break;
    case "alerts": initAlerts(); break;
    case "preferences": initPreferences(); break;
    case "admin": initAdmin(); break;
  }
});
