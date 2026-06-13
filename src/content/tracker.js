// Watch-time tracker.
//
// Counts only ACTIVE viewing: the tab must be visible AND a <video> element
// must be playing. Idle, paused, or background-tab time is not counted, so the
// numbers reflect real attention rather than "left the tab open".
//
// Accumulated seconds are batched per video and handed to the background
// service worker (chrome.runtime.sendMessage), which forwards them to the API.

const TICK_MS = 5000; // how often we sample playback state
const TICK_SECONDS = TICK_MS / 1000;
const FLUSH_MS = 15000; // how often we ship accumulated time to the backend

// videoId -> { title, channel, seconds } accumulated since the last flush.
const pending = new Map();

function currentVideoId() {
  if (location.pathname !== '/watch') return null;
  return new URLSearchParams(location.search).get('v');
}

function currentTitle() {
  // document.title looks like "Video name - YouTube"; strip the suffix.
  return document.title.replace(/\s*-\s*YouTube\s*$/, '').trim();
}

function currentChannel() {
  // Best-effort; YouTube's DOM drifts, so treat a miss as "unknown".
  const el =
    document.querySelector('ytd-channel-name#channel-name a') ||
    document.querySelector('#owner #channel-name a') ||
    document.querySelector('ytd-video-owner-renderer a.yt-formatted-string');
  const name = el?.textContent?.trim();
  return name || null;
}

function isActivelyPlaying() {
  if (document.visibilityState !== 'visible') return false;
  const video = document.querySelector('video');
  // readyState > 2 means it actually has current data (not buffering/empty).
  return Boolean(video && !video.paused && !video.ended && video.readyState > 2);
}

function tick() {
  const videoId = currentVideoId();
  if (!videoId || !isActivelyPlaying()) return;

  const entry = pending.get(videoId) || {
    title: currentTitle(),
    channel: currentChannel(),
    seconds: 0,
  };
  entry.seconds += TICK_SECONDS;
  // Refresh metadata in case it wasn't ready when first seen.
  if (!entry.channel) entry.channel = currentChannel();
  entry.title = currentTitle() || entry.title;
  pending.set(videoId, entry);
}

function flush() {
  if (pending.size === 0) return;
  const events = [];
  for (const [video_id, { title, channel, seconds }] of pending.entries()) {
    if (seconds > 0) {
      events.push({ video_id, title, channel, seconds: Math.round(seconds) });
    }
  }
  pending.clear();
  if (events.length === 0) return;

  try {
    chrome.runtime.sendMessage({ type: 'watch', events });
  } catch (err) {
    // Extension context can be invalidated on reload; ignore.
    console.debug('[YFM] sendMessage failed:', err.message);
  }
}

export function startTracking() {
  setInterval(tick, TICK_MS);
  setInterval(flush, FLUSH_MS);
  // Flush promptly when the user leaves or backgrounds the tab so we don't
  // lose the last partial interval.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush();
  });
  window.addEventListener('pagehide', flush);
}
