const pending = new Map();

function button(text, fn, cls="") {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.onclick = fn;
    b.className = cls;
    return b;
}

function statusRow(row, badge, active) {
    row.classList.toggle("inactive", !active);
    badge.textContent = active ? "Aktiv" : "Deaktiviert";
}

async function loadActions() {
    try {
        const all = await api("/api/actions"), body = document.getElementById("actions");
        body.replaceChildren();
        for (const a of all) {
            const row = document.createElement("tr");
            const check = document.createElement("input");
            check.type = "checkbox";
            check.checked = a.enabled;
            check.title = "Aktion aktivieren/deaktivieren";
            check.setAttribute("aria-label", `Aktion ${a.name} aktivieren`);

            const name = document.createElement("input");
            name.value = a.name;

            const trigger = document.createElement("input");
            trigger.value = a.trigger;
            trigger.placeholder = "/netflix";

            const timeout = document.createElement("input");
            timeout.type = "text";
            timeout.inputMode = "numeric";
            timeout.placeholder = "timeout";
            timeout.value = (a.timeout_minutes !== null && a.timeout_minutes !== undefined) ? a.timeout_minutes : "";
            timeout.style.width = "90px";
            timeout.title = "Timeout in ganzen Minuten (leer = 1 Min)";
            filterDigitsOnly(timeout);

            const category = createCategorySelect(a.category || "");
            const meta = document.createElement("div"); meta.className = "action-meta";
            meta.append(category);
            const badge = document.createElement("span");
            badge.className = "badge";
            statusRow(row, badge, a.enabled);

            for (const el of [check, name, trigger, timeout, badge, meta]) {
                const td = document.createElement("td");
                td.append(el);
                row.append(td);
            }

            check.onchange = async () => {
                const desired = check.checked;
                check.disabled = true;
                try {
                    await api(`/api/actions/${a.id}`, jsonRequest("PUT", {enabled: desired}));
                    a.enabled = desired;
                    statusRow(row, badge, desired);
                    notify(desired ? "Aktion aktiviert." : "Aktion deaktiviert.", {kind: "success"});
                } catch (e) {
                    check.checked = a.enabled;
                    notify(e.message, {kind: "error"});
                } finally {
                    check.disabled = false;
                }
            };

            const controls = document.createElement("td");
            controls.className = "action-buttons";

            const save = button("Speichern", async () => {
                save.disabled = true;
                const n = notify("Speichern läuft …", {duration: 0});
                try {
                    let trigVal = trigger.value.trim();
                    if (!trigVal) throw Error("Trigger darf nicht leer sein (z.B. /netflix).");
                    if (!trigVal.startsWith("/")) trigVal = "/" + trigVal;
                    const rawTo = timeout.value.trim();
                    const timeoutVal = rawTo === "" ? null : parseInt(rawTo, 10);
                    await api(`/api/actions/${a.id}`, jsonRequest("PUT", {
                        name: name.value.trim(),
                        trigger: trigVal,
                        timeout_minutes: timeoutVal,
                        category: category.value
                    }));
                    trigger.value = trigVal;
                    n.update("Gespeichert.", "success");
                } catch (e) {
                    n.update(e.message, "error");
                } finally {
                    save.disabled = false;
                    n.dismissAfter();
                }
            });
            controls.append(save);

            controls.append(button("Blockly", () => location.href = `/editor/${a.id}`, "primary"));

            const testBtn = button("Testlauf", async () => {
                testBtn.disabled = true;
                const n = notify("Testlauf angefordert …", {duration: 0});
                try {
                    const job = await api(`/api/actions/${a.id}/test`, jsonRequest("POST", {}));
                    while (true) {
                        const s = await api(`/api/tests/${job.id}`);
                        if (s.state === "running") n.update("Testlauf läuft …");
                        if (s.state === "done") { n.update("Testlauf abgeschlossen.", "success"); break; }
                        if (s.state === "stopped") { n.update("Testlauf abgebrochen.", "warning"); break; }
                        if (s.state === "error") throw Error(s.error);
                        await new Promise(r => setTimeout(r, 400));
                    }
                } catch (e) {
                    n.update(`Fehler: ${e.message}`, "error");
                } finally {
                    testBtn.disabled = false;
                    n.dismissAfter(6000);
                }
            });
            controls.append(testBtn);

            controls.append(button("Export", () => location.href = `/api/actions/${a.id}/export`));
            controls.append(button("Löschen", () => deleteAction(a.id, row), "danger"));

            row.append(controls);
            body.append(row);
        }
    } catch (e) {
        notify(e.message, {kind: "error"});
    }
}

async function createAction(e, formEl) {
    if (e) e.preventDefault();
    const btn = formEl ? formEl.querySelector("button[type=submit]") : null;
    if (btn) btn.disabled = true;

    try {
        const nameInput = document.getElementById("newName");
        const trigInput = document.getElementById("newTrigger");
        const timeoutInput = document.getElementById("newTimeout");

        const nameVal = nameInput.value.trim();
        let trigVal = trigInput.value.trim();
        const rawTo = timeoutInput.value.trim();
        const timeoutVal = rawTo === "" ? null : parseInt(rawTo, 10);

        if (!nameVal) throw Error("Aktionsname darf nicht leer sein.");
        if (!trigVal) throw Error("Trigger darf nicht leer sein (z.B. /netflix).");
        if (!trigVal.startsWith("/")) trigVal = "/" + trigVal;

        await api("/api/actions", jsonRequest("POST", {
            name: nameVal,
            trigger: trigVal,
            category: document.getElementById("newCategory").value.trim(),
            timeout_minutes: timeoutVal
        }));

        nameInput.value = "";
        trigInput.value = "";
        timeoutInput.value = "";

        await loadActions();
        notify("Aktion erfolgreich angelegt (deaktiviert).", {kind: "success"});
    } catch (err) {
        notify(err.message, {kind: "error"});
    } finally {
        if (btn) btn.disabled = false;
    }
}

function deleteAction(id, row) {
    if (pending.has(id)) return;
    row.hidden = true;
    let done = false;
    const end = Date.now() + 5000;
    const n = notify("Löschen vorgemerkt — noch 5 Sekunden", {
        kind: "warning",
        duration: 0,
        actionLabel: "Rückgängig",
        onAction: () => {
            if (done) return;
            done = true;
            clearTimeout(timer);
            clearInterval(tick);
            pending.delete(id);
            row.hidden = false;
            n.close();
            notify("Löschen rückgängig gemacht.", {kind: "success"});
        }
    });
    const tick = setInterval(() => n.update(`Löschen vorgemerkt — noch ${Math.max(0, Math.ceil((end - Date.now()) / 1000))} Sekunden`, "warning"), 100);
    const timer = setTimeout(async () => {
        done = true;
        clearInterval(tick);
        pending.delete(id);
        n.close();
        try {
            await api(`/api/actions/${id}`, {method: "DELETE"});
            row.remove();
            notify("Aktion gelöscht.", {kind: "success"});
        } catch (e) {
            row.hidden = false;
            notify(e.message, {kind: "error"});
        }
    }, 5000);
    pending.set(id, true);
}

document.getElementById("importFile").onchange = async e => {
    try {
        if (!e.target.files[0]) return;
        await api("/api/actions/import", jsonRequest("POST", JSON.parse(await e.target.files[0].text())));
        await loadActions();
        notify("Aktion importiert — deaktiviert.", {kind: "success"});
    } catch (e) {
        notify(e.message, {kind: "error"});
    } finally {
        e.target.value = "";
    }
};

filterDigitsOnly(document.getElementById("newTimeout"));
window.addEventListener("DOMContentLoaded", () => { loadActions(); });
loadLogs();
setInterval(loadLogs, 2000);
