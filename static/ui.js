window.notify = function(message, {kind="info", duration=5000, actionLabel, onAction}={}) {
    let box = document.getElementById("notifications");
    if (!box) {
        box = document.createElement("div");
        box.id = "notifications";
        Object.assign(box.style, {
            position: "fixed",
            bottom: "20px",
            right: "20px",
            zIndex: 99999,
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            maxWidth: "min(560px, calc(100vw - 40px))"
        });
        document.body.append(box);
    }
    const colors = {info: "#1e40af", success: "#166534", error: "#b91c1c", warning: "#92400e"};
    const item = document.createElement("div"), text = document.createElement("span");
    item.setAttribute("role", "status");
    Object.assign(item.style, {
        padding: "13px 17px",
        borderRadius: "10px",
        background: colors[kind],
        color: "white",
        display: "flex",
        gap: "12px",
        alignItems: "center",
        boxShadow: "0 6px 22px #0003",
        whiteSpace: "pre-wrap"
    });
    text.textContent = message;
    item.append(text);
    box.append(item);
    if (actionLabel) {
        const b = document.createElement("button");
        b.textContent = actionLabel;
        b.onclick = onAction;
        item.append(b);
    }
    let timer;
    const h = {
        close() { clearTimeout(timer); item.remove(); },
        update(m, k="info") { text.textContent = m; item.style.background = colors[k]; },
        dismissAfter(ms=5000) { clearTimeout(timer); timer = setTimeout(() => h.close(), ms); }
    };
    if (duration > 0) h.dismissAfter(duration);
    return h;
};

window.api = async function(url, options={}) {
    options.headers = {...(options.headers || {}), "X-WinCtrl-Key": window.adminKey};
    const r = await fetch(url, options), d = await r.json().catch(() => ({}));
    if (!r.ok || d.ok === false) throw Error(d.error || `HTTP ${r.status}`);
    return d;
};

window.jsonRequest = (method, data) => ({
    method,
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data)
});

window.loadLogs = async () => {
    try {
        const e = document.getElementById("logs");
        if (e) e.textContent = (await api("/api/logs")).join("\n");
    } catch (e) {
        console.error(e);
    }
};

window.filterDigitsOnly = function(inputEl) {
    if (!inputEl) return;
    inputEl.addEventListener("input", () => {
        inputEl.value = inputEl.value.replace(/[^0-9]/g, "");
    });
};
