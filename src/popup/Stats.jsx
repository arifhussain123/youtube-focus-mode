import { useEffect, useState } from 'react';
import { API_BASE } from '../common/config.js';

// Seconds -> "1h 23m" / "5m" / "12s"
function formatDuration(totalSeconds) {
  const s = Math.round(totalSeconds || 0);
  if (s < 60) return `${s}s`;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

// "2026-06-13" -> "Sat" (label for the daily bars)
function weekdayLabel(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`);
  return d.toLocaleDateString(undefined, { weekday: 'short' });
}

export default function Stats() {
  const [state, setState] = useState({ status: 'loading', data: null });
  const [categorizing, setCategorizing] = useState(false);
  const [catMsg, setCatMsg] = useState('');

  function load() {
    return fetch(`${API_BASE}/api/stats/summary?days=7`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => setState({ status: 'ok', data }))
      .catch(() => setState({ status: 'offline', data: null }));
  }

  useEffect(() => {
    load();
  }, []);

  async function categorize() {
    setCategorizing(true);
    setCatMsg('');
    try {
      const res = await fetch(`${API_BASE}/api/categorize`, { method: 'POST' });
      const data = await res.json();
      if (!data.configured) {
        setCatMsg('No API key set on the backend — see README.');
      } else {
        setCatMsg(`Categorized ${data.categorized}; ${data.remaining} left.`);
        await load();
      }
    } catch {
      setCatMsg('Request failed — is the backend running?');
    } finally {
      setCategorizing(false);
    }
  }

  if (state.status === 'loading') {
    return <p className="stats__msg">Loading stats…</p>;
  }

  if (state.status === 'offline') {
    return (
      <p className="stats__msg">
        Backend offline — start the API on <code>:8000</code> to see your watch
        time. Hiding distractions still works without it.
      </p>
    );
  }

  const {
    today_seconds,
    week_seconds,
    total_seconds,
    daily,
    top_videos,
    top_channels,
    by_category = [],
  } = state.data;
  const maxDay = Math.max(1, ...daily.map((d) => d.seconds));
  const maxCat = Math.max(1, ...by_category.map((c) => c.seconds));

  return (
    <div className="stats">
      <div className="stats__totals">
        <div className="stat-card">
          <span className="stat-card__value">{formatDuration(today_seconds)}</span>
          <span className="stat-card__label">Today</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__value">{formatDuration(week_seconds)}</span>
          <span className="stat-card__label">This week</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__value">{formatDuration(total_seconds)}</span>
          <span className="stat-card__label">All time</span>
        </div>
      </div>

      <h2 className="stats__heading">Last 7 days</h2>
      <div className="chart" role="img" aria-label="Daily watch time, last 7 days">
        {daily.map((d) => (
          <div key={d.date} className="chart__col" title={`${formatDuration(d.seconds)}`}>
            <div className="chart__bar-track">
              <div
                className="chart__bar"
                style={{ height: `${(d.seconds / maxDay) * 100}%` }}
              />
            </div>
            <span className="chart__label">{weekdayLabel(d.date)}</span>
          </div>
        ))}
      </div>

      <div className="stats__heading-row">
        <h2 className="stats__heading">By category</h2>
        <button
          type="button"
          className="cat-btn"
          onClick={categorize}
          disabled={categorizing}
        >
          {categorizing ? 'Categorizing…' : 'Categorize'}
        </button>
      </div>
      {catMsg && <p className="stats__msg">{catMsg}</p>}
      {by_category.length > 0 ? (
        <ul className="toplist">
          {by_category.map((c) => (
            <li key={c.category} className="cat-row">
              <span className="cat-row__name">{c.category}</span>
              <span className="cat-row__bar-track">
                <span
                  className="cat-row__bar"
                  style={{ width: `${(c.seconds / maxCat) * 100}%` }}
                />
              </span>
              <span className="toplist__value">{formatDuration(c.seconds)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="stats__msg">No watch data yet.</p>
      )}

      {top_videos.length > 0 && (
        <>
          <h2 className="stats__heading">Top videos</h2>
          <ul className="toplist">
            {top_videos.map((v) => (
              <li key={v.video_id} className="toplist__row">
                <span className="toplist__name" title={v.title}>
                  {v.title || v.video_id}
                </span>
                <span className="toplist__value">{formatDuration(v.seconds)}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {top_channels.length > 0 && (
        <>
          <h2 className="stats__heading">Top channels</h2>
          <ul className="toplist">
            {top_channels.map((c) => (
              <li key={c.channel} className="toplist__row">
                <span className="toplist__name" title={c.channel}>
                  {c.channel}
                </span>
                <span className="toplist__value">{formatDuration(c.seconds)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
