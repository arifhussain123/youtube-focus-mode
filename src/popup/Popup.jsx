import { useEffect, useState } from 'react';
import { FEATURES, DEFAULTS, getSettings, saveSettings } from '../common/settings.js';
import Stats from './Stats.jsx';

function FocusTab() {
  const [settings, setSettings] = useState(DEFAULTS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getSettings().then((stored) => {
      setSettings(stored);
      setLoaded(true);
    });
  }, []);

  function toggle(key) {
    const next = !settings[key];
    setSettings((prev) => ({ ...prev, [key]: next }));
    saveSettings({ [key]: next });
  }

  return (
    <ul className="feature-list">
      {FEATURES.map((feature) => (
        <li key={feature.key} className="feature">
          <label className="feature__label" htmlFor={feature.key}>
            <span className="feature__name">{feature.label}</span>
            <span className="feature__desc">{feature.description}</span>
          </label>
          <button
            id={feature.key}
            type="button"
            role="switch"
            aria-checked={Boolean(settings[feature.key])}
            className={`switch ${settings[feature.key] ? 'switch--on' : ''}`}
            onClick={() => toggle(feature.key)}
            disabled={!loaded}
          >
            <span className="switch__knob" />
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function Popup() {
  const [tab, setTab] = useState('focus');

  return (
    <div className="popup">
      <header className="popup__header">
        <h1 className="popup__title">YouTube Focus Mode</h1>
      </header>

      <nav className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'focus'}
          className={`tab ${tab === 'focus' ? 'tab--active' : ''}`}
          onClick={() => setTab('focus')}
        >
          Focus
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'stats'}
          className={`tab ${tab === 'stats' ? 'tab--active' : ''}`}
          onClick={() => setTab('stats')}
        >
          Stats
        </button>
      </nav>

      <main className="popup__body">
        {tab === 'focus' ? <FocusTab /> : <Stats />}
      </main>
    </div>
  );
}
