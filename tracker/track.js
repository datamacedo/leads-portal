/**
 * InForge Leads — track.js v1
 *
 * Uso (cliente cola no <head> do site):
 *   <script src="https://cdn.inforge.com.br/track.js" data-token="TOKEN_DO_CLIENTE"></script>
 *
 * Identificação (no submit do formulário):
 *   Inforge.identify({ email: "carlos@empresa.com", nome: "Carlos" })
 *
 * Captura automática: pageviews, cliques, scroll, tempo na página,
 * dispositivo/OS/browser/tela/conexão, UTM e referrer.
 */
(function () {
  "use strict";

  var script = document.currentScript || document.querySelector("script[data-token]");
  if (!script) return;
  var TOKEN = script.getAttribute("data-token");
  var API = script.getAttribute("data-api") || "https://api.inforge.com.br/api/v1/track";
  if (!TOKEN) return;

  // ---------- Identidades ----------
  function uuid() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  function getVisitorId() {
    try {
      var id = localStorage.getItem("_ifl_vid");
      if (!id) { id = uuid(); localStorage.setItem("_ifl_vid", id); }
      return id;
    } catch (e) { return uuid(); }
  }

  // Sessão: expira após 30 min de inatividade
  function getSessionKey() {
    try {
      var raw = sessionStorage.getItem("_ifl_sid");
      var now = Date.now();
      if (raw) {
        var s = JSON.parse(raw);
        if (now - s.last < 30 * 60 * 1000) {
          s.last = now;
          sessionStorage.setItem("_ifl_sid", JSON.stringify(s));
          return s.key;
        }
      }
      var key = uuid();
      sessionStorage.setItem("_ifl_sid", JSON.stringify({ key: key, last: now }));
      return key;
    } catch (e) { return uuid(); }
  }

  var VISITOR_ID = getVisitorId();
  var SESSION_KEY = getSessionKey();

  // ---------- Dispositivo ----------
  function deviceInfo() {
    var ua = navigator.userAgent;
    var type = "desktop";
    if (/Mobi|Android.*Mobile|iPhone/i.test(ua)) type = "mobile";
    else if (/iPad|Android(?!.*Mobile)|Tablet/i.test(ua)) type = "tablet";
    else if (/Macintosh|Windows NT/.test(ua) && navigator.maxTouchPoints > 1) type = "tablet";

    var os = "Outro";
    if (/Windows NT 10/.test(ua)) os = "Windows 10/11";
    else if (/Windows/.test(ua)) os = "Windows";
    else if (/iPhone|iPad/.test(ua)) os = "iOS";
    else if (/Android/.test(ua)) os = "Android";
    else if (/Macintosh/.test(ua)) os = "macOS";
    else if (/Linux/.test(ua)) os = "Linux";

    var browser = "Outro";
    if (/Edg\//.test(ua)) browser = "Edge";
    else if (/Chrome\//.test(ua)) browser = "Chrome";
    else if (/Safari\//.test(ua) && !/Chrome/.test(ua)) browser = "Safari";
    else if (/Firefox\//.test(ua)) browser = "Firefox";

    var conn = (navigator.connection && navigator.connection.effectiveType) || null;

    return {
      type: type, os: os, browser: browser,
      screen: screen.width + "x" + screen.height,
      connection: conn,
      touch: navigator.maxTouchPoints > 0
    };
  }

  // ---------- UTM ----------
  function utmParams() {
    var p = new URLSearchParams(location.search), out = {}, found = false;
    ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"].forEach(function (k) {
      if (p.get(k)) { out[k] = p.get(k); found = true; }
    });
    return found ? out : null;
  }

  // ---------- Envio ----------
  function send(type, data, useBeacon) {
    var payload = JSON.stringify({
      token: TOKEN,
      visitor_id: VISITOR_ID,
      session_key: SESSION_KEY,
      type: type,
      url: location.href,
      data: data || null,
      device: deviceInfo(),
      referrer: document.referrer || null,
      utm: utmParams()
    });
    var url = API + "/event";
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([payload], { type: "application/json" }));
    } else {
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true
      }).catch(function () {});
    }
  }

  // ---------- Pageview + tempo na página ----------
  var pageStart = Date.now();
  send("pageview", { title: document.title });

  function flushTime() {
    var secs = Math.round((Date.now() - pageStart) / 1000);
    if (secs > 0) send("pageview", { title: document.title, time_on_page: secs }, true);
    pageStart = Date.now();
  }
  window.addEventListener("pagehide", flushTime);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flushTime();
  });

  // SPA: detecta mudança de rota
  var lastPath = location.pathname;
  setInterval(function () {
    if (location.pathname !== lastPath) {
      flushTime();
      lastPath = location.pathname;
      send("pageview", { title: document.title });
    }
  }, 800);

  // ---------- Cliques ----------
  document.addEventListener("click", function (e) {
    var el = e.target.closest("a, button, [role=button], input[type=submit]");
    if (!el) return;
    send("click", {
      tag: el.tagName.toLowerCase(),
      text: (el.innerText || el.value || "").trim().slice(0, 80),
      href: el.href || null,
      id: el.id || null,
      classes: (typeof el.className === "string" ? el.className : "").slice(0, 120)
    });
  }, true);

  // ---------- Scroll depth (25/50/75/100) ----------
  var marks = { 25: false, 50: false, 75: false, 100: false };
  window.addEventListener("scroll", function () {
    var h = document.documentElement;
    var pct = Math.round(((h.scrollTop + window.innerHeight) / h.scrollHeight) * 100);
    [25, 50, 75, 100].forEach(function (m) {
      if (pct >= m && !marks[m]) { marks[m] = true; send("scroll", { depth_pct: m }); }
    });
  }, { passive: true });

  // ---------- Formulários ----------
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var fields = {};
    try {
      new FormData(form).forEach(function (v, k) {
        var kl = k.toLowerCase();
        // captura apenas campos de contato — nunca senhas/cartões
        if (/email|e-mail/.test(kl)) fields.email = String(v);
        else if (/phone|telefone|celular|whats/.test(kl)) fields.phone = String(v);
        else if (/^(name|nome|full_?name)$/.test(kl)) fields.name = String(v);
        else if (/empresa|company/.test(kl)) fields.company = String(v);
      });
    } catch (err) {}
    send("form_submit", { form_id: form.id || null, action: form.action || null });
    if (fields.email || fields.phone) window.Inforge.identify(fields);
  }, true);

  // ---------- API pública ----------
  window.Inforge = {
    identify: function (data) {
      fetch(API + "/identify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: TOKEN,
          visitor_id: VISITOR_ID,
          email: data.email || null,
          phone: data.phone || data.telefone || null,
          name: data.name || data.nome || null,
          company: data.company || data.empresa || null
        }),
        keepalive: true
      }).catch(function () {});
    },
    track: function (eventName, data) {
      send("custom", Object.assign({ event: eventName }, data || {}));
    }
  };
})();
