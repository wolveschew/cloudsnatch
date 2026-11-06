const form = document.getElementById("export-form");
const input = document.getElementById("profile-url");
const start = document.getElementById("start");
const retry = document.getElementById("retry");
const statusText = document.getElementById("status-text");
const pill = document.getElementById("status-pill");
const bar = document.getElementById("progress-bar");
const errorBox = document.getElementById("error-box");
const accentSetting = document.getElementById("accent-setting");
const compactSetting = document.getElementById("compact-setting");
const folderButtons = [
  document.getElementById("likes-folder"),
  document.getElementById("playlists-folder"),
];
const writePreview = document.querySelector(".write-preview");
const previewStatus = document.getElementById("preview-status");
const jsonPreview = document.getElementById("json-preview");
const csvPreview = document.getElementById("csv-preview");
let timer;
let initialized = false;
let hasSeenLatestItem = false;
let appearanceSaveQueue = Promise.resolve();

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function setCategory(category, item = {}) {
  const state = document.getElementById(`${category}-state`);
  if (!state) return;
  const status = item.status || "Waiting";
  const count = Number.isFinite(item.count) ? ` · ${item.count.toLocaleString()} items` : "";
  const detail = item.error || item.reason;
  state.textContent = detail ? `${status}${count} · ${detail}` : `${status}${count}`;
  state.title = detail || state.textContent;
  state.classList.toggle("error-state", status === "failed");
  if (category !== "likes" && category !== "playlists") return;
}

function showReport(report) {
  if (!report || !report.categories) return;
  setCategory("likes", report.categories.likes);
  setCategory("playlists", report.categories.playlists);
  const following = report.categories.followings || {
    status: "unsupported",
    reason: "No verified public method is supported.",
  };
  document.getElementById("following-state").textContent =
    following.status === "unsupported"
      ? `Unsupported — ${following.reason || "no verified public method"}`
      : following.reason || "Unsupported — no verified public method";
  if (!input.value && report.profile_url) input.value = report.profile_url;
}

function showProgress(categories) {
  for (const category of ["likes", "playlists", "followings"]) {
    if (categories && categories[category]) setCategory(category, categories[category]);
  }
}

function showLatestItem(item) {
  if (!item) return;
  if (!hasSeenLatestItem) {
    writePreview.open = true;
    hasSeenLatestItem = true;
  }
  previewStatus.textContent =
    `${item.category} · item ${Number(item.count || 0).toLocaleString()} · ` +
    `${item.checkpoint ? "CSV and JSON checkpoint saved" : "CSV saved; JSON checkpoint pending"} · ${item.title}`;
  jsonPreview.textContent = (item.json || "No JSON preview available.") +
    (item.json_truncated ? "\n… preview shortened; open the account folder to inspect the full file." : "");
  csvPreview.textContent = item.csv || "No CSV row available.";
}

async function refresh() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error(`Status request failed (${response.status}).`);
    const job = await response.json();
    statusText.textContent = job.status || "Ready";
    showProgress(job.categories);
    if (job.report) showReport(job.report);
    showLatestItem(job.latest_item);
    folderButtons.forEach(button => { button.disabled = !job.profile_url && !input.value.trim(); });
    if (job.error) showError(job.error);

    if (job.running) {
      const count = Object.values(job.categories || {}).reduce(
        (total, category) => total + (Number(category.count) || 0), 0
      );
      bar.style.width = `${Math.min(90, 12 + Math.log10(count + 1) * 22)}%`;
      return;
    }

    clearInterval(timer);
    start.disabled = false;
    bar.classList.remove("active");
    if (job.status !== "idle") {
      const failed = job.error || Object.values(job.categories || {}).some(
        category => category.status === "failed"
      );
      pill.textContent = failed ? "CHECK REPORT" : "FINISHED";
      pill.className = failed ? "pill failed" : "pill complete";
      bar.style.width = "100%";
    } else if (job.report) {
      pill.textContent = "SAVED";
      pill.className = "pill complete";
    }
    if (!initialized && job.report) showReport(job.report);
    initialized = true;
  } catch (error) {
    statusText.textContent = "Could not read the local exporter status.";
    showError(error instanceof Error ? error.message : String(error));
  }
}

async function launch(force) {
  errorBox.classList.add("hidden");
  hasSeenLatestItem = false;
  jsonPreview.textContent = "Waiting for an item…";
  csvPreview.textContent = "Waiting for an item…";
  previewStatus.textContent = "Preparing the collection export.";
  try {
    const response = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.value, retry: force }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Could not start export (${response.status}).`);
    start.disabled = true;
    pill.textContent = "WORKING";
    pill.className = "pill working";
    bar.classList.add("active");
    bar.style.width = "12%";
    clearInterval(timer);
    timer = setInterval(refresh, 2000);
    await refresh();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

async function openAccountFolder() {
  errorBox.classList.add("hidden");
  try {
    const response = await fetch("/api/open-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Could not open folder (${response.status}).`);
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

async function loadAppearance() {
  try {
    const response = await fetch("/api/settings");
    const settings = await response.json();
    if (!response.ok) throw new Error(settings.error || `Settings request failed (${response.status}).`);
    accentSetting.value = settings.accent;
    document.body.dataset.accent = settings.accent;
    compactSetting.checked = settings.compact;
    document.body.classList.toggle("compact", settings.compact);
  } catch (error) {
    showError(`Could not load appearance preferences: ${error.message}`);
  }
}

function saveAppearance() {
  const settings = { accent: accentSetting.value, compact: compactSetting.checked };
  appearanceSaveQueue = appearanceSaveQueue.then(async () => {
    try {
      const response = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Settings request failed (${response.status}).`);
      if (errorBox.textContent.startsWith("Could not save appearance preferences:")) {
        errorBox.classList.add("hidden");
      }
    } catch (error) {
      showError(`Could not save appearance preferences: ${error.message}`);
    }
  });
  return appearanceSaveQueue;
}

accentSetting.addEventListener("change", () => {
  document.body.dataset.accent = accentSetting.value;
  saveAppearance();
});

compactSetting.addEventListener("change", () => {
  document.body.classList.toggle("compact", compactSetting.checked);
  saveAppearance();
});

form.addEventListener("submit", event => {
  event.preventDefault();
  launch(false);
});
retry.addEventListener("click", () => launch(true));
folderButtons.forEach(button => button.addEventListener("click", openAccountFolder));
input.addEventListener("input", () => {
  folderButtons.forEach(button => { button.disabled = !input.value.trim(); });
});

loadAppearance();
refresh();
