// Single source of truth for the extension's feature toggles.
// Shared by the popup (writes settings) and the content script (applies them).
//
// Each feature maps a storage `key` to:
//   - `label`: shown in the popup
//   - `cls`:   the class toggled on <html>; content.css gates its hide rules on it

export const FEATURES = [
  {
    key: 'hideRecommendations',
    label: 'Recommendations sidebar',
    description: 'Hide the related-videos sidebar on watch pages.',
    cls: 'yfm-hide-recommendations',
  },
  {
    key: 'hideHomeFeed',
    label: 'Homepage feed',
    description: 'Hide the video grid on the YouTube home page.',
    cls: 'yfm-hide-home',
  },
  {
    key: 'hideShorts',
    label: 'Shorts',
    description: 'Hide Shorts shelves and the Shorts nav entry.',
    cls: 'yfm-hide-shorts',
  },
  {
    key: 'hideComments',
    label: 'Comments',
    description: 'Hide the comments section under videos.',
    cls: 'yfm-hide-comments',
  },
  {
    key: 'hideEndScreen',
    label: 'End-screen suggestions',
    description: 'Hide the suggested-video cards shown at the end of playback.',
    cls: 'yfm-hide-endscreen',
  },
];

// Every feature defaults to ON (distractions hidden out of the box).
export const DEFAULTS = Object.fromEntries(FEATURES.map((f) => [f.key, true]));

// Promise wrapper around chrome.storage.sync.get, seeded with DEFAULTS so
// missing keys come back as `true` rather than `undefined`.
export function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(DEFAULTS, (stored) => resolve(stored));
  });
}

// Persist a partial settings object (e.g. { hideShorts: false }).
export function saveSettings(partial) {
  return new Promise((resolve) => {
    chrome.storage.sync.set(partial, resolve);
  });
}
