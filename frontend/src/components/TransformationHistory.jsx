import { useMemo, useState } from 'react';

const FILTERS = ['all', 'document', 'text', 'generation', 'image', 'audio', 'video', 'transcript'];
const PAGE_SIZE = 6;

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
  if (value < 1) return `${Math.max(1, Math.round(value * 1024))} B`;
  return value >= 1024 ? `${(value / 1024).toFixed(1)} MB` : `${value.toFixed(1)} KB`;
}

function sizeOutcome(item) {
  if (!Number.isFinite(item.input_size_kb) || !Number.isFinite(item.output_size_kb)) return null;
  if (item.input_size_kb <= 0) return null;
  const change = Math.round((1 - item.output_size_kb / item.input_size_kb) * 100);
  return {
    label: change >= 0 ? `${change}% smaller` : `${Math.abs(change)}% larger`,
    tone: change >= 0 ? 'positive' : 'neutral',
    detail: `${formatKilobytes(item.input_size_kb)} → ${formatKilobytes(item.output_size_kb)}`,
  };
}

function outcomeFor(item) {
  const size = sizeOutcome(item);
  if (size) return size;
  if (!item.success) return { label: 'Needs attention', tone: 'failed' };
  if (item.kind === 'image') {
    return {
      label: item.width && item.height ? `${item.width} × ${item.height} px` : 'Image ready',
      detail: 'Size comparison unavailable for this record',
      tone: 'neutral',
    };
  }
  if (item.kind === 'document') return { label: 'Typeset PDF ready', tone: 'positive' };
  if (item.kind === 'text') {
    return {
      label: 'Deterministic output',
      detail: item.output_size_kb ? formatKilobytes(item.output_size_kb) : 'No generative model',
      tone: 'positive',
    };
  }
  if (item.kind === 'generation') {
    return { label: 'Governed generation', detail: 'Routed through Sluice', tone: 'governed' };
  }
  if (item.kind === 'audio') {
    return {
      label: item.detail ? `${item.detail} media preserved` : 'Audio ready',
      detail: item.output_size_kb ? formatKilobytes(item.output_size_kb) : 'Codec changed',
      tone: 'positive',
    };
  }
  if (item.kind === 'video') {
    return {
      label: item.width && item.height ? `${item.width} × ${item.height} video` : 'Video ready',
      detail:
        item.detail ||
        (item.output_size_kb ? formatKilobytes(item.output_size_kb) : 'Transcoded locally'),
      tone: 'positive',
    };
  }
  if (item.kind === 'transcript') {
    return {
      label: 'Speech extracted',
      detail: item.detail ? `Language: ${item.detail}` : 'Text ready',
      tone: 'positive',
    };
  }
  return { label: 'Output ready', tone: 'positive' };
}

export function TransformationHistory({
  items,
  loading,
  error,
  onRefresh,
  onDownload,
  onCollapse,
}) {
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter(item => {
      if (filter !== 'all' && item.kind !== filter) return false;
      if (!needle) return true;
      return [item.filename, item.kind, item.input_format, item.output_format, item.detail]
        .filter(Boolean)
        .some(value => String(value).toLowerCase().includes(needle));
    });
  }, [filter, items, query]);
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const activePage = Math.min(page, pageCount);
  const pageItems = visible.slice((activePage - 1) * PAGE_SIZE, activePage * PAGE_SIZE);
  const rangeStart = visible.length ? (activePage - 1) * PAGE_SIZE + 1 : 0;
  const rangeEnd = Math.min(activePage * PAGE_SIZE, visible.length);

  return (
    <aside id="transformation-history" className="history-ledger" aria-labelledby="history-heading">
      <div className="history-heading-row">
        <div>
          <p className="eyebrow">Activity ledger</p>
          <h2 id="history-heading">Transformation history</h2>
        </div>
        <div className="history-heading-actions">
          <button
            className="icon-button"
            type="button"
            onClick={onRefresh}
            aria-label="Refresh history"
          >
            ↻
          </button>
          {onCollapse && (
            <button type="button" onClick={onCollapse} aria-label="Collapse history">
              Collapse
            </button>
          )}
        </div>
      </div>
      <div className="history-toolbar">
        <label className="history-search">
          <span>Search</span>
          <input
            type="search"
            value={query}
            onChange={event => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="Name or format"
          />
        </label>
        <label className="history-filter">
          <span>Type</span>
          <select
            value={filter}
            onChange={event => {
              setFilter(event.target.value);
              setPage(1);
            }}
          >
            {FILTERS.map(value => (
              <option value={value} key={value}>
                {value === 'all' ? 'All activity' : value}
              </option>
            ))}
          </select>
        </label>
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
          <p>{items.length ? 'No matching transformations.' : 'No transformations here yet.'}</p>
          <small>
            {items.length
              ? 'Try another name, format, or activity type.'
              : 'Your completed work will stay available in this private ledger.'}
          </small>
        </div>
      )}
      {!loading && !error && visible.length > 0 && (
        <>
          <div className="history-count" aria-live="polite">
            Showing {rangeStart}–{rangeEnd} of {visible.length}
          </div>
          <ol className="history-list">
            {pageItems.map(item => {
              const outcome = outcomeFor(item);
              return (
                <li
                  key={`${item.retained === false ? 'session' : 'saved'}-${item.kind}-${item.id}`}
                >
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
                  <div className={`history-outcome outcome-${outcome.tone}`}>
                    <strong>{outcome.label}</strong>
                    {outcome.detail && <span>{outcome.detail}</span>}
                  </div>
                  <div className="history-meta">
                    {item.retained === false && <span className="session-chip">This session</span>}
                    {(item.kind === 'image' || item.kind === 'video') && item.quality && (
                      <span className="setting-chip">
                        {item.quality === 'custom' ? 'Custom' : item.quality} quality
                        {item.quality_value ? ` · ${item.quality_value}%` : ''}
                      </span>
                    )}
                    {item.downloadable && (
                      <button type="button" onClick={() => onDownload(item)}>
                        {item.kind === 'transcript' ? 'Download transcript' : 'Download'}
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
          <nav className="history-pagination" aria-label="History pages">
            <button
              type="button"
              disabled={activePage === 1}
              onClick={() => setPage(activePage - 1)}
            >
              Previous
            </button>
            <span>
              {activePage} / {pageCount}
            </span>
            <button
              type="button"
              disabled={activePage === pageCount}
              onClick={() => setPage(activePage + 1)}
            >
              Next
            </button>
          </nav>
        </>
      )}
    </aside>
  );
}
