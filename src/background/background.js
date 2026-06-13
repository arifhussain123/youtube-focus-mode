// Background service worker.
//
// Why this exists: content scripts run in the youtube.com page context and
// cannot reliably POST to localhost (page CSP + CORS). The service worker has
// host_permissions for the API, so the content script forwards watch events
// here and this worker does the actual network call.

import { API_BASE } from '../common/config.js';

// Events that failed to send (e.g. backend offline) wait here and are retried
// with the next incoming batch. In-memory only — best-effort for v1.
let retryQueue = [];

async function postEvents(events) {
  if (events.length === 0) return true;
  try {
    const res = await fetch(`${API_BASE}/api/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events }),
    });
    return res.ok;
  } catch (err) {
    // Backend is likely just not running — don't crash the worker.
    console.debug('[YFM] event POST failed, will retry later:', err.message);
    return false;
  }
}

async function flush(incoming) {
  const batch = retryQueue.concat(incoming);
  retryQueue = [];
  const ok = await postEvents(batch);
  if (!ok) {
    // Keep the batch for next time, but cap it so it can't grow unbounded.
    retryQueue = batch.slice(-500);
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'watch' && Array.isArray(message.events)) {
    // Respond immediately; do the network work asynchronously.
    flush(message.events);
    sendResponse({ received: message.events.length });
  }
  // Returning false: we've already responded synchronously above.
  return false;
});
