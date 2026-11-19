// SeniorVoice portal UI. Every view is fetched live from the device through
// the portal server; nothing is kept in the browser beyond the open page.
"use strict";

const $ = (id) => document.getElementById(id);
const ROLE_LABEL = { angehoerige: "Angehörige", spitex: "Spitex", admin: "Admin (nur Technik)" };
const KIND_LABEL = { termin: "Termin", medikament: "Medikament" };
const STATUS_LABEL = { geplant: "geplant", klingelt: "klingelt", bestaetigt: "bestätigt",
  verpasst: "verpasst", offen: "offen", quittiert: "erledigt", "niemand erreicht": "niemand erreicht" };
const REFRESH_MS = 15000;

let me = null;
let devices = [];
let current = null;     // selected device
let tab = null;
let timer = null;

// --- helpers ---

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => t.classList.remove("show"), 3500);
}

async function api(method, path, body) {
  const opts = { method, headers: { "X-Portal": "1" }, credentials: "same-origin" };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let resp;
  try {
    resp = await fetch(path, opts);
  } catch (e) {
    return { status: 0, data: { error: "Portal nicht erreichbar" } };
  }
  let data = {};
  try { data = await resp.json(); } catch (e) { /* empty */ }
  if (resp.status === 401 && path !== "/api/login") showLogin("Bitte neu anmelden.");
  return { status: resp.status, data };
}

const WEEKDAY = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
function fmtLocal(s) {          // "2026-11-24 14:30" (device local time)
  const m = /^(\d{4})-(\d\d)-(\d\d) (\d\d:\d\d)$/.exec(s || "");
  if (!m) return s || "";
  const d = new Date(+m[1], +m[2] - 1, +m[3]);
  return `${WEEKDAY[d.getDay()]} ${m[3]}.${m[2]}. ${m[4]}`;
}
function fmtIso(s) {            // UTC ISO from the device or the portal
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d)) return s;
  return d.toLocaleString("de-CH", { weekday: "short", day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit" });
}
function since(s) {
  if (!s) return "noch nie erreicht";
  return "zuletzt erreicht " + fmtIso(s);
}
function chip(status) {
  const cls = status === "niemand erreicht" ? "niemand" : status;
  return el("span", { class: `status st-${cls}` }, STATUS_LABEL[status] || status);
}
function errText(r) {
  if (r.status === 503) return "Gerät offline – " + since(r.data.last_seen);
  if (r.status === 403) return "Kein Zugriff: " + (r.data.error || "nicht freigegeben");
  return r.data.error || `Fehler ${r.status}`;
}

// --- login ---

function showLogin(message) {
  stopTimer();
  me = null; current = null;
  $("main-view").hidden = true;
  $("who").hidden = true;
  $("logout").hidden = true;
  $("login-view").hidden = false;
  $("login-err").textContent = message || "";
  $("l-login").focus();
}

$("login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("login-err").textContent = "";
  const r = await api("POST", "/api/login", {
    login: $("l-login").value.trim(), password: $("l-pass").value, code: $("l-code").value.trim() });
  $("l-pass").value = ""; $("l-code").value = "";
  if (r.status !== 200) {
    $("login-err").textContent = r.status === 401
      ? "Anmeldung fehlgeschlagen. Nach 5 Fehlversuchen ist das Konto 5 Minuten gesperrt."
      : (r.data.error || "Anmeldung nicht möglich");
    return;
  }
  start(r.data);
});

$("logout").addEventListener("click", async () => {
  await api("POST", "/api/logout");
  showLogin("Abgemeldet.");
});

async function start(account) {
  me = account;
  $("login-view").hidden = true;
  $("main-view").hidden = false;
  $("who").hidden = false;
  $("who").textContent = `${me.name} · ${ROLE_LABEL[me.role] || me.role}`;
  $("logout").hidden = false;
  await loadDevices();
}

// --- devices ---

$("reload-devices").addEventListener("click", () => loadDevices());

async function loadDevices() {
  const box = $("devices");
  box.replaceChildren(el("p", { class: "muted" }, el("span", { class: "spinner" }), "Geräte werden abgefragt …"));
  const r = await api("GET", "/api/devices");
  if (r.status !== 200) { box.replaceChildren(el("p", { class: "err" }, errText(r))); return; }
  devices = r.data.devices;
  $("devices-title").textContent = me.role === "spitex" ? "Klientinnen und Klienten"
    : me.role === "admin" ? "Alle Geräte" : "Gerät";
  if (!devices.length) {
    box.replaceChildren(el("p", { class: "empty" }, "Diesem Konto ist noch kein Gerät zugeordnet."));
    return;
  }
  box.replaceChildren(...devices.map((d) => el("button", {
    type: "button", class: "person", "aria-pressed": current && current.id === d.id ? "true" : "false",
    onclick: () => openDevice(d.id) },
    el("b", {}, d.senior_name),
    el("span", { class: "small muted" }, d.label), el("br"),
    el("span", { class: "small" }, el("span", { class: `dot ${d.online ? "on" : "off"}` }),
      d.online ? "online" : d.no_access ? "kein Zugriff (Token oder Freigabe am Gerät prüfen)" : "offline – " + since(d.last_seen)))));
  $("devices-area").hidden = me.role === "angehoerige" && devices.length === 1;
  if (current) openDevice(current.id, tab);
  else if (devices.length === 1) openDevice(devices[0].id);
}

function tabsFor(role) {
  if (role === "admin") return [["technik", "Technik"], ["audit", "Zugriffsprotokoll"], ["logins", "Anmeldungen Portal"]];
  return [["termine", "Termine"], ["hilfe", "Hilfe-Verlauf"], ["rat", "Rat-Infos"], ["audit", "Zugriffsprotokoll"]];
}

function openDevice(id, wanted) {
  current = devices.find((d) => d.id === id);
  if (!current) return;
  for (const b of $("devices").querySelectorAll(".person")) b.setAttribute("aria-pressed", "false");
  const idx = devices.indexOf(current);
  const btn = $("devices").querySelectorAll(".person")[idx];
  if (btn) btn.setAttribute("aria-pressed", "true");
  $("device-view").hidden = false;
  $("dv-name").textContent = current.senior_name;
  $("dv-state").replaceChildren(el("span", { class: `status st-${current.online ? "online" : "offline"}` },
    current.online ? "online" : "offline"));
  const tabs = tabsFor(me.role);
  $("tabs").replaceChildren(...tabs.map(([key, label]) => el("button", {
    type: "button", role: "tab", "data-tab": key, onclick: () => showTab(key) }, label)));
  showTab(wanted && tabs.some(([k]) => k === wanted) ? wanted : tabs[0][0]);
}

function showTab(key) {
  tab = key;
  for (const b of $("tabs").children) b.setAttribute("aria-selected", b.dataset.tab === key ? "true" : "false");
  stopTimer();
  const render = { termine: renderTermine, hilfe: renderHilfe, rat: renderRat, audit: renderAudit,
    technik: renderTechnik, logins: renderLogins }[key];
  $("panel").replaceChildren(el("p", { class: "muted" }, el("span", { class: "spinner" }), "Wird live vom Gerät geladen …"));
  render();
  if (key === "termine" || key === "hilfe" || key === "technik") {
    timer = setInterval(() => { if (document.visibilityState === "visible") render(true); }, REFRESH_MS);
  }
}
function stopTimer() { if (timer) clearInterval(timer); timer = null; }

function stamp() {
  $("dv-live").textContent = "Live vom Gerät geladen um " +
    new Date().toLocaleTimeString("de-CH", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function dev(path) { return `/api/devices/${current.id}${path}`; }

async function load(path, refresh) {
  const r = await api("GET", dev(path));
  if (r.status === 200) { stamp(); return r.data; }
  if (!refresh || r.status !== 503) $("panel").replaceChildren(el("div", { class: "note warn" }, errText(r)));
  else $("dv-live").textContent = errText(r);
  return null;
}

// --- Termine ---

function pad(n) { return String(n).padStart(2, "0"); }

function termForm() {
  const now = new Date(Date.now() + 3 * 60000);
  const date = el("input", { type: "date", id: "t-date", required: true,
    value: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}` });
  const time = el("input", { type: "time", id: "t-time", required: true,
    value: `${pad(now.getHours())}:${pad(now.getMinutes())}` });
  const title = el("input", { type: "text", id: "t-title", maxlength: "120", required: true,
    placeholder: "z.B. Arzttermin Dr. Meier" });
  const kind = el("select", { id: "t-kind" }, el("option", { value: "termin" }, "Termin"),
    el("option", { value: "medikament" }, "Medikament"));
  const pre = el("select", { id: "t-pre" }, el("option", { value: "" }, "keine"),
    ...[15, 30, 60, 120].map((m) => el("option", { value: String(m) }, `${m} Minuten vorher`)));
  const err = el("p", { class: "err", role: "alert" });
  const form = el("form", { class: "editor" },
    el("h3", {}, "Neuer Eintrag"),
    el("div", { class: "fields" },
      el("div", { class: "field full" }, el("label", { for: "t-title" }, "Was"), title),
      el("div", { class: "field" }, el("label", { for: "t-kind" }, "Art"), kind),
      el("div", { class: "field" }, el("label", { for: "t-date" }, "Datum"), date),
      el("div", { class: "field" }, el("label", { for: "t-time" }, "Uhrzeit"), time),
      el("div", { class: "field" }, el("label", { for: "t-pre" }, "Vorerinnerung"), pre)),
    el("p", { class: "hint" }, "Das Telefon klingelt zur eingetragenen Zeit und sagt den Eintrag an."),
    err, el("button", { class: "btn", type: "submit" }, "Eintragen"));
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    err.textContent = "";
    const body = { title: title.value.trim(), kind: kind.value, due_local: `${date.value} ${time.value}` };
    if (pre.value) body.pre_minutes = Number(pre.value);
    const r = await api("POST", dev("/v1/appointments"), body);
    if (r.status === 201) { toast("Eingetragen – das Gerät erinnert zur Zeit."); renderTermine(); }
    else err.textContent = errText(r);
  });
  return form;
}

async function renderTermine(refresh) {
  const data = await load("/v1/appointments", refresh);
  if (!data) return;
  const items = data.appointments;
  const list = el("ul", { class: "list" }, ...items.map((a) => {
    const last = a.reminders[a.reminders.length - 1];
    return el("li", { class: "item" },
      el("div", { class: "when" }, fmtLocal(a.due_local), el("small", {}, KIND_LABEL[a.kind] || a.kind)),
      el("div", { class: "what" }, el("b", {}, a.title),
        el("span", { class: "src" }, "eingetragen von ", a.created_by),
        ...a.reminders.map((r) => el("span", { class: "src" },
          r.stage === "pre" ? "Vorerinnerung " : "Erinnerung ", fmtLocal(r.due_local), ": ",
          STATUS_LABEL[r.status] || r.status, r.attempts > 1 ? ` (${r.attempts} Versuche)` : ""))),
      el("div", { class: "side" }, last ? chip(last.status) : null,
        a.own ? el("div", { class: "actions" }, el("button", { type: "button", class: "btn danger sm",
          onclick: async () => {
            if (!window.confirm(`«${a.title}» löschen?`)) return;
            const r = await api("DELETE", dev(`/v1/appointments/${a.id}`));
            if (r.status === 200) { toast("Gelöscht."); renderTermine(); } else toast(errText(r));
          } }, "Löschen")) : el("span", { class: "small muted" }, "nur Ersteller/in kann ändern")));
  }));
  const card = el("div", { class: "card", id: "termine-list" },
    el("h3", {}, "Termine und Medikamente"),
    items.length ? list : el("p", { class: "empty" }, "Keine Einträge."),
    el("p", { class: "small muted" }, "«bestätigt» heisst: abgehoben und gehört. «verpasst»: zwei Versuche im Abstand von 10 Minuten ohne Abheben."));
  const old = $("termine-list");
  if (refresh && old) old.replaceWith(card);          // keep the form and what is typed in it
  else $("panel").replaceChildren(termForm(), card);
}

// --- Hilfe ---

async function renderHilfe(refresh) {
  const data = await load("/v1/help", refresh);
  if (!data) return;
  const rows = data.alerts.map((a) => el("tr", {},
    el("td", {}, fmtIso(a.created_at)), el("td", {}, chip(a.status)),
    el("td", {}, a.delivered ? "zugestellt" : "nicht zugestellt"),
    el("td", {}, a.acknowledged_by || "–")));
  $("panel").replaceChildren(el("div", { class: "card" }, el("h3", {}, "Hilfe-Verlauf"),
    data.alerts.length ? el("div", { class: "tbl-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", {}, "Wann"), el("th", {}, "Status"), el("th", {}, "Meldung"), el("th", {}, "Gekümmert hat sich"))),
      el("tbody", {}, rows))) : el("p", { class: "empty" }, "Keine Hilfe-Meldungen."),
    el("p", { class: "privacy" }, "Der Hilfe-Knopf meldet sich direkt bei der Kontaktperson. Das Portal ist kein Notruf und zeigt nur den Verlauf.")));
}

// --- Rat ---

async function renderRat() {
  const data = await load("/v1/advice");
  if (!data) return;
  const topic = el("input", { type: "text", id: "r-topic", maxlength: "60", required: true, placeholder: "z.B. Blutdruck" });
  const text = el("textarea", { id: "r-text", maxlength: "600", required: true,
    placeholder: "Wird am Telefon wörtlich vorgelesen." });
  const err = el("p", { class: "err", role: "alert" });
  const form = el("form", { class: "editor" }, el("h3", {}, "Neue Rat-Info"),
    el("div", { class: "fields" },
      el("div", { class: "field" }, el("label", { for: "r-topic" }, "Thema"), topic),
      el("div", { class: "field full" }, el("label", { for: "r-text" }, "Text"), text)),
    err, el("button", { class: "btn", type: "submit" }, "Speichern"));
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const r = await api("POST", dev("/v1/advice"), { topic: topic.value.trim(), text: text.value.trim() });
    if (r.status === 201) { toast("Gespeichert."); renderRat(); } else err.textContent = errText(r);
  });
  const list = el("ul", { class: "list" }, ...data.advice.map((i) => el("li", { class: "item" },
    el("div", { class: "when" }, i.topic),
    el("div", { class: "what" }, el("span", {}, i.text), el("span", { class: "src" }, "von ", i.created_by)),
    el("div", { class: "side" }, i.own ? el("button", { type: "button", class: "btn danger sm", onclick: async () => {
      if (!window.confirm(`«${i.topic}» löschen?`)) return;
      const r = await api("DELETE", dev(`/v1/advice/${i.id}`));
      if (r.status === 200) { toast("Gelöscht."); renderRat(); } else toast(errText(r));
    } }, "Löschen") : null))));
  $("panel").replaceChildren(form, el("div", { class: "card" }, el("h3", {}, "Rat-Infos auf dem Gerät"),
    data.advice.length ? list : el("p", { class: "empty" }, "Noch keine Rat-Infos.")));
}

// --- Zugriffsprotokoll ---
// The device stores each request as "METHOD /path" plus the HTTP status
// (pipeline/device_api.py, unchanged). Here it is put into plain German;
// unknown actions stay visible as they are, so nothing is hidden.

const AUDIT_ACTION = {
  "GET /v1/status": "Prüfen, ob das Gerät erreichbar ist",
  "GET /v1/appointments": "Termine und Medikamente ansehen",
  "POST /v1/appointments": "Termin oder Medikament eintragen",
  "PUT /v1/appointments/{id}": "Termin oder Medikament ändern",
  "DELETE /v1/appointments/{id}": "Termin oder Medikament löschen",
  "GET /v1/help": "Hilfe-Verlauf ansehen",
  "GET /v1/advice": "Rat-Infos ansehen",
  "POST /v1/advice": "Rat-Info eintragen",
  "PUT /v1/advice/{id}": "Rat-Info ändern",
  "DELETE /v1/advice/{id}": "Rat-Info löschen",
  "GET /v1/audit": "Zugriffsprotokoll ansehen",
  "GET /v1/health": "Technik-Ansicht ansehen",
};
const AUDIT_GROUP_GAP_MS = 5 * 60000;   // repeated automatic refreshes become one row

function auditWhat(e) {
  const known = AUDIT_ACTION[e.action];
  if (!known) {
    const unknown = /\(unknown\)$/.test(e.action || "");
    return unknown ? "Unbekannte Anfrage" : (e.action || "Unbekannte Anfrage");
  }
  return e.target ? `${known} (Eintrag Nr. ${e.target})` : known;
}
function auditResult(code) {
  if (code >= 200 && code < 300) return ["ok", "erledigt"];
  if (code === 403) return ["bad", "abgelehnt: keine Berechtigung"];
  if (code === 404) return ["bad", "nicht gefunden"];
  if (code >= 400 && code < 500) return ["bad", "abgelehnt: ungültige Eingabe"];
  return ["bad", "Fehler am Gerät"];
}
function auditWho(e) { return me && e.person_id === me.login ? "Sie" : e.person_id; }
function hhmm(s) {
  const d = new Date(s);
  return isNaN(d) ? "" : d.toLocaleTimeString("de-CH", { hour: "2-digit", minute: "2-digit" });
}
// Entries come newest first. Consecutive identical requests (same person,
// action, target, result) less than 5 minutes apart are shown as one row.
function groupAudit(entries) {
  const groups = [];
  for (const e of entries) {
    const g = groups[groups.length - 1];
    const t = new Date(e.at).getTime();
    if (g && g.person_id === e.person_id && g.action === e.action && g.target === e.target
        && g.result === e.result && g.oldestMs - t <= AUDIT_GROUP_GAP_MS) {
      g.count += 1; g.oldest = e.at; g.oldestMs = t;
    } else {
      groups.push({ ...e, count: 1, newest: e.at, oldest: e.at, oldestMs: t });
    }
  }
  return groups;
}

async function renderAudit() {
  const data = await load("/v1/audit");
  if (!data) return;
  const admin = me.role === "admin";
  const rows = groupAudit(data.entries).map((g) => {
    const [cls, label] = auditResult(g.result);
    const when = g.count > 1 ? `${fmtIso(g.oldest)} – ${hhmm(g.newest)}` : fmtIso(g.newest);
    return el("tr", {},
      el("td", {}, when),
      el("td", {}, auditWho(g)),
      el("td", {}, auditWhat(g),
        g.count > 1 ? el("span", { class: "src" }, `${g.count} Abrufe hintereinander`) : null,
        admin ? el("span", { class: "src mono" }, `${g.action}${g.target ? " #" + g.target : ""} → ${g.result}`) : null),
      el("td", {}, el("span", { class: `status st-audit-${cls}` }, label)));
  });
  $("panel").replaceChildren(el("div", { class: "card" }, el("h3", {}, "Zugriffsprotokoll des Geräts"),
    el("p", { class: "small muted" }, admin
      ? "Wer wann über das Portal auf dieses Gerät zugegriffen hat (30 Tage). Inhalte werden nicht protokolliert."
      : "Wann Sie über das Portal auf dieses Gerät zugegriffen haben (30 Tage). Inhalte werden nicht protokolliert."),
    data.entries.length ? el("div", { class: "tbl-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ...["Wann", "Wer", "Was", "Ergebnis"].map((h) => el("th", {}, h)))),
      el("tbody", {}, rows))) : el("p", { class: "empty" }, "Keine Einträge."),
    el("p", { class: "small muted" }, "Offene Seiten wie «Termine» laden alle 15 Sekunden neu. Solche Wiederholungen sind zu einer Zeile zusammengefasst.")));
}

async function renderLogins() {
  const r = await api("GET", "/api/logins");
  if (r.status !== 200) { $("panel").replaceChildren(el("div", { class: "note warn" }, errText(r))); return; }
  const rows = r.data.entries.map((e) => el("tr", {}, el("td", {}, fmtIso(e.at)), el("td", {}, e.login), el("td", {}, e.result)));
  $("panel").replaceChildren(el("div", { class: "card" }, el("h3", {}, "Anmeldungen am Portal (30 Tage)"),
    el("div", { class: "tbl-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", {}, "Wann"), el("th", {}, "Login"), el("th", {}, "Ergebnis"))),
      el("tbody", {}, rows)))));
}

// --- Technik (admin) ---

function kpi(label, value, sub, state) {
  return el("div", { class: `kpi ${state || ""}` }, el("div", { class: "n" }, value),
    el("div", { class: "l" }, label), sub ? el("div", { class: "s" }, sub) : null);
}
function dur(s) {
  if (s === null || s === undefined) return "–";
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d ? `${d} T ${h} h` : h ? `${h} h ${m} min` : `${m} min`;
}
function ms(v) { return v === null || v === undefined ? "–" : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${v} ms`; }

const SVG = "http://www.w3.org/2000/svg";
function svg(tag, attrs, text) {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}

function latencyChart(days, target) {
  const rows = days.slice().reverse();            // oldest first
  const W = 640, H = 240, L = 48, B = 28, T = 12, R = 8;
  const top = Math.max(target * 1.25, ...rows.map((d) => d.answer_ms.p95 || 0));
  const step = top > 8000 ? 2000 : 1000;
  const max = Math.ceil(top / step) * step;
  const y = (v) => T + (H - T - B) * (1 - v / max);
  const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img",
    "aria-label": "Antwortzeit pro Tag, Median und 95 %, Ziel 3 Sekunden" });
  for (let v = 0; v <= max; v += step) {
    chart.append(svg("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "grid" }),
      svg("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" }, `${v / 1000} s`));
  }
  const slot = (W - L - R) / Math.max(rows.length, 1);
  const bw = Math.min(22, slot / 3);
  rows.forEach((d, i) => {
    const x = L + slot * i + slot / 2;
    const p50 = d.answer_ms.p50, p95 = d.answer_ms.p95;
    if (p95 !== null && p95 !== undefined) {
      const r = svg("rect", { x: x, y: y(p95), width: bw, height: y(0) - y(p95), class: "p95", rx: 3 });
      r.append(svg("title", {}, `${d.date}: 95 % ${ms(p95)}`));
      chart.append(r);
    }
    if (p50 !== null && p50 !== undefined) {
      const r = svg("rect", { x: x - bw, y: y(p50), width: bw, height: y(0) - y(p50), class: "p50", rx: 3 });
      r.append(svg("title", {}, `${d.date}: Median ${ms(p50)}`));
      chart.append(r);
    }
    chart.append(svg("text", { x: x, y: H - 8, "text-anchor": "middle" }, d.date.slice(8, 10) + "." + d.date.slice(5, 7) + "."));
  });
  chart.append(svg("line", { x1: L, x2: W - R, y1: y(target), y2: y(target), class: "target" }));
  return el("div", {}, chart, el("div", { class: "legend" },
    el("span", {}, el("i", { class: "l50" }), "Median"), el("span", {}, el("i", { class: "l95" }), "95 %"),
    el("span", {}, el("i", { class: "lt" }), `Ziel ${target / 1000} s`)));
}

const CHANNEL_LABEL = { ConsoleChannel: "Testkanal (Anzeige auf der Telefon-Seite)", EmailChannel: "E-Mail", TelegramChannel: "Telegram" };
const DIALOG_LABEL = { bereit: "bereit", laedt: "lädt", neustart: "startet neu", aus: "aus" };

async function renderTechnik(refresh) {
  const h = await load("/v1/health", refresh);
  if (!h) return;
  const dv = h.device, core = h.services.core, ai = h.ai;
  const days = h.daily || [];
  const today = days[0] || null;
  const turns7 = days.reduce((s, d) => s + d.turns, 0);
  const errors7 = days.reduce((s, d) => s + Object.values(d.errors || {}).reduce((a, b) => a + b, 0), 0);
  const restarts7 = days.reduce((s, d) => s + ((d.events || {}).dialog_restart || 0), 0);
  const p95 = today ? today.answer_ms.p95 : null;
  const aiOk = ai.on_device ? ai.reachable && ai.model_installed : null;
  const memPct = dv.memory_mb.total ? Math.round(100 * (1 - dv.memory_mb.available / dv.memory_mb.total)) : null;

  const tiles = el("div", { class: "kpis" },
    kpi("Kern", core.running ? "läuft" : "aus", core.input === "web" ? "Simulation (Telefon-Seite)" : core.input === "gpio" ? "Telefon (GPIO)" : core.input || "",
      core.running ? "ok" : "bad"),
    kpi("Gesprächsteil", DIALOG_LABEL[core.dialog] || core.dialog || "–",
      core.dialog_restarts ? `${core.dialog_restarts} Neustarts seit Start` : "keine Neustarts",
      core.dialog === "bereit" ? "ok" : core.dialog === "aus" ? "bad" : "warn"),
    kpi("Sprachmodell", aiOk === null ? "extern" : aiOk ? "bereit" : ai.reachable ? "Modell fehlt" : "nicht erreichbar",
      `${ai.model}${ai.on_device ? " · auf dem Gerät" : ""}`, aiOk ? "ok" : "bad"),
    kpi("Antwortzeit heute (95 %)", ms(p95), today ? `Median ${ms(today.answer_ms.p50)} · ${today.turns} Antworten` : "heute noch keine",
      p95 === null ? "" : p95 <= h.latency_target_ms ? "ok" : "warn"),
    kpi("Fehler 7 Tage", String(errors7), `${turns7} Antworten · ${restarts7} Neustarts`, errors7 ? "warn" : "ok"),
    kpi("Temperatur", dv.cpu_temp_c === null ? "–" : `${dv.cpu_temp_c} °C`, dv.load ? `Last ${dv.load.join(" / ")}` : "",
      dv.cpu_temp_c === null ? "" : dv.cpu_temp_c < 70 ? "ok" : dv.cpu_temp_c < 80 ? "warn" : "bad"),
    kpi("Speicher", memPct === null ? "–" : `${memPct} %`, dv.memory_mb.total ? `von ${(dv.memory_mb.total / 1024).toFixed(1)} GB belegt` : "",
      memPct === null ? "" : memPct < 85 ? "ok" : "warn"),
    kpi("Disk frei", `${dv.disk_free_gb} GB`, `von ${dv.disk_total_gb} GB`, dv.disk_free_gb > 5 ? "ok" : "warn"));

  const facts = el("dl", { class: "facts" },
    el("dt", {}, "Laufzeit Gerät"), el("dd", {}, dur(dv.uptime_s)),
    el("dt", {}, "Software"), el("dd", {}, dv.version),
    el("dt", {}, "Ton"), el("dd", {}, core.audio === "text" ? "Textmodus (Simulation)" : core.audio || "–"),
    el("dt", {}, "Hilfe-Kanal"), el("dd", {}, CHANNEL_LABEL[core.channel] || core.channel || "–"),
    el("dt", {}, "Spracherkennung"), el("dd", {}, ai.stt_model),
    el("dt", {}, "Stimme"), el("dd", {}, ai.voice),
    el("dt", {}, "Cloud-Sprachmodell"), el("dd", {}, ai.cloud_allowed ? "erlaubt" : "gesperrt"),
    el("dt", {}, "Letzter Neustart Gesprächsteil"), el("dd", {}, core.last_restart || "–"));

  const dayRows = days.map((d) => el("tr", {}, el("td", {}, d.date), el("td", {}, String(d.turns)),
    el("td", {}, ms(d.stt_ms.p50)), el("td", {}, ms(d.llm_ms.p50)), el("td", {}, ms(d.tts_ms.p50)),
    el("td", {}, ms(d.answer_ms.p95)),
    el("td", {}, Object.entries(d.errors || {}).map(([k, v]) => `${k}: ${v}`).join(", ") || "–"),
    el("td", {}, Object.entries(d.events || {}).map(([k, v]) => `${k}: ${v}`).join(", ") || "–")));

  $("panel").replaceChildren(tiles,
    el("div", { class: "grid2" },
      el("div", { class: "card" }, el("h3", {}, "Antwortzeit pro Tag"),
        el("p", { class: "small muted" }, "Zeit vom Ende des Sprechens bis zum Beginn der Antwort (Erkennung + Sprachmodell)."),
        days.length ? latencyChart(days, h.latency_target_ms) : el("p", { class: "empty" }, "Noch keine Messwerte.")),
      el("div", { class: "card" }, el("h3", {}, "Gerät und Dienste"), facts)),
    el("div", { class: "card" }, el("h3", {}, "Tageswerte (Median, 95 %)"),
      el("div", { class: "tbl-wrap" }, el("table", {},
        el("thead", {}, el("tr", {}, ...["Tag", "Antworten", "Erkennung", "Modell", "Stimme", "Antwort 95 %", "Fehler", "Ereignisse"].map((t) => el("th", {}, t)))),
        el("tbody", {}, dayRows)))),
    el("p", { class: "privacy" }, "Nur Technik: keine Gesprächsinhalte, keine Zeitpunkte einzelner Gespräche, nur Tageswerte (A8, B5)."));
}

// --- boot ---

(async () => {
  const r = await api("GET", "/api/me");
  if (r.status === 200) start(r.data); else showLogin();
})();
