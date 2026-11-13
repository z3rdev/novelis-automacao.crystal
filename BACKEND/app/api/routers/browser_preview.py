import json
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
PREVIEW_NAVIGATION_PATCH = """
<script>
(function () {
  if (window.__automationNovelisPreviewPatch) return;
  window.__automationNovelisPreviewPatch = true;
  var proxyPrefix = "/api/browser/site/";
  var remoteOrigin = "https://webcloud16.datapardc.com";
  var previewWValue;
  function lockFalse(target, key) {
    try {
      Object.defineProperty(target, key, {
        configurable: false,
        enumerable: true,
        get: function () { return false; },
        set: function () {}
      });
    } catch (_error) {
      try { target[key] = false; } catch (_nestedError) {}
    }
  }
  function lockPreviewFrameMode(target) {
    if (!target) return;
    lockFalse(target, "underIframe");
    lockFalse(target, "gooutofiframe");
    lockFalse(target, "openinsideopener");
    lockFalse(target, "callparentclose");
    try {
      target.nowarnings = true;
      target.xhrreverse = true;
      target.disablewebsocket = true;
      target.reverseproxy = true;
      target.informOnBadConnection = false;
      target.connectionmessage = false;
      syncPreviewCredentials(target);
    } catch (_error) {}
  }
  function syncPreviewCredentials(target) {
    if (!target) return;
    [
      "cmdline", "user", "pass", "code", "server",
      "port", "webport", "lang", "domain", "encPassW"
    ].forEach(function (key) {
      if ((target[key] === "" || target[key] === null || typeof target[key] === "undefined") && window[key]) {
        target[key] = window[key];
      }
    });
    try {
      if (window.pass && !target.encPassW) target.pass = window.pass;
      if (window.encPassW) target.encPassW = window.encPassW;
    } catch (_error) {}
  }
  function installPreviewFrameLock() {
    try {
      previewWValue = window.W || previewWValue;
      Object.defineProperty(window, "W", {
        configurable: true,
        enumerable: true,
        get: function () { return previewWValue; },
        set: function (value) {
          previewWValue = value;
          lockPreviewFrameMode(previewWValue);
        }
      });
      lockPreviewFrameMode(previewWValue);
    } catch (_error) {
      lockPreviewFrameMode(window.W);
    }
  }
  function extractWindowNameValue(script, key) {
    var marker = "window." + key + "='";
    var start = script.indexOf(marker);
    if (start < 0) return null;
    start += marker.length;
    var end = script.indexOf("';", start);
    if (end < 0) return null;
    return script.substring(start, end).split("\\\\'").join("'");
  }
  function hydrateWindowNameGlobals() {
    try {
      var script = decodeWindowNameScript(window.name);
      if (!script) return;
      [
        "cmdline", "user", "pass", "code", "server",
        "port", "webport", "lang", "domain", "encPassW"
      ].forEach(function (key) {
        var value = extractWindowNameValue(script, key);
        if (value !== null) window[key] = value;
      });
      syncPreviewCredentials(window.W);
    } catch (_error) {}
  }
  function decodeWindowNameScript(value) {
    var script = String(value || "");
    for (var index = 0; index < 4; index += 1) {
      var previous = script;
      try { script = decodeBase64Value(script); } catch (_base64Error) {}
      try { script = decodeURIComponent(script); } catch (_decodeError) {}
      if (script.indexOf("window.") >= 0) break;
      if (script === previous) break;
    }
    return script;
  }
  function decodeBase64Value(value) {
    var input = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
    while (input.length % 4) input += "=";
    return window.atob(input);
  }
  function rememberWindowName(target) {
    var name = String(target || "");
    if (!name || /^_(blank|self|parent|top)$/i.test(name)) return;
    try {
      window.name = name;
      hydrateWindowNameGlobals();
    } catch (_error) {}
  }
  function normalizeCookiePath(value) {
    var cookie = String(value || "");
    if (!cookie) return cookie;
    if (/;\\s*path\\s*=/i.test(cookie)) {
      return cookie.replace(/;\\s*path\\s*=\\s*[^;]*/ig, "; path=" + proxyPrefix.replace(/\\/$/, ""));
    }
    return cookie + "; path=" + proxyPrefix.replace(/\\/$/, "");
  }
  function normalizeDocumentCookieWrites() {
    try {
      var prototypes = [
        Document.prototype,
        typeof HTMLDocument !== "undefined" ? HTMLDocument.prototype : null
      ];
      var descriptor = null;
      for (var index = 0; index < prototypes.length; index += 1) {
        var proto = prototypes[index];
        if (!proto) continue;
        descriptor = Object.getOwnPropertyDescriptor(proto, "cookie");
        if (descriptor && descriptor.get && descriptor.set) break;
      }
      if (!descriptor || !descriptor.get || !descriptor.set) return;
      Object.defineProperty(document, "cookie", {
        configurable: true,
        get: function () { return descriptor.get.call(document); },
        set: function (value) { return descriptor.set.call(document, normalizeCookiePath(value)); }
      });
    } catch (_error) {}
  }
  function resetPreviewWorkers() {
    if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
      navigator.serviceWorker.getRegistrations().then(function (registrations) {
        registrations.forEach(function (registration) {
          if (registration.scope.indexOf(proxyPrefix) >= 0) registration.unregister();
        });
      }).catch(function () {});
    }
    if (window.caches && window.caches.keys) {
      window.caches.keys().then(function (keys) {
        keys.forEach(function (key) { window.caches.delete(key); });
      }).catch(function () {});
    }
  }
  function forcePreviewFrameMode() {
    try {
      lockPreviewFrameMode(window.W);
    } catch (_error) {}
  }
  function normalizePreviewUrl(value) {
    if (!value || value === "about:blank") return value;
    try {
      var raw = String(value);
      if (raw.indexOf("software/") === 0 || raw.indexOf("/software/") === 0) {
        return window.location.origin + proxyPrefix + raw.replace(/^\\/+/, "");
      }
      var url = new URL(value, window.location.href);
      if (url.origin === window.location.origin && url.pathname.indexOf(proxyPrefix) === 0) {
        return url.href;
      }
      if (url.origin === remoteOrigin) {
        return window.location.origin + proxyPrefix + url.pathname.replace(/^\\/+/, "") + url.search + url.hash;
      }
      if (url.origin === window.location.origin) return url.href;
    } catch (_error) {
      return value;
    }
    return value;
  }
  function navigateInFrame(value) {
    var target = normalizePreviewUrl(value);
    if (target && target !== "about:blank") window.location.assign(target);
    return window;
  }
  var originalOpen = window.open ? window.open.bind(window) : null;
  window.open = function (url, target, features) {
    rememberWindowName(target);
    if (url) return navigateInFrame(url);
    if (originalOpen) return originalOpen(url, "_self", features);
    return window;
  };
  document.addEventListener("click", function (event) {
    var target = event.target;
    var link = target && target.closest ? target.closest("a[target]") : null;
    if (!link) return;
    var href = link.getAttribute("href");
    if (!href) {
      link.setAttribute("target", "_self");
      return;
    }
    event.preventDefault();
    navigateInFrame(href);
  }, true);
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form && form.tagName === "FORM") form.target = "_self";
  }, true);
  function allowedPreviewOrigin(origin) {
    return origin === "http://127.0.0.1:5173" ||
      origin === "http://localhost:5173" ||
      origin === window.location.origin;
  }
  function scaledPoint(command) {
    var sourceWidth = Number(command.viewportWidth || 1024);
    var sourceHeight = Number(command.viewportHeight || 750);
    var viewWidth = window.innerWidth || document.documentElement.clientWidth || sourceWidth;
    var viewHeight = window.innerHeight || document.documentElement.clientHeight || sourceHeight;
    return {
      x: Number(command.x || 0) * viewWidth / sourceWidth,
      y: Number(command.y || 0) * viewHeight / sourceHeight
    };
  }
  function targetAt(point) {
    return document.elementFromPoint(point.x, point.y) || document.body || document.documentElement;
  }
  function dispatchPointer(target, type, point, buttons) {
    var EventClass = window.PointerEvent || window.MouseEvent;
    target.dispatchEvent(new EventClass(type, {
      bubbles: true, cancelable: true, view: window,
      clientX: point.x, clientY: point.y, screenX: point.x, screenY: point.y,
      button: 0, buttons: buttons, pointerId: 1, pointerType: "mouse", isPrimary: true
    }));
  }
  function dispatchMouse(target, type, point, buttons) {
    target.dispatchEvent(new MouseEvent(type, {
      bubbles: true, cancelable: true, view: window,
      clientX: point.x, clientY: point.y, screenX: point.x, screenY: point.y,
      button: 0, buttons: buttons
    }));
  }
  function previewClick(command) {
    var point = scaledPoint(command);
    var target = targetAt(point);
    if (target && target.focus) target.focus();
    dispatchPointer(target, "pointermove", point, 0);
    dispatchMouse(target, "mousemove", point, 0);
    dispatchPointer(target, "pointerdown", point, 1);
    dispatchMouse(target, "mousedown", point, 1);
    dispatchPointer(target, "pointerup", point, 0);
    dispatchMouse(target, "mouseup", point, 0);
    dispatchMouse(target, "click", point, 0);
  }
  function dispatchKeyboard(target, type, key) {
    if (!target || !target.dispatchEvent) return;
    var code = key && key.length === 1 ? key.toUpperCase().charCodeAt(0) : 0;
    var event = new KeyboardEvent(type, {
      bubbles: true, cancelable: true,
      key: key, code: key.length === 1 ? "Key" + key.toUpperCase() : key,
      keyCode: code, which: code, charCode: type === "keypress" ? code : 0
    });
    try {
      Object.defineProperty(event, "keyCode", { get: function () { return code; } });
      Object.defineProperty(event, "which", { get: function () { return code; } });
      Object.defineProperty(event, "charCode", { get: function () { return type === "keypress" ? code : 0; } });
    } catch (_error) {}
    target.dispatchEvent(event);
  }
  function sendRemoteText(text) {
    try {
      if (window.W && typeof window.W.sendScannerText === "function") {
        window.W.sendScannerText(text);
        return true;
      }
    } catch (_error) {}
    return false;
  }
  function previewType(command) {
    var text = String(command.text || "");
    var target = document.activeElement || document.body || document.documentElement;
    var tagName = target && target.tagName ? target.tagName.toLowerCase() : "";
    var canSetValue = tagName === "input" || tagName === "textarea";
    if (canSetValue) {
      target.value = String(target.value || "") + text;
      target.dispatchEvent(new Event("input", { bubbles: true }));
      target.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
    if (sendRemoteText(text)) return;
    for (var index = 0; index < text.length; index += 1) {
      var key = text[index];
      var targets = [target, document.body, document, window];
      targets.forEach(function (item) { dispatchKeyboard(item, "keydown", key); });
      targets.forEach(function (item) { dispatchKeyboard(item, "keypress", key); });
      targets.forEach(function (item) { dispatchKeyboard(item, "keyup", key); });
    }
  }
  function previewSetValue(command) {
    var target = document.querySelector(String(command.selector || ""));
    if (!target) return false;
    var text = String(command.text || "");
    if (target.focus) target.focus();
    target.value = text;
    target.dispatchEvent(new Event("input", { bubbles: true }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
    target.dispatchEvent(new Event("blur", { bubbles: true }));
    return true;
  }
  window.__automationNovelisPreviewClick = previewClick;
  window.__automationNovelisPreviewType = previewType;
  window.__automationNovelisPreviewSetValue = previewSetValue;
  window.addEventListener("message", function (event) {
    if (!allowedPreviewOrigin(event.origin)) return;
    var command = event.data || {};
    if (command.source !== "automacao-novelis-preview") return;
    window.__automationNovelisLastCommand = command;
    if (command.type === "preview.click") previewClick(command);
    if (command.type === "preview.type") previewType(command);
    if (command.type === "preview.set_value") previewSetValue(command);
    if (command.type === "preview.dellmar_login" && window.__automationNovelisDellmarLogin) {
      window.__automationNovelisDellmarLogin();
    }
  });
  resetPreviewWorkers();
  normalizeDocumentCookieWrites();
  hydrateWindowNameGlobals();
  installPreviewFrameLock();
  forcePreviewFrameMode();
  var frameModeTimer = window.setInterval(forcePreviewFrameMode, 100);
  window.setTimeout(function () { window.clearInterval(frameModeTimer); }, 60000);
})();
</script>
"""
NOOP_SERVICE_WORKER = """
self.addEventListener("install", function (event) {
  self.skipWaiting();
});
self.addEventListener("activate", function (event) {
  event.waitUntil(
    self.registration.unregister().then(function () {
      return self.clients.matchAll();
    }).then(function (clients) {
      clients.forEach(function (client) { client.navigate(client.url); });
    })
  );
});
"""
def build_preview_patch(
    settings: Settings,
    html_text: str,
    proxy_prefix: str = "/api/browser/site/",
    remote_origin: str = "https://webcloud16.datapardc.com",
) -> str:
    navigation_patch = (
        PREVIEW_NAVIGATION_PATCH.replace(
            'var proxyPrefix = "/api/browser/site/";',
            f"var proxyPrefix = {json.dumps(proxy_prefix)};",
        ).replace(
            'var remoteOrigin = "https://webcloud16.datapardc.com";',
            f"var remoteOrigin = {json.dumps(remote_origin)};",
        )
    )
    auto_login = _preview_auto_login_patch(settings) if _looks_like_datapar_login(html_text) else ""
    dellmar_login = _preview_dellmar_login_patch(settings)
    return navigation_patch + auto_login + dellmar_login
def _preview_dellmar_login_patch(settings: Settings) -> str:
    config = LegacyConfig(settings)
    user = config.get("PRE_DELLMAR_USER")
    password = config.get("PRE_DELLMAR_PASS")
    if not user or not password:
        return ""
    manual_login = config.bool("PRE_DELLMAR_MANUAL_LOGIN", False)
    can_submit = (
        not manual_login
        and password.strip().lower() not in {"123", "senha", "password", "changeme"}
    )
    credentials = json.dumps({"user": user, "password": password, "canSubmit": can_submit})
    return f"""
<script>
(function () {{
  if (window.__automationNovelisDellmarLoginPatch) return;
  window.__automationNovelisDellmarLoginPatch = true;
  if (window.location.pathname.indexOf("/software/html5.html") < 0) return;
  var credentials = {credentials};
  function click(x, y) {{
    if (!window.__automationNovelisPreviewClick) return;
    window.__automationNovelisPreviewClick({{
      type: "preview.click",
      x: x,
      y: y,
      viewportWidth: 1024,
      viewportHeight: 750
    }});
  }}
  function sendText(text) {{
    if (!window.__automationNovelisPreviewType) return;
    window.__automationNovelisPreviewType({{ type: "preview.type", text: text }});
  }}
  function login() {{
    if (!credentials.canSubmit) return;
    click(516, 384);
    window.setTimeout(function () {{ sendText(credentials.user); }}, 250);
    window.setTimeout(function () {{ click(462, 410); }}, 900);
    window.setTimeout(function () {{ sendText(credentials.password); }}, 1150);
    window.setTimeout(function () {{ click(470, 455); }}, 2200);
  }}
  function run() {{
    click(300, 430);
    window.setTimeout(function () {{ click(84, 385); }}, 13000);
    window.setTimeout(login, 27000);
  }}
  window.__automationNovelisDellmarLogin = login;
}})();
</script>
"""
def _preview_auto_login_patch(settings: Settings) -> str:
    config = LegacyConfig(settings)
    if not config.bool("PREVIEW_AUTO_LOGIN", False):
        return ""
    user = config.get("PRE_USER")
    password = config.get("PRE_PASS")
    if not user or not password:
        return ""
    credentials = json.dumps({"user": user, "password": password})
    return f"""
<script>
(function () {{
  var credentials = {credentials};
  var attempts = 0;
  var filled = false;
  var submitAttempts = 0;
  function setValue(field, value) {{
    field.focus();
    field.value = value;
    field.dispatchEvent(new Event("input", {{ bubbles: true }}));
    field.dispatchEvent(new Event("change", {{ bubbles: true }}));
  }}
  function chooseHtml5() {{
    var options = Array.prototype.slice.call(document.querySelectorAll("input[type='radio']"));
    var html5 = options.find(function (item) {{
      return /html5/i.test(String(item.value || item.id || item.name || ""));
    }});
    if (html5 && !html5.checked) {{
      html5.checked = true;
      html5.dispatchEvent(new Event("change", {{ bubbles: true }}));
    }}
  }}
  function tryLogin() {{
    attempts += 1;
    var user = document.querySelector("#Editbox1");
    var password = document.querySelector("#Editbox2");
    var button = document.querySelector("#buttonLogOn");
    if (!user || !password || !button) return attempts > 40;
    if (!filled) {{
      filled = true;
      chooseHtml5();
      setValue(user, credentials.user);
      setValue(password, credentials.password);
      if (window.onLoginTyped) window.onLoginTyped();
      return false;
    }}
    var handler = String(button.onclick || button.getAttribute("onclick") || "");
    var ready = handler.indexOf("cplogon") >= 0 || typeof window.cplogon === "function";
    var twoFactorReady = !window.twoStepStatus || window.twoStepStatus === "disabled";
    if (!twoFactorReady || (!ready && attempts < 8)) return attempts > 80;
    if (window.__automationNovelisPreviewLoginDone && submitAttempts >= 2) return true;
    window.__automationNovelisPreviewLoginDone = true;
    submitAttempts += 1;
    chooseHtml5();
    if (window.cplogon) window.cplogon();
    else button.click();
    return submitAttempts >= 6;
  }}
  function start() {{
    var timer = window.setInterval(function () {{
      if (tryLogin()) window.clearInterval(timer);
    }}, 250);
  }}
  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", start, {{ once: true }});
  }} else {{
    start();
  }}
}})();
</script>
"""
def _looks_like_datapar_login(text: str) -> bool:
    lowered = text.lower()
    return "editbox1" in lowered and "buttonlogon" in lowered
