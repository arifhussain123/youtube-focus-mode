// Content script: reflects the user's settings onto <html> as classes.
// content.css (loaded via the manifest) contains the actual hide rules,
// each gated on one of these classes. Toggling a class shows/hides the
// corresponding YouTube section instantly, no page reload required.

import { FEATURES, getSettings } from '../common/settings.js';
import { startTracking } from './tracker.js';

const root = document.documentElement;

// Map storage key -> class name for quick lookup on change events.
const KEY_TO_CLASS = Object.fromEntries(FEATURES.map((f) => [f.key, f.cls]));

function applyFeature(key, enabled) {
  const cls = KEY_TO_CLASS[key];
  if (cls) root.classList.toggle(cls, Boolean(enabled));
}

function applyAll(settings) {
  for (const { key } of FEATURES) {
    applyFeature(key, settings[key]);
  }
}

// Initial paint from stored settings.
getSettings().then(applyAll);

// Live updates when the popup changes a setting.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'sync') return;
  for (const [key, { newValue }] of Object.entries(changes)) {
    applyFeature(key, newValue);
  }
});

// Begin recording active watch time (independent of the hide features).
startTracking();
