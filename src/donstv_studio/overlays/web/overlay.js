// Overlay-Seite: baut sich aus «snapshot» und «update» des Overlay-Servers auf (F-17, F-18).
// Kein Neuladen nötig. Bei Verbindungsverlust bleibt das letzte Bild stehen und es wird
// leise mit wachsender Wartezeit neu verbunden (OBS-Bild bleibt sauber).
(function () {
  "use strict";

  var DEFAULT_FONT = "Be Vietnam Pro";
  var DEFAULT_STYLE = "comic"; // Standardstil einer Textquelle (wie im Original)
  var parts = location.pathname.split("/");
  var overlayId = parts[parts.length - 1];
  var token = new URLSearchParams(location.search).get("t") || "";
  var stage = document.getElementById("stage");
  var elements = new Map(); // Quellen-Kennung -> Element
  var delay = 500;
  var MAX_DELAY = 10000;

  // Für Tests und Fehlersuche
  window.__overlay = { renders: 0, connected: false, state: null };

  function px(n) { return Math.round(n) + "px"; }

  function mediaUrl(mediaId) {
    return "/media/" + encodeURIComponent(overlayId) + "/" + encodeURIComponent(mediaId) +
      "?t=" + encodeURIComponent(token);
  }

  function fontFamily(name) {
    if (!name || name === DEFAULT_FONT) return '"' + DEFAULT_FONT + '", sans-serif';
    return '"' + String(name).replace(/["\\]/g, "") + '", "' + DEFAULT_FONT + '", sans-serif';
  }

  function applyText(el, props) {
    var style = props.style || DEFAULT_STYLE;
    el.className = "source text txt-" + style;
    el.textContent = props.text || ""; // textContent: kein HTML einschleusbar
    el.style.color = props.color || "#ffffff";
    el.style.fontSize = px(props.size || 48);
    el.style.fontFamily = fontFamily(props.font);
  }

  function applyImage(el, props, media) {
    el.className = "source image";
    var id = props.media_id || "";
    var info = id && media[id];
    var wantTag = info ? (info.mime === "video/webm" ? "VIDEO" : "IMG") : "";
    var child = el.firstElementChild;
    if (!info) { // nichts zu zeigen
      if (child) el.removeChild(child);
      return;
    }
    if (child && (child.tagName !== wantTag || child.dataset.mediaId !== id)) {
      el.removeChild(child);
      child = null;
    }
    if (!child) {
      child = document.createElement(wantTag === "VIDEO" ? "video" : "img");
      child.dataset.mediaId = id;
      if (wantTag === "VIDEO") {
        child.muted = true; child.loop = true; child.autoplay = true;
        child.setAttribute("playsinline", "");
      } else {
        child.alt = "";
      }
      child.src = mediaUrl(id);
      el.appendChild(child);
    }
  }

  function render(overlay) {
    window.__overlay.state = overlay;
    window.__overlay.renders += 1;
    stage.style.width = px(overlay.width);
    stage.style.height = px(overlay.height);
    document.body.style.width = px(overlay.width);
    document.body.style.height = px(overlay.height);

    var seen = new Set();
    overlay.sources.forEach(function (s) {
      seen.add(s.id);
      var el = elements.get(s.id);
      if (el && el.dataset.kind !== s.kind) { stage.removeChild(el); elements.delete(s.id); el = null; }
      if (!el) {
        el = document.createElement("div");
        el.dataset.sourceId = s.id;
        el.dataset.kind = s.kind;
        stage.appendChild(el);
        elements.set(s.id, el);
      }
      // Ganze Pixel, Drehung um die Mitte, Reihenfolge über z (F-65)
      el.style.left = px(s.x);
      el.style.top = px(s.y);
      el.style.width = px(s.width);
      el.style.height = px(s.height);
      el.style.zIndex = String(s.z);
      el.style.transform = s.rotation ? "rotate(" + s.rotation + "deg)" : "none";
      if (s.kind === "text") applyText(el, s.props);
      else if (s.kind === "image") applyImage(el, s.props, overlay.media || {});
      el.classList.toggle("hidden", !s.visible);
    });
    elements.forEach(function (el, id) {
      if (!seen.has(id)) { stage.removeChild(el); elements.delete(id); }
    });
  }

  function clear() {
    elements.forEach(function (el) { stage.removeChild(el); });
    elements.clear();
  }

  function connect() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var ws = new WebSocket(proto + "//" + location.host + "/o/" + encodeURIComponent(overlayId) +
      "/ws?t=" + encodeURIComponent(token));
    window.__overlay.socket = ws;
    ws.onopen = function () { delay = 500; window.__overlay.connected = true; };
    ws.onmessage = function (ev) {
      var msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (msg.type === "snapshot" || msg.type === "update") render(msg.overlay);
      else if (msg.type === "deleted") clear();
    };
    ws.onclose = function () {
      window.__overlay.connected = false;
      setTimeout(connect, delay);
      delay = Math.min(delay * 2, MAX_DELAY);
    };
    ws.onerror = function () { try { ws.close(); } catch (e) { /* ignorieren */ } };
  }

  connect();
})();
