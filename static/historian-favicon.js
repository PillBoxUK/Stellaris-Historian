/* Stellaris Historian v0.0.56 - live browser-tab status, no external assets. */
(() => {
  "use strict";
  const colours = {on:"#29bd73", off:"#db4851", busy:"#ecb34a", offline:"#89939d"};
  let last = "";
  let inflight = false;
  function setIcon(state) {
    if (state === last || !colours[state]) return;
    last = state;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect x="2" y="2" width="60" height="60" rx="14" fill="#111822"/><path d="M32 9 52 21v22L32 55 12 43V21z" fill="none" stroke="${colours[state]}" stroke-width="5"/><circle cx="32" cy="32" r="11" fill="${colours[state]}"/><circle cx="32" cy="32" r="4" fill="#111822"/></svg>`;
    let link = document.querySelector('link[data-historian-favicon]');
    if (!link) {link = document.createElement('link'); link.rel = 'icon'; link.type = 'image/svg+xml'; link.dataset.historianFavicon = '1'; document.head.appendChild(link);}
    link.href = 'data:image/svg+xml,' + encodeURIComponent(svg);
    link.title = 'Historian: ' + (state === 'on' ? 'Live History ON' : state === 'off' ? 'Live History OFF' : state === 'busy' ? 'Processing' : 'Connection lost');
  }
  function fromData(data) {
    if (!data || !data.campaign) { setIcon('off'); return; }
    setIcon(data.live_history_busy ? 'busy' : data.live_history_enabled ? 'on' : 'off');
  }
  async function poll() {
    if (inflight) return;
    inflight = true;
    try {
      const response = await fetch('/api/active-campaign', {cache:'no-store', signal: AbortSignal.timeout(3500)});
      if (!response.ok) throw new Error('Status unavailable');
      fromData(await response.json());
    } catch (_) { setIcon('offline'); }
    finally { inflight = false; }
  }
  window.HistorianFavicon = {fromData, offline: () => setIcon('offline'), poll};
  setIcon('offline');
  poll();
  setInterval(poll, 5000);
})();
