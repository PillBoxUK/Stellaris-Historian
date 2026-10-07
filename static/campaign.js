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
const updateButton = document.getElementById("update-history");
const reviewButton = document.getElementById("review-campaign");
const constructButton = document.getElementById("construct-campaign");
const constructModal = document.getElementById("construct-modal");
const constructCancel = document.getElementById("construct-cancel");
const constructConfirm = document.getElementById("construct-confirm");
const viewJournalButton = document.getElementById("view-journal");
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

  updateButton.disabled =
    actionInProgress || unprocessed === 0;

  reviewButton.disabled =
    actionInProgress || unprocessed > 0 || archived === 0;

  constructButton.disabled =
    actionInProgress || archived === 0;

  updateButton.title = unprocessed === 0
    ? "No archived saves are waiting for history."
    : `Process ${unprocessed} archived save(s) waiting for history.`;

  reviewButton.title = unprocessed > 0
    ? `Run Update History first. ${unprocessed} archived save(s) are waiting for history.`
    : "Re-read the full processed campaign using the current Historian logic.";

  constructButton.title = archived > 0
    ? "Discard generated analysis/cache and rebuild the campaign from every archived save."
    : "No archived saves are available to construct.";
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

    viewJournalButton.disabled = !data.journal_exists;
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
    status.textContent =
      `Could not refresh campaign status: ${error}`;
  }
}

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

    viewJournalButton.disabled = false;

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
      viewJournalButton.disabled = false;
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
  viewJournalButton.disabled = true;

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
      viewJournalButton.disabled = false;
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

viewJournalButton.addEventListener("click", () => {
  window.open(
    "/journal",
    "_blank",
    "noopener"
  );
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

closeButton.addEventListener("click", async () => {
  closeButton.disabled = true;
  closeButton.textContent = "Closing...";

  try{
    await fetch(
      "/app/close",
      {method:"POST"}
    );
  }catch{}

  status.textContent =
    "Historian closed. You can close this browser tab.";
});

loadActive();
setInterval(loadActive, 2000);
