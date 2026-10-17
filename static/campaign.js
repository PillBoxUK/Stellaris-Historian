const appVersion = document.getElementById("app-version");
const title = document.getElementById("campaign-title");
const empireName = document.getElementById("empire-name");
const gameDate = document.getElementById("game-date");
const archiveCount = document.getElementById("archive-count");
const unprocessedCount = document.getElementById("unprocessed-count");
const processedCount = document.getElementById("processed-count");
const monitorStatus = document.getElementById("monitor-status");
const archiveList = document.getElementById("archive-list");
const status = document.getElementById("status");
const selectCampaignButton = document.getElementById("select-new-campaign");
const updateButton = document.getElementById("update-history");
const liveHistoryButton = document.getElementById("live-history");
const reviewButton = document.getElementById("review-campaign");
const rewriteTimelineButton = document.getElementById("rewrite-timeline");
const constructButton = document.getElementById("construct-campaign");
const constructModal = document.getElementById("construct-modal");
const constructCancel = document.getElementById("construct-cancel");
const constructConfirm = document.getElementById("construct-confirm");
const openCampaignFolderButton = document.getElementById("open-campaign-folder");
const openDiagnosticsFolderButton = document.getElementById("open-diagnostics-folder");
const closeButton = document.getElementById("close-app");

let actionInProgress = false;
let latestCampaignState = null;

function applyActionAvailability(data = latestCampaignState){
  if(!data){
    return;
  }

  latestCampaignState = data;

  const unprocessed = Number(data.unprocessed_count ?? 0);
  const archived = Number(data.archive_count ?? 0);
  const liveEnabled = Boolean(data.live_history_enabled);
  const liveBusy = Boolean(data.live_history_busy);
  const liveBlocking = liveEnabled || liveBusy;

  selectCampaignButton.disabled = actionInProgress || liveBusy;
  selectCampaignButton.title = liveBusy
    ? "Wait for the current Live History update to finish before selecting another campaign."
    : "Stop monitoring this campaign and return to campaign selection.";

  updateButton.disabled =
    actionInProgress || liveBlocking || unprocessed === 0;

  liveHistoryButton.disabled = actionInProgress;

  reviewButton.disabled =
    actionInProgress || liveBlocking || unprocessed > 0 || archived === 0;

  rewriteTimelineButton.disabled = actionInProgress || liveBlocking || unprocessed > 0 || archived === 0;
  constructButton.disabled =
    actionInProgress || liveBlocking || archived === 0;

  // Reading the existing archive stays accessible while fresh saves finish.
  document.getElementById("historian-library").hidden = archived === 0;

  updateButton.title = liveBlocking
    ? "Live History is ON or finishing an automatic history update."
    : (unprocessed === 0
      ? "No archived saves are waiting for history."
      : `Process ${unprocessed} archived save(s) waiting for history.`);

  liveHistoryButton.textContent = liveEnabled
    ? "Live History: ON"
    : (liveBusy ? "Live History: STOPPING" : "Live History: OFF");
  liveHistoryButton.classList.toggle("live-on", liveEnabled);
  liveHistoryButton.setAttribute("aria-pressed", liveEnabled ? "true" : "false");
  liveHistoryButton.title = data.live_history_status || (liveEnabled ? "Live History is ON." : "Live History is OFF.");

  reviewButton.title = liveBlocking
    ? "Wait for Live History to be fully OFF before running Review Campaign."
    : (unprocessed > 0
      ? `Run Update History first. ${unprocessed} archived save(s) are waiting for history.`
      : "Re-read the full processed campaign using the current Historian logic.");

  constructButton.title = liveBlocking
    ? "Wait for Live History to be fully OFF before constructing the campaign."
    : (archived > 0
      ? "Discard generated analysis/cache and rebuild the campaign from every archived save."
      : "No archived saves are available to construct.");
}

function escapeHtml(value){
  return String(value ?? "").replace(
    /[&<>"']/g,
    ch => ({
      "&":"&amp;",
      "<":"&lt;",
      ">":"&gt;",
      "\"":"&quot;",
      "'":"&#39;"
    }[ch])
  );
}

async function loadActive(){
  try{
    const response = await fetch(
      "/api/active-campaign",
      {cache:"no-store"}
    );

    const data = await response.json();
    window.HistorianFavicon?.fromData(data);

    if(appVersion && data.version){
      appVersion.textContent = data.version;
    }

    if(!data.campaign){
      window.location.href = "/";
      return;
    }

    const campaign = data.campaign;

    title.textContent =
      `${campaign.empire_name} - ${campaign.latest_game_date}`;

    empireName.textContent = campaign.empire_name;
    gameDate.textContent = campaign.latest_game_date || "--";
    archiveCount.textContent = data.archive_count ?? 0;
    unprocessedCount.textContent = data.unprocessed_count ?? 0;
    processedCount.textContent = data.processed_count ?? 0;
    monitorStatus.textContent = data.watcher_status || "Monitoring";

    applyActionAvailability(data);

    const snapshots = data.snapshots || [];

    archiveList.innerHTML = snapshots.length
      ? snapshots.map(snapshot => `
          <div class="archive-row">
            <strong>${escapeHtml(snapshot.archive_filename)}</strong>
            <span>${escapeHtml(snapshot.game_date)}</span>
            <span>${snapshot.processed ? "Processed" : "Waiting for history"}</span>
          </div>
        `).join("")
      : "Waiting for the first stable save to be archived.";
  }catch(error){
    window.HistorianFavicon?.offline();
    status.textContent =
      `Could not refresh campaign status: ${error}`;
  }
}

selectCampaignButton.addEventListener("click", async () => {
  actionInProgress = true;
  applyActionAvailability();
  status.textContent = "Stopping campaign monitoring and returning to campaign selection...";

  try{
    const response = await fetch("/api/select-new-campaign", {method:"POST"});
    const data = await response.json();
    if(!response.ok){
      throw new Error(data.detail || "Could not return to campaign selection.");
    }
    window.location.href = data.redirect || "/";
  }catch(error){
    status.textContent = `Could not select a new campaign: ${error.message}`;
    actionInProgress = false;
    applyActionAvailability();
  }
});

liveHistoryButton.addEventListener("click", async () => {
  const currentlyEnabled = Boolean(latestCampaignState?.live_history_enabled);
  actionInProgress = true;
  applyActionAvailability();
  status.textContent = `${currentlyEnabled ? "Turning off" : "Turning on"} Live History...`;

  try{
    const response = await fetch(
      "/api/live-history",
      {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({enabled:!currentlyEnabled})
      }
    );
    const data = await response.json();
    if(!response.ok){
      throw new Error(data.detail || "Could not change Live History state.");
    }
    status.textContent = data.enabled
      ? "Live History is ON. New archived saves will be processed automatically."
      : (data.busy
        ? "Live History is stopping after the current automatic history update finishes."
        : "Live History is OFF. Update History is manual again.");
    await loadActive();
  }catch(error){
    status.textContent = `Live History toggle failed: ${error.message}`;
  }finally{
    actionInProgress = false;
    applyActionAvailability();
  }
});

updateButton.addEventListener("click", async () => {
  actionInProgress = true;
  applyActionAvailability();
  updateButton.textContent = "Processing...";
  status.textContent =
    "Processing unprocessed archived saves...";

  try{
    const response = await fetch(
      "/api/update-history",
      {method:"POST"}
    );

    const data = await response.json();

    if(!response.ok){
      throw new Error(
        data.detail || "History update failed."
      );
    }

    status.textContent = data.message;

    if(data.errors && data.errors.length){
      status.textContent +=
        ` Errors: ${data.errors.join(" | ")}`;
    }


    await loadActive();

  }catch(error){
    status.textContent =
      `History update failed: ${error.message}`;

  }finally{
    actionInProgress = false;
    updateButton.textContent = "Update History";
    applyActionAvailability();
  }
});

reviewButton.addEventListener("click", async () => {
  actionInProgress = true;
  applyActionAvailability();
  reviewButton.textContent = "Reviewing...";
  status.textContent =
    "Reviewing every archived save in this campaign...";

  try{
    const response = await fetch(
      "/api/review-campaign",
      {method:"POST"}
    );

    const data = await response.json();

    if(!response.ok){
      throw new Error(
        data.detail || "Review Campaign failed."
      );
    }

    status.textContent = data.message;

    if(data.errors && data.errors.length){
      status.textContent +=
        ` Errors: ${data.errors.join(" | ")}`;
    }

    if(data.ok){
      }

    await loadActive();

  }catch(error){
    status.textContent =
      `Review Campaign failed: ${error.message}`;

  }finally{
    actionInProgress = false;
    reviewButton.textContent = "Review Campaign";
    applyActionAvailability();
  }
});


function openConstructModal(){
  constructModal.hidden = false;
  constructConfirm.focus();
}

function closeConstructModal(){
  constructModal.hidden = true;
  constructButton.focus();
}

constructButton.addEventListener("click", () => {
  openConstructModal();
});

constructCancel.addEventListener("click", () => {
  closeConstructModal();
});

constructModal.addEventListener("click", event => {
  if(event.target === constructModal){
    closeConstructModal();
  }
});

document.addEventListener("keydown", event => {
  if(event.key === "Escape" && !constructModal.hidden){
    closeConstructModal();
  }
});

constructConfirm.addEventListener("click", async () => {
  constructModal.hidden = true;

  actionInProgress = true;
  applyActionAvailability();

  constructButton.textContent = "Constructing...";
  status.textContent =
    "Constructing campaign from every archived save. This can take a long time...";

  try{
    const response = await fetch(
      "/api/construct-campaign",
      {method:"POST"}
    );

    const data = await response.json();

    if(!response.ok){
      throw new Error(
        data.detail || "Construct Campaign failed."
      );
    }

    status.textContent = data.message;

    if(data.errors && data.errors.length){
      status.textContent +=
        ` Errors: ${data.errors.join(" | ")}`;
    }

    if(data.ok){
      }

    await loadActive();

  }catch(error){
    status.textContent =
      `Construct Campaign failed: ${error.message}`;

  }finally{
    actionInProgress = false;
    constructButton.textContent = "Construct Campaign";
    applyActionAvailability();
  }
});

async function openFolder(endpoint, label){
  status.textContent = `Opening ${label}...`;

  try{
    const response = await fetch(endpoint, {method:"POST"});
    const data = await response.json();

    if(!response.ok){
      throw new Error(data.detail || `Could not open ${label}.`);
    }

    status.textContent = `${label} opened: ${data.path}`;
  }catch(error){
    status.textContent = `Could not open ${label}: ${error.message}`;
  }
}

openCampaignFolderButton.addEventListener("click", () => {
  openFolder("/api/open-campaign-folder", "campaign folder");
});

openDiagnosticsFolderButton.addEventListener("click", () => {
  openFolder("/api/open-diagnostics-folder", "diagnostics folder");
});

closeButton.addEventListener("click", () => window.HistorianClose(closeButton, status));

loadActive();
setInterval(loadActive, 2000);

// Full historical reconstruction runs in the background after a SQLite backup.
rewriteTimelineButton.addEventListener('click', async () => {
  if (actionInProgress) return;
  if (!confirm('Rebuild the complete historical timeline from every archived save? The canonical database is backed up first; current evidence parsers will re-derive the historical registers. This can take several minutes. Keep Live History OFF.')) return;
  actionInProgress = true;
  rewriteTimelineButton.textContent = 'Rebuilding History…';
  applyActionAvailability();
  try {
    const start = await fetch('/api/rewrite-timeline', {method:'POST'});
    const first = await start.json();
    if (!start.ok) throw new Error(first.detail || 'Could not start the rewrite.');
    let complete = false;
    while (!complete) {
      await new Promise(resolve => setTimeout(resolve, 800));
      const req = await fetch('/api/rewrite-timeline/status', {cache:'no-store'});
      const item = await req.json();
      status.textContent = `${item.message} ${item.total ? `(${item.progress}/${item.total})` : ''}`;
      if (!item.running) {
        complete = true;
        if (item.error) throw new Error(item.error);
        status.textContent = `${item.message} ${item.result?.archived_saves_inspected ?? 0} archived saves checked. Open Empire Timeline to read it.`;
      }
    }
  } catch (err) {
    status.textContent = `Timeline rewrite: ${err.message}`;
  } finally {
    actionInProgress = false;
    rewriteTimelineButton.textContent = 'Update Historical Timeline';
    applyActionAvailability();
  }
});

document.getElementById('save-stellaris-game-folder').addEventListener('click', async ()=> {
  const field=document.getElementById('stellaris-game-folder');
  const button=document.getElementById('save-stellaris-game-folder');
  button.disabled=true;
  try{
    const req=await fetch('/api/stellaris-game-folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folder:field.value})});
    const data=await req.json();
    if(!req.ok) throw new Error(data.detail || 'Could not load game texts');
    status.textContent=`Game text catalogue ready: ${data.catalogue.localisation_keys} entries. Run Rewrite Timeline to incorporate story descriptions.`;
  }catch(err){status.textContent=`Game texts: ${err.message}`;}
  finally{button.disabled=false;}
});
