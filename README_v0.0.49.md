# Stellaris Historian v0.0.49

## Campaign Navigation + First Contact Foundation

This patch starts from the tested v0.0.48.1 baseline.

### Select New Campaign

The campaign page now gets a blue **Select New Campaign** button. It sits before the current-campaign actions with a flexible spacer between them.

Selecting it turns Live History OFF, stops the save watcher monitoring the current campaign, returns to the campaign-selection page, and does not delete or rebuild campaign data. If Live History is actively processing a save, campaign switching waits until that update has finished.

### First Contact evidence foundation

Adds `diagnostics/First_Contact_Probe_Debug.txt`. The probe finds leaders entering/leaving `first_contact_system` assignments from cached history, correlates those intervals with new diplomatic relation records and communications changes, and performs targeted raw-save inspection around those windows and the recent campaign edge. Raw reads are capped at 48 saves.

This remains evidence-first. v0.0.49 does **not** invent an exact First Contact completion date, counterpart or response choice when Stellaris has not yet been proven to retain those values in a decoded structure.

### Refresh progress

Review Campaign and Construct Campaign now show 6 refresh outputs. First Contact is step 5/6 and Origin Localisation is step 6/6.

## Install

1. Stop Stellaris Historian.
2. Copy the contents of this patch folder over `G:\codex\StellarisHistorian\` and allow overwrite of `start.bat`.
3. Run `start.bat`.
4. Confirm the launcher reports `STELLARIS HISTORIAN v0.0.49`.
5. Select Commonwealth of Man and test **Select New Campaign**.
6. Re-select Commonwealth of Man, keep Live History OFF, and run **Review Campaign** once.
7. Send `diagnostics\First_Contact_Probe_Debug.txt` for the Hazaran evidence review.

**Restart required:** YES  
**Review Campaign required:** YES for the new First Contact diagnostic  
**Construct Campaign required:** NO  
**Full cache rebuild required:** NO
