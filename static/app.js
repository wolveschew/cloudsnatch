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
  document.getElementById("playlist-tracks-folder"),
];
const trackList = document.getElementById("track-list");
const trackListContent = document.getElementById("track-list-content");
const trackEmpty = document.getElementById("track-empty");
const trackCount = document.getElementById("track-count");
const snapshotCount = document.getElementById("snapshot-count");
const compareButton = document.getElementById("compare-snapshots");
const deleteSnapshotsButton = document.getElementById("delete-snapshots");
const snapshotDiff = document.getElementById("snapshot-diff");
const writePreview = document.querySelector(".write-preview");
const previewStatus = document.getElementById("preview-status");
const jsonPreview = document.getElementById("json-preview");
const csvPreview = document.getElementById("csv-preview");
let timer;
let initialized = false;
let hasSeenLatestItem = false;
let appearanceSaveQueue = Promise.resolve();
let trackIds = [];
let trackIdOffset = 0;
let snapshotProfile = "";
let snapshotTotal = 0;
let lastSnapshotId = "";
const trackRowHeight = 32;

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function setCategory(category, item = {}) {
  const state = document.getElementById(`${category}-state`);
  if (!state) return;
  const status = item.status || "Waiting";
  const count = Number.isFinite(item.count)
    ? ` · ${item.count.toLocaleString()}${Number.isFinite(item.total) ? ` / ${item.total.toLocaleString()}` : ""} items`
    : "";
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
  for (const category of ["likes", "playlists", "playlist_tracks", "followings"]) {
    if (categories && categories[category]) setCategory(category, categories[category]);
  }
}

function updateProgressBar(categories, running) {
  const values = Object.values(categories || {}).filter(item => item && item.status !== "unsupported");
  const required = ["likes", "playlists", "playlist_tracks"];
  const known = required.every(category =>
    categories?.[category] && Number.isFinite(categories[category].total) && categories[category].total >= 0
  );
  bar.classList.toggle("indeterminate", running && !known);
  if (!running && required.every(category => categories?.[category]?.status === "complete")) {
    bar.style.width = "100%";
    bar.setAttribute("aria-valuenow", "100");
  } else if (known) {
    const total = values.reduce((sum, item) => sum + item.total, 0);
    const count = values.reduce((sum, item) => sum + Math.min(item.count || 0, item.total), 0);
    const percent = total === 0 ? 100 : Math.min(100, Math.round((count / total) * 100));
    bar.style.width = `${percent}%`;
    bar.setAttribute("aria-valuenow", String(percent));
  } else if (!running) {
    bar.style.width = "0%";
    bar.setAttribute("aria-valuenow", "0");
  } else {
    bar.style.width = "34%";
    bar.removeAttribute("aria-valuenow");
  }
}

function renderTrackIds() {
  const total = trackIds.length;
  trackCount.textContent = `${total.toLocaleString()} track ${total === 1 ? "ID" : "IDs"} found`;
  trackEmpty.classList.toggle("hidden", total > 0);
  trackListContent.style.height = `${total * trackRowHeight}px`;
  trackListContent.replaceChildren();
  if (!total) return;

  const first = Math.max(0, Math.floor(trackList.scrollTop / trackRowHeight) - 6);
  const visible = Math.ceil(trackList.clientHeight / trackRowHeight) + 12;
  const last = Math.min(total, first + visible);
  for (let index = first; index < last; index += 1) {
    const item = trackIds[index];
    const row = document.createElement("div");
    row.className = "track-row";
    row.style.transform = `translateY(${index * trackRowHeight}px)`;
    const label = document.createElement("span");
    label.textContent = item.category === "playlist_tracks" ? "PLAYLIST" : "LIKE";
    label.className = "track-kind";
    const id = document.createElement("code");
    id.textContent = item.id;
    const title = document.createElement("span");
    title.className = "track-title";
    title.textContent = item.title || "Track";
    title.title = item.title || "Track";
    row.append(label, id, title);
    trackListContent.append(row);
  }
}

async function loadTrackIds() {
  let rounds = 0;
  while (rounds < 5) {
    rounds += 1;
    const response = await fetch(`/api/track-ids?after=${trackIdOffset}`);
    if (!response.ok) throw new Error(`Track ID request failed (${response.status}).`);
    const data = await response.json();
    const atBottom = trackList.scrollHeight - trackList.scrollTop - trackList.clientHeight < 48;
    if (Array.isArray(data.items) && data.items.length) trackIds.push(...data.items);
    trackIdOffset = data.next_offset;
    if (data.items && data.items.length) {
      renderTrackIds();
      if (atBottom) trackList.scrollTop = trackList.scrollHeight;
    }
    if (trackIdOffset >= data.total) break;
  }
}

async function refreshSnapshots() {
  const profile = input.value.trim();
  if (profile === snapshotProfile) return;
  snapshotProfile = profile;
  snapshotTotal = 0;
  compareButton.disabled = true;
  deleteSnapshotsButton.disabled = true;
  snapshotDiff.classList.add("hidden");
  snapshotCount.textContent = "Checking saved snapshots…";
  if (!profile) {
    snapshotCount.textContent = "Create a snapshot to start a local history.";
    return;
  }
  try {
    const response = await fetch(`/api/snapshots?url=${encodeURIComponent(profile)}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Snapshot request failed (${response.status}).`);
    snapshotTotal = result.snapshots.length;
    snapshotCount.textContent = snapshotTotal
      ? `${snapshotTotal.toLocaleString()} local ${snapshotTotal === 1 ? "snapshot" : "snapshots"} for this profile`
      : "Create a snapshot to start a local history.";
    compareButton.disabled = snapshotTotal < 2;
    deleteSnapshotsButton.disabled = snapshotTotal < 1;
  } catch (error) {
    snapshotCount.textContent = error instanceof Error ? error.message : String(error);
  }
}

async function deleteSnapshots() {
  if (!snapshotTotal || !window.confirm("Delete saved snapshot history for this profile? The current likes and playlist files will stay in place.")) {
    return;
  }
  try {
    const response = await fetch("/api/delete-snapshots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Could not clear snapshot history (${response.status}).`);
    snapshotProfile = "";
    lastSnapshotId = "";
    snapshotDiff.classList.add("hidden");
    await refreshSnapshots();
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  }
}

async function compareSnapshots() {
  snapshotDiff.classList.remove("hidden");
  snapshotDiff.textContent = "Comparing the latest snapshots…";
  try {
    const response = await fetch("/api/compare-snapshots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Snapshot comparison failed (${response.status}).`);
    const summaries = ["likes", "playlist_tracks", "playlists"].map(category => {
      const item = result.categories[category];
      if (!item.available) return `${category.replace("_", " ")}: not compared (incomplete snapshot)`;
      return `${category.replace("_", " ")}: +${item.added_count} added, −${item.removed_count} removed`;
    });
    snapshotDiff.textContent = `${result.older_snapshot.snapshot_id} → ${result.newer_snapshot.snapshot_id}\n${summaries.join(" · ")}`;
  } catch (error) {
    snapshotDiff.textContent = error instanceof Error ? error.message : String(error);
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
    `${item.id ? `ID ${item.id} · ` : ""}${item.checkpoint ? "snapshot checkpoint saved" : "CSV saved; JSON checkpoint pending"} · ${item.title}`;
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
    updateProgressBar(job.categories, job.running);
    if (job.report) showReport(job.report);
    showLatestItem(job.latest_item);
    await loadTrackIds();
    if (job.profile_url && job.profile_url !== input.value) input.value = job.profile_url;
    if (job.report && job.report.snapshot_id !== lastSnapshotId) {
      lastSnapshotId = job.report.snapshot_id || "";
      snapshotProfile = "";
    }
    await refreshSnapshots();
    folderButtons.forEach(button => { button.disabled = !job.profile_url && !input.value.trim(); });
    if (job.error) showError(job.error);

    if (job.running) return;

    clearInterval(timer);
    start.disabled = false;
    bar.classList.remove("active");
    if (job.status !== "idle") {
      const failed = job.error || Object.values(job.categories || {}).some(
        category => category.status === "failed"
      );
      pill.textContent = failed ? "CHECK REPORT" : "FINISHED";
      pill.className = failed ? "pill failed" : "pill complete";
      bar.classList.remove("indeterminate");
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
  trackIds = [];
  trackIdOffset = 0;
  trackList.scrollTop = 0;
  renderTrackIds();
  jsonPreview.textContent = "Waiting for an item…";
  csvPreview.textContent = "Waiting for an item…";
  previewStatus.textContent = "Preparing the snapshot.";
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
    bar.classList.add("indeterminate");
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
  snapshotProfile = "";
  refreshSnapshots();
});
trackList.addEventListener("scroll", renderTrackIds, { passive: true });
compareButton.addEventListener("click", compareSnapshots);
deleteSnapshotsButton.addEventListener("click", deleteSnapshots);

loadAppearance();
refresh();
