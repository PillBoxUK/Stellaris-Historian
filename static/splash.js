const appVersion = document.getElementById("app-version");
const limitSelect = document.getElementById("campaign-limit");
const campaignSelect = document.getElementById("campaign-select");
const startButton = document.getElementById("start-campaign");
const refreshButton = document.getElementById("refresh-campaigns");
const closeButton = document.getElementById("close-app");
const status = document.getElementById("status");

function optionLabel(campaign){
  return (
    `${campaign.empire_name} - ` +
    `${campaign.game_date} - ` +
    `${campaign.folder_name}`
  );
}

async function loadCampaigns(){
  const limit = Number(limitSelect.value || 5);

  campaignSelect.disabled = true;
  startButton.disabled = true;
  refreshButton.disabled = true;
  status.textContent = "Scanning Stellaris save folders...";

  try{
    const response = await fetch(
      `/api/recent-campaigns?limit=${limit}`,
      {cache:"no-store"}
    );

    const data = await response.json();

    if(appVersion && data.version){
      appVersion.textContent = data.version;
    }

    if(!response.ok){
      throw new Error(data.detail || "Could not scan campaigns.");
    }

    campaignSelect.innerHTML = "";
    const campaigns = data.campaigns || [];

    if(!campaigns.length){
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No valid Ironman campaigns found";
      campaignSelect.appendChild(option);
      status.textContent = `No valid saves found under ${data.save_root}`;
      return;
    }

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent =
      `Select one of your ${campaigns.length} most recent campaigns`;
    campaignSelect.appendChild(placeholder);

    for(const campaign of campaigns){
      const option = document.createElement("option");
      option.value = campaign.save_path;
      option.textContent = optionLabel(campaign);
      campaignSelect.appendChild(option);
    }

    status.textContent =
      `${campaigns.length} recent campaign(s) found.`;
  }catch(error){
    campaignSelect.innerHTML =
      '<option value="">Could not scan campaigns</option>';
    status.textContent = error.message;
  }finally{
    campaignSelect.disabled = false;
    refreshButton.disabled = false;
  }
}

campaignSelect.addEventListener("change", () => {
  startButton.disabled = !campaignSelect.value;
});

limitSelect.addEventListener("change", loadCampaigns);
refreshButton.addEventListener("click", loadCampaigns);

startButton.addEventListener("click", async () => {
  if(!campaignSelect.value){
    return;
  }

  startButton.disabled = true;
  startButton.textContent = "Starting...";

  try{
    const response = await fetch("/api/start-campaign", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        save_path:campaignSelect.value
      })
    });

    const data = await response.json();

    if(appVersion && data.version){
      appVersion.textContent = data.version;
    }

    if(!response.ok){
      throw new Error(data.detail || "Could not start campaign.");
    }

    window.location.href = data.redirect;
  }catch(error){
    status.textContent = error.message;
    startButton.disabled = false;
    startButton.textContent = "Start Campaign";
  }
});

closeButton.addEventListener("click", async () => {
  closeButton.disabled = true;
  closeButton.textContent = "Closing...";

  try{
    await fetch("/app/close", {method:"POST"});
  }catch{}

  status.textContent =
    "Historian closed. You can close this browser tab.";
});

loadCampaigns();
