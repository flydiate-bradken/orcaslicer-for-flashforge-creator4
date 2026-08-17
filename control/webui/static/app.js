const POLL_INTERVAL_MS = 3000;

const el = {
  conn: document.getElementById("conn-indicator"),
  camera: document.getElementById("camera"),
  machineInfo: document.getElementById("machine-info"),
  temps: document.getElementById("temps"),
  progressFill: document.getElementById("progress-fill"),
  progressText: document.getElementById("progress-text"),
  printStatus: document.getElementById("print-status"),
  positionText: document.getElementById("position-text"),
  lastUpdated: document.getElementById("last-updated"),
  setTempRightForm: document.getElementById("set-temp-right-form"),
  setTempRightValue: document.getElementById("set-temp-right-value"),
  setTempLeftForm: document.getElementById("set-temp-left-form"),
  setTempLeftValue: document.getElementById("set-temp-left-value"),
  setBedTempForm: document.getElementById("set-bed-temp-form"),
  setBedTempValue: document.getElementById("set-bed-temp-value"),
  tempFormResult: document.getElementById("temp-form-result"),
  ledToggle: document.getElementById("led-toggle"),
};

// "1" / "0" / null (unknown, before the first successful poll)
let ledState = null;

// Fields from M115 worth surfacing; anything else in the parsed dict is
// skipped rather than dumped wholesale, since a couple of lines (the X/Y/Z
// build-volume line in particular) don't split cleanly on ":" -- see
// server.py's parse_kv_block docstring.
const MACHINE_FIELDS = ["Machine Type", "Machine Name", "Firmware", "SN"];
const PRINT_STATUS_FIELDS = ["MachineStatus", "CurrentFile", "LED"];

function setConn(state, label) {
  el.conn.className = `badge ${state}`;
  el.conn.textContent = label;
}

function renderKv(dl, pairs) {
  dl.innerHTML = "";
  for (const [key, value] of pairs) {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = value || "–";
    dl.append(dt, dd);
  }
}

function renderTemps(temp) {
  el.temps.innerHTML = "";
  const labels = { T0: "Right (T0)", T1: "Left (T1)", B: "Bed" };
  for (const [key, vals] of Object.entries(temp)) {
    const tile = document.createElement("div");
    tile.className = "temp-tile";
    const label = document.createElement("div");
    label.className = "label";
    label.textContent = labels[key] || key;
    const value = document.createElement("div");
    value.className = "value";
    value.textContent = `${vals.current}° / ${vals.target}°`;
    tile.append(label, value);
    el.temps.append(tile);
  }
}

function renderProgress(progress) {
  const pct = progress.percent ?? 0;
  el.progressFill.style.width = `${pct}%`;
  if (progress.total) {
    el.progressText.textContent = `${progress.current} / ${progress.total} bytes (${pct}%)`;
  } else {
    el.progressText.textContent = "idle — no print running";
  }
}

function cleanPositionRaw(raw) {
  // position_raw still has the "CMD M114 Received." / "ok" framing lines
  // in it (server.py deliberately doesn't parse the X1/X2/Y/Z/A/B format
  // yet -- see PROTOCOL_NOTES.md), so just strip those two for display.
  return raw
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && l !== "ok" && !l.startsWith("CMD"))
    .join(" ");
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return { httpOk: res.ok, data };
}

// LED endpoints take no body -- server.py doesn't read one for them, so
// deliberately not sending one (unlike postJSON above) avoids leaving an
// unread request body sitting in a keep-alive connection.
async function postNoBody(url) {
  const res = await fetch(url, { method: "POST" });
  const data = await res.json();
  return { httpOk: res.ok, data };
}

function renderLedButton(status) {
  const val = status["LED"];
  if (val === "1" || val === "0") {
    ledState = val;
    el.ledToggle.textContent = val === "1" ? "Turn LED off" : "Turn LED on";
  } else {
    ledState = null;
    el.ledToggle.textContent = "Toggle LED";
  }
}

el.ledToggle.addEventListener("click", async () => {
  el.ledToggle.disabled = true;
  const turningOn = ledState !== "1"; // unknown or off -> try turning on
  try {
    const { httpOk, data } = await postNoBody(turningOn ? "/api/led-on" : "/api/led-off");
    if (!(httpOk && data.ok)) {
      alert(`LED command failed: ${data.error || "unknown error"}`);
    }
  } catch (err) {
    alert(`LED command failed: ${err}`);
  } finally {
    setTimeout(() => {
      el.ledToggle.disabled = false;
      poll();
    }, 800);
  }
});

function showTempFormResult(text, isError) {
  el.tempFormResult.textContent = text;
  el.tempFormResult.style.color = isError ? "var(--bad)" : "var(--text-dim)";
}

function makeSetTempHandler(tool, toolLabel, valueEl) {
  return async (e) => {
    e.preventDefault();
    const celsius = Number(valueEl.value);
    if (!confirm(`Set ${toolLabel} nozzle to ${celsius}°C on the real printer now?`)) {
      return;
    }
    showTempFormResult("sending...", false);
    try {
      const { httpOk, data } = await postJSON("/api/set-temp", { tool, celsius });
      if (httpOk && data.ok) {
        showTempFormResult(`OK: ${data.response || "(empty response)"}`, false);
        setTimeout(poll, 1000);
      } else {
        showTempFormResult(`Failed: ${data.error || "unknown error"}`, true);
      }
    } catch (err) {
      showTempFormResult(`Failed: ${err}`, true);
    }
  };
}

el.setTempRightForm.addEventListener("submit", makeSetTempHandler(0, "Right (T0)", el.setTempRightValue));
el.setTempLeftForm.addEventListener("submit", makeSetTempHandler(1, "Left (T1)", el.setTempLeftValue));

el.setBedTempForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const celsius = Number(el.setBedTempValue.value);
  if (!confirm(`Set bed to ${celsius}°C on the real printer now?`)) {
    return;
  }
  showTempFormResult("sending...", false);
  try {
    const { httpOk, data } = await postJSON("/api/set-bed-temp", { celsius });
    if (httpOk && data.ok) {
      showTempFormResult(`OK: ${data.response || "(empty response)"}`, false);
      setTimeout(poll, 1000);
    } else {
      showTempFormResult(`Failed: ${data.error || "unknown error"}`, true);
    }
  } catch (err) {
    showTempFormResult(`Failed: ${err}`, true);
  }
});

async function poll() {
  let data;
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    data = await res.json();
  } catch (e) {
    setConn("bad", "server unreachable");
    return;
  }

  if (!data.ok) {
    setConn("bad", `printer unreachable (${data.error || "unknown error"})`);
    return;
  }

  setConn("ok", "connected");

  renderKv(
    el.machineInfo,
    MACHINE_FIELDS.map((f) => [f, data.info[f]])
  );
  renderTemps(data.temp);
  renderProgress(data.progress);
  renderKv(
    el.printStatus,
    PRINT_STATUS_FIELDS.map((f) => [f, data.status[f]])
  );
  if (!el.ledToggle.disabled) {
    renderLedButton(data.status);
  }
  el.positionText.textContent = cleanPositionRaw(data.position_raw) || "–";

  const t = new Date(data.timestamp * 1000);
  el.lastUpdated.textContent = `last updated ${t.toLocaleTimeString()}`;
}

async function init() {
  try {
    const res = await fetch("/api/config");
    const config = await res.json();
    el.camera.src = config.camera_url;
  } catch (e) {
    // camera panel just stays blank; status polling below still works
  }

  poll();
  setInterval(poll, POLL_INTERVAL_MS);
}

init();
