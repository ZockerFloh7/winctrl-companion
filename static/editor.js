let workspace, saved, lastSeq = 0;
let currentJobId = null;
let pollTimer = null;

const definitions = [];
function action(type, label, value="", color=160, options=null) {
    definitions.push({
        type: "winctrl_" + type,
        message0: label + (value !== null ? " %1" : ""),
        args0: value === null ? [] : [
            options
                ? {type: "field_dropdown", name: "VALUE", options}
                : {type: "field_input", name: "VALUE", text: String(value)}
        ],
        previousStatement: null,
        nextStatement: null,
        colour: color
    });
}

definitions.push({type: "winctrl_when", message0: "Wenn Aktion gestartet wird", nextStatement: null, colour: 230});
action("start_app", "Programm starten", "notepad.exe");
action("open_url", "Webseite öffnen", "https://example.com");
action("focus_window", "Fenster fokussieren", "Editor");
action("press_key", "Taste drücken", "enter", 20);
action("hotkey", "Tastenkombination", "ctrl+s", 20);
action("type_text", "Text tippen (ASCII)", "Hallo", 20);
action("paste_text", "Text einfügen (Unicode)", "Hallo Welt", 20);
action("mouse_move", "Maus bewegen zu X,Y", "500,400", 260);
action("mouse_drag", "Mit linker Taste ziehen zu X,Y", "700,400", 260);
action("mouse_click", "Mausklick", "left", 260, [["Links", "left"], ["Rechts", "right"], ["Doppelklick", "double"], ["Mitte", "middle"]]);
action("scroll", "Scrollen (negativ = abwärts)", "3", 260);
action("media", "Medienaktion", "play_pause", 120, [["Play/Pause", "play_pause"], ["Nächster Titel", "next"], ["Vorheriger Titel", "prev"], ["Stopp", "stop"], ["Lauter", "volume_up"], ["Leiser", "volume_down"], ["Stumm", "mute"]]);
action("wait", "Warte Sekunden", "1", 290);
action("lock_pc", "PC sperren", null, 0);
action("shutdown_pc", "PC in 10 Sekunden herunterfahren", null, 0);

definitions.push({
    type: "winctrl_log",
    message0: "Logge %1 %2",
    args0: [
        {type: "field_dropdown", name: "LEVEL", options: [["Info", "INFO"], ["Warnung", "WARNING"], ["Fehler", "ERROR"], ["Debug", "DEBUG"]]},
        {type: "field_input", name: "VALUE", text: "Mein Logeintrag"}
    ],
    previousStatement: null,
    nextStatement: null,
    colour: 45
});
definitions.push({
    type: "winctrl_log_value",
    message0: "Logge Wert %1",
    args0: [{type: "input_value", name: "TEXT"}],
    previousStatement: null,
    nextStatement: null,
    colour: 45
});

definitions.push({
    type: "winctrl_return",
    message0: "Rückgabewert senden %1",
    args0: [{type: "field_input", name: "VALUE", text: "OK"}],
    previousStatement: null,
    nextStatement: null,
    colour: 180,
    tooltip: "Sendet einen Text als Rückgabewert an den Client (z.B. ioBroker)"
});
definitions.push({
    type: "winctrl_return_value",
    message0: "Rückgabewert senden (Wert) %1",
    args0: [{type: "input_value", name: "TEXT"}],
    previousStatement: null,
    nextStatement: null,
    colour: 180,
    tooltip: "Sendet einen Variablenwert oder Ausdruck als Rückgabewert an den Client"
});

for (const [type, label, value] of [["window_exists", "Fenster vorhanden", "Editor"], ["file_exists", "Datei vorhanden", "C:\\Windows\\notepad.exe"]]) {
    definitions.push({
        type: "winctrl_" + type,
        message0: label + " %1",
        args0: [{type: "field_input", name: "VALUE", text: value}],
        output: "Boolean",
        colour: 210
    });
}
definitions.push({type: "winctrl_clipboard", message0: "Zwischenablage lesen", output: "String", colour: 210});

const cat = (name, types) => ({kind: "category", name, contents: types.map(type => ({kind: "block", type}))});
const toolbox = {
    kind: "categoryToolbox",
    contents: [
        cat("Start", ["winctrl_when"]),
        cat("Antwort / Log", ["winctrl_return", "winctrl_return_value", "winctrl_log", "winctrl_log_value"]),
        cat("Logik", ["controls_if", "logic_compare", "logic_operation", "logic_negate", "logic_boolean"]),
        cat("Schleifen", ["controls_repeat_ext", "controls_whileUntil"]),
        {kind: "category", name: "Variablen", custom: "VARIABLE"},
        cat("Werte", ["math_number", "math_arithmetic", "text"]),
        cat("Programme", ["winctrl_start_app", "winctrl_open_url", "winctrl_focus_window"]),
        cat("Eingabe", ["winctrl_press_key", "winctrl_hotkey", "winctrl_type_text", "winctrl_paste_text"]),
        cat("Maus", ["winctrl_mouse_move", "winctrl_mouse_drag", "winctrl_mouse_click", "winctrl_scroll"]),
        cat("Abfragen", ["winctrl_window_exists", "winctrl_file_exists", "winctrl_clipboard"]),
        cat("Medien", ["winctrl_media"]),
        cat("System", ["winctrl_wait", "winctrl_lock_pc", "winctrl_shutdown_pc"])
    ]
};

function state() { return Blockly.serialization.workspaces.save(workspace); }
function loadState(d) { Blockly.serialization.workspaces.load(d, workspace); }

function appendLog(level, message, time="") {
    const line = document.createElement("div");
    line.className = "log" + level;
    line.textContent = `${time} ${level} ${message}`;
    const box = document.getElementById("runLog");
    box.append(line);
    if (document.getElementById("autoScroll").checked) box.scrollTop = box.scrollHeight;
}
function clearRunLog() { document.getElementById("runLog").replaceChildren(); }
function toggleLog() { const b = document.getElementById("runLog"); b.hidden = !b.hidden; }

function setButtonRunning(running) {
    const btn = document.getElementById("toggleRunBtn");
    const status = document.getElementById("testStatus");
    if (!btn) return;
    if (running) {
        btn.className = "btn-stop";
        btn.innerHTML = `<span class="icon-stop"></span><span class="btn-text">Stop</span>`;
        btn.title = "Laufenden Testlauf sofort beenden (Force Stop)";
        status.textContent = "Läuft …";
        status.classList.add("is-running");
    } else {
        btn.className = "btn-play";
        btn.innerHTML = `<span class="icon-play"></span><span class="btn-text">Testlauf</span>`;
        btn.title = "Testlauf starten";
        status.classList.remove("is-running");
    }
}

function showStatus(s) {
    const names = {
        requesting: "Angefordert …",
        starting: "Startet …",
        running: "Läuft …",
        done: "Erfolgreich",
        stopped: "Abgebrochen",
        error: "Fehlgeschlagen",
        client_error: "Fehlgeschlagen"
    };
    document.getElementById("testStatus").textContent = names[s.state] || s.state;
    if (s.id) document.getElementById("runId").textContent = "Lauf " + s.id.slice(0, 8);

    for (const line of s.logs || []) {
        if (line.seq > lastSeq) {
            appendLog(line.level, line.message, line.time);
            lastSeq = line.seq;
        }
    }
    if (s.state === "client_error") appendLog("ERROR", s.error);

    if (["done", "stopped", "error", "client_error"].includes(s.state)) {
        if (s.return_value) {
            appendLog("INFO", "Rückgabewert: " + s.return_value);
        }
        setButtonRunning(false);
        currentJobId = null;
    }
}

async function handlePlayStop(btn) {
    if (currentJobId) {
        btn.disabled = true;
        appendLog("WARNING", "Force-Stop angefordert …");
        try {
            await api(`/api/tests/${currentJobId}/stop`, jsonRequest("POST", {}));
            notify("Stop-Befehl gesendet.", {kind: "warning"});
        } catch (e) {
            notify(`Stop-Fehler: ${e.message}`, {kind: "error"});
        } finally {
            btn.disabled = false;
        }
        return;
    }

    if (!workspace) return notify("Blockly nicht bereit.", {kind: "error"});
    clearRunLog();
    lastSeq = 0;
    appendLog("INFO", "Testlauf angefordert …");

    const rawTo = document.getElementById("scriptTimeout").value.trim();
    const timeoutMin = rawTo === "" ? null : parseInt(rawTo, 10);
    btn.disabled = true;

    try {
        const blocklyData = state();
        const job = await api(`/api/actions/${actionData.id}/test`, jsonRequest("POST", {
            blockly: blocklyData,
            timeout_minutes: timeoutMin
        }));
        currentJobId = job.id;
        setButtonRunning(true);
        notify("Testlauf gestartet.", {kind: "info"});

        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(async () => {
            if (!currentJobId) {
                clearInterval(pollTimer);
                return;
            }
            try {
                const s = await api(`/api/tests/${currentJobId}`);
                showStatus(s);
                if (["done", "stopped", "error"].includes(s.state)) {
                    clearInterval(pollTimer);
                    pollTimer = null;
                }
            } catch (err) {
                showStatus({state: "client_error", error: err.message, logs: []});
                clearInterval(pollTimer);
                pollTimer = null;
            }
        }, 300);

    } catch (e) {
        notify(`Start fehlgeschlagen: ${e.message}`, {kind: "error"});
        appendLog("ERROR", e.message);
        setButtonRunning(false);
    } finally {
        btn.disabled = false;
    }
}

async function saveBlockly(b) {
    if (!workspace) return;
    b.disabled = true;
    const n = notify("Speichern läuft …", {duration: 0});
    try {
        const blockly = state();
        const rawTo = document.getElementById("scriptTimeout").value.trim();
        const timeoutMin = rawTo === "" ? null : parseInt(rawTo, 10);
        await api(`/api/actions/${actionData.id}`, jsonRequest("PUT", {
            blockly,
            timeout_minutes: timeoutMin
        }));
        saved = blockly;
        actionData.timeout_minutes = timeoutMin;
        n.update("Blockly-Plan gespeichert.", "success");
    } catch (e) {
        n.update(e.message, "error");
    } finally {
        b.disabled = false;
        n.dismissAfter();
    }
}

function discardChanges() {
    if (!workspace) return;
    loadState(saved);
    const toEl = document.getElementById("scriptTimeout");
    toEl.value = (actionData.timeout_minutes !== null && actionData.timeout_minutes !== undefined) ? actionData.timeout_minutes : "";
    notify("Letzter Speicherstand wiederhergestellt.", {kind: "success"});
}

function exportBlockly() {
    if (!workspace) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(state(), null, 2)], {type: "application/json"}));
    const a = document.createElement("a");
    a.href = url;
    a.download = "aktion.blockly.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify("Blockly-Export erstellt.", {kind: "success"});
}

function init() {
    if (!window.Blockly) {
        notify("Blockly konnte nicht geladen werden — Internetverbindung/CDN prüfen.", {kind: "error", duration: 0});
        return;
    }
    Blockly.defineBlocksWithJsonArray(definitions);
    workspace = Blockly.inject("blocklyDiv", {
        toolbox,
        trashcan: true,
        scrollbars: true,
        zoom: {controls: true, wheel: true},
        grid: {spacing: 25, length: 3, colour: "#cbd5e1", snap: true}
    });
    saved = actionData.blockly;
    if (!saved?.blocks?.blocks?.length) {
        saved = {blocks: {languageVersion: 0, blocks: [
            {type: "winctrl_when", x: 50, y: 50}
        ]}};
    }
    try {
        loadState(saved);
    } catch (e) {
        notify(`Workspacefehler: ${e.message}`, {kind: "error", duration: 0});
    }
    document.getElementById("workspaceImport").onchange = async e => {
        try {
            if (!e.target.files[0]) return;
            const data = JSON.parse(await e.target.files[0].text()), backup = state();
            try {
                loadState(data.blockly || data);
            } catch (error) {
                loadState(backup);
                throw error;
            }
            notify("Blockly importiert — noch nicht gespeichert.", {kind: "success"});
        } catch (e) {
            notify(e.message, {kind: "error"});
        } finally {
            e.target.value = "";
        }
    };
    filterDigitsOnly(document.getElementById("scriptTimeout"));
    window.addEventListener("resize", () => Blockly.svgResize(workspace));
}


// WinCtrl Feature Pack: appended to definitions/toolbox BEFORE init().
action("double_click", "Doppelklick", null, 260);
action("close_window", "Fenster schließen (Titel enthält)", "Editor", 160);
action("minimize_window", "Fenster minimieren (Titel enthält)", "Editor", 160);
action("maximize_window", "Fenster maximieren (Titel enthält)", "Editor", 160);
action("volume", "Lautstärke setzen in %", "50", 120);
action("mute", "Lautstärke stumm", "on", 120, [["Ein", "on"], ["Aus", "off"]]);
action("media_next", "Medien: nächster Titel", null, 120);
action("media_previous", "Medien: vorheriger Titel", null, 120);
definitions.push({type:"winctrl_process_running",message0:"Prozess läuft %1",args0:[{type:"field_input",name:"VALUE",text:"notepad.exe"}],output:"Boolean",colour:210});
definitions.push({type:"winctrl_if_process",message0:"Wenn Prozess läuft %1",args0:[{type:"field_input",name:"VALUE",text:"notepad.exe"}],message1:"dann %1",args1:[{type:"input_statement",name:"DO"}],message2:"sonst %1",args2:[{type:"input_statement",name:"ELSE"}],previousStatement:null,nextStatement:null,colour:210});
definitions.push({type:"winctrl_wait_window",message0:"Warten bis Fenster existiert %1 maximal %2 Sekunden",args0:[{type:"field_input",name:"VALUE",text:"Editor"},{type:"field_number",name:"SECONDS",value:10,min:0,max:7200}],previousStatement:null,nextStatement:null,colour:290});
definitions.push({type:"winctrl_loop",message0:"Wiederhole bis Abbruch %1",args0:[{type:"input_statement",name:"DO"}],previousStatement:null,nextStatement:null,colour:120,tooltip:"Mit Schleife abbrechen beenden. Das Aktionszeitlimit bleibt aktiv."});
function addBlocks(category, types) {
    const c=toolbox.contents.find(c=>c.name===category);
    for(const type of types) c.contents.push({kind:"block",type});
}
addBlocks("Maus",["winctrl_double_click"]);
addBlocks("Programme",["winctrl_close_window","winctrl_minimize_window","winctrl_maximize_window","winctrl_wait_window","winctrl_if_process"]);
addBlocks("Abfragen",["winctrl_process_running"]);
addBlocks("Medien",["winctrl_volume","winctrl_mute","winctrl_media_next","winctrl_media_previous"]);
addBlocks("Schleifen",["winctrl_loop","controls_flow_statements"]);

init();
