const fields = ["host", "port", "token", "log_level", "action_timeout_minutes", "allow_dangerous_actions"];

async function loadSettings() {
    try {
        const d = await api("/api/settings");
        for (const k of fields) {
            const e = document.getElementById(k);
            if (e.type === "checkbox") e.checked = d.settings[k];
            else e.value = d.settings[k];
        }
        document.getElementById("serverStatus").textContent = d.running
            ? `Aktiv: ${d.active.host}:${d.active.port}`
            : "Kommandoserver gestoppt";

        const autostartCheck = document.getElementById("autostart");
        autostartCheck.checked = !!d.autostart;
    } catch (e) {
        notify(e.message, {kind: "error"});
    }
}

document.getElementById("autostart").onchange = async () => {
    const desired = document.getElementById("autostart").checked;
    try {
        const res = await api("/api/autostart", jsonRequest("POST", {enabled: desired}));
        document.getElementById("autostart").checked = !!res.enabled;
        notify(res.enabled ? "Autostart-Verknüpfung eingerichtet." : "Autostart entfernt.", {kind: "success"});
    } catch (e) {
        document.getElementById("autostart").checked = !desired;
        notify(`Autostart-Fehler: ${e.message}`, {kind: "error"});
    }
};

function generateToken() {
    document.getElementById("token").value = Array.from(
        crypto.getRandomValues(new Uint8Array(32)),
        x => x.toString(16).padStart(2, "0")
    ).join("");
    notify("Token vorbereitet — Übernehmen zum Aktivieren.");
}

async function applySettings(b) {
    b.disabled = true;
    const n = notify("Einstellungen werden übernommen …", {duration: 0});
    try {
        const d = {};
        for (const k of fields) {
            const e = document.getElementById(k);
            d[k] = e.type === "checkbox" ? e.checked : e.type === "number" ? Number(e.value) : e.value;
        }
        await api("/api/settings", jsonRequest("POST", d));
        await loadSettings();
        n.update("Einstellungen gespeichert und Server aktualisiert.", "success");
    } catch (e) {
        n.update(e.message, "error");
    } finally {
        b.disabled = false;
        n.dismissAfter();
    }
}

loadSettings();
loadLogs();
setInterval(loadLogs, 2000);
