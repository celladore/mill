import { useMemo, useState } from 'react';

const FILTERS = ['all', 'document', 'text', 'image', 'audio', 'transcript'];

function formatTime(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime())
    ? 'Just now'
    : new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(date);
}

function formatKilobytes(value) {
  if (!Number.isFinite(value)) return null;
  return value >= 1024 ? `${(value / 1024).toFixed(1)} MB` : `${value.toFixed(1)} KB`;
}

export function TransformationHistory({ items, loading, error, onRefresh, onDownload }) {
  const [filter, setFilter] = useState('all');
  const visible = useMemo(
    () => items.filter(item => filter === 'all' || item.kind === filter),
    [filter, items]
  );

  return (
    <aside className="history-ledger" aria-labelledby="history-heading">
      <div className="history-heading-row">
        <div>
          <p className="eyebrow">Activity ledger</p>
          <h2 id="history-heading">Transformation history</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={onRefresh}
          aria-label="Refresh history"
        >
          ↻
        </button>
      </div>
      <div className="history-filters" aria-label="Filter history">
        {FILTERS.map(value => (
          <button
            type="button"
            key={value}
            onClick={() => setFilter(value)}
            aria-pressed={filter === value}
          >
            {value}
          </button>
        ))}
      </div>
      {loading && (
        <p className="history-state" role="status">
          Loading your activity…
        </p>
      )}
      {error && (
        <p className="history-state history-error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && visible.length === 0 && (
        <div className="history-empty">
          <span>00</span>
          <p>No transformations here yet.</p>
          <small>Your completed work will stay available in this private ledger.</small>
        </div>
      )}
      <ol className="history-list">
        {visible.map(item => (
          <li key={`${item.retained === false ? 'session' : 'saved'}-${item.kind}-${item.id}`}>
            <div className="history-item-top">
              <span className={`kind-chip kind-${item.kind}`}>{item.kind}</span>
              <time dateTime={item.timestamp}>{formatTime(item.timestamp)}</time>
            </div>
            <strong title={item.filename}>{item.filename}</strong>
            <div className="history-route">
              {(item.input_format || item.kind).toUpperCase()}
              <span>→</span>
              {(item.output_format || 'file').toUpperCase()}
            </div>
            <div className="history-meta">
              <span className={item.success ? 'status-success' : 'status-failed'}>
                {item.success ? 'Complete' : 'Failed'}
              </span>
              {item.retained === false && <span className="session-chip">This session</span>}
              {item.detail && <span>{item.detail}</span>}
              {item.kind === 'image' && item.input_size_kb != null && (
                <span>
                  {formatKilobytes(item.input_size_kb)} → {formatKilobytes(item.output_size_kb)}
                </span>
              )}
              {item.kind === 'image' && item.quality && (
                <span>
                  {item.quality === 'custom' ? 'Custom' : item.quality} quality
                  {item.quality_value ? ` · ${item.quality_value}%` : ''}
                </span>
              )}
              {item.downloadable && (
                <button type="button" onClick={() => onDownload(item)}>
                  Download
                </button>
              )}
            </div>
          </li>
        ))}
      </ol>
    </aside>
  );
}
