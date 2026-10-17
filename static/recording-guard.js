/* Stellaris Historian v0.0.85.1 — explicit per-selection recording confirmation.
   UI only: historical evidence continues to come exclusively from Ironman saves/DB. */
(() => {
  'use strict';
  const banner = document.getElementById('recording-status-banner');
  const label = document.getElementById('recording-status-label');
  const detail = document.getElementById('recording-status-detail');
  const reopen = document.getElementById('recording-status-action');
  const modal = document.getElementById('recording-confirm-modal');
  const panel = modal?.querySelector('[role="dialog"]');
  const civilisation = document.getElementById('recording-guard-civilisation');
  const yes = document.getElementById('recording-guard-yes');
  const no = document.getElementById('recording-guard-no');
  const errorBox = document.getElementById('recording-guard-error');
  if (![banner, label, detail, reopen, modal, panel, civilisation, yes, no, errorBox].every(Boolean)) return;

  let currentCampaign = null;
  let lastAutoPrompted = null;
  let submitting = false;
  let fetching = false;
  let formerFocus = null;

  function setStatus(kind, heading, explanation, showButton) {
    banner.hidden = false;
    banner.dataset.state = kind;
    label.textContent = heading;
    detail.textContent = explanation;
    reopen.hidden = !showButton;
    reopen.textContent = kind === 'pending' ? 'Choose YES or NO' : 'Review recording choice';
  }

  function showDialog() {
    if (!currentCampaign || submitting) return;
    formerFocus = document.activeElement;
    civilisation.textContent = `Selected civilisation: ${currentCampaign.name}`;
    errorBox.hidden = true;
    errorBox.textContent = '';
    modal.hidden = false;
    document.body.classList.add('recording-dialog-open');
    yes.focus();
  }

  function hideDialog() {
    modal.hidden = true;
    document.body.classList.remove('recording-dialog-open');
    if (formerFocus && typeof formerFocus.focus === 'function') formerFocus.focus();
  }

  async function refresh() {
    if (fetching || submitting) return;
    fetching = true;
    try {
      const response = await fetch('/api/active-campaign', {cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const state = await response.json();
      if (!state?.campaign) {
        currentCampaign = null;
        hideDialog();
        banner.hidden = true;
        return;
      }
      const id = Number(state.campaign.id);
      if (!Number.isSafeInteger(id) || id <= 0) throw new Error('Invalid campaign ID');
      const changed = !currentCampaign || currentCampaign.id !== id;
      currentCampaign = {id, name: String(state.campaign.empire_name || 'Unnamed civilisation')};
      if (changed) {
        hideDialog();
        lastAutoPrompted = null;
      }

      const enabled = state.live_history_enabled === true;
      const busy = state.live_history_busy === true;
      const waiting = Number(state.unprocessed_count || 0);
      const status = String(state.live_history_status || '');
      if (enabled) {
        setStatus('on', '● LIVE HISTORY: ON',
          `${currentCampaign.name} — ${status || 'processing enabled'}. ${waiting} archived save(s) awaiting history processing.`, false);
      } else if (busy) {
        setStatus('stopping', '■ LIVE HISTORY: STOPPING',
          `${currentCampaign.name} — an in-progress history update is finishing. Do not close Historian until it completes.`, false);
      } else if (state.recording_confirmation_required === true) {
        setStatus('pending', '⚠ RECORDING DECISION REQUIRED',
          `${currentCampaign.name} — Live History is OFF. Choose YES or NO before continuing.`, true);
      } else {
        setStatus('off', '⚠ LIVE HISTORY: OFF — NOT RECORDING HISTORY',
          `${currentCampaign.name} — historical processing is disabled. Ironman save archiving may continue, but historical gaps cannot always be recovered.`, true);
      }
      if (state.recording_confirmation_required === true && lastAutoPrompted !== id) {
        lastAutoPrompted = id;
        showDialog();
      }
    } catch (err) {
      setStatus('error', '⚠ RECORDING STATUS CANNOT BE VERIFIED',
        `Historian did not return a valid campaign status (${err.message}). Check the local server before continuing gameplay.`, false);
    } finally {
      fetching = false;
    }
  }

  async function recordDecision(enabled) {
    if (submitting || !currentCampaign) return;
    submitting = true;
    yes.disabled = true;
    no.disabled = true;
    errorBox.hidden = true;
    try {
      const response = await fetch('/api/recording-decision', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({campaign_id: currentCampaign.id, enabled})
      });
      const result = await response.json();
      if (!response.ok || result.ok !== true || result.enabled !== enabled ||
          Number(result.campaign_id) !== currentCampaign.id) {
        throw new Error(result.detail || 'The server did not confirm your recording choice.');
      }
      hideDialog();
      if (enabled) {
        setStatus('on', '● LIVE HISTORY: ON',
          `${currentCampaign.name} — ${result.status}. Waiting saves: ${result.queued_saves ?? '?'}.`, false);
      } else {
        setStatus('off', '⚠ LIVE HISTORY: OFF — NOT RECORDING HISTORY',
          `${currentCampaign.name} — you selected NO. Historical processing is OFF; missing history may be unrecoverable.`, true);
      }
    } catch (err) {
      errorBox.textContent = `${err.message} Recording choice not confirmed. Please try again.`;
      errorBox.hidden = false;
    } finally {
      submitting = false;
      yes.disabled = false;
      no.disabled = false;
      await refresh();
    }
  }

  // The only routes out of this modal are the actual Yes/No choices.
  // Clicking the backdrop or pressing Escape does not dismiss a pending choice.
  panel.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { event.preventDefault(); return; }
    if (event.key !== 'Tab') return;
    const available = [yes, no].filter(button => !button.disabled);
    if (!available.length) { event.preventDefault(); return; }
    const first = available[0];
    const last = available[available.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (!modal.hidden && event.key === 'Escape') event.preventDefault();
  });
  yes.addEventListener('click', () => recordDecision(true));
  no.addEventListener('click', () => recordDecision(false));
  reopen.addEventListener('click', showDialog);
  document.getElementById('live-history')?.addEventListener('click', () => {
    // The existing campaign.js handler remains authoritative for the manual switch.
    setTimeout(refresh, 800);
  });
  refresh();
  setInterval(refresh, 4000);
})();
