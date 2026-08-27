import { useCallback, useEffect, useRef, useState } from 'react';
import './App.css';
import { AuthStatus } from './components/AuthStatus';
import { MarketingPage } from './components/MarketingPage';
import { ProgressBar } from './components/ProgressBar';
import { TransformationHistory } from './components/TransformationHistory';
import { isMystiraOidcConfigured } from './auth/mystiraOidcConfig';
import { conversionAPI } from './utils/apiClient';

const ROUTES = [
  { id: 'document', index: '01', label: 'Document', route: '.TEX → .PDF', hint: 'Typeset source' },
  { id: 'image', index: '02', label: 'Image', route: 'IMAGE → IMAGE', hint: 'Reformat pixels' },
  { id: 'audio', index: '03', label: 'Audio', route: 'AUDIO → AUDIO', hint: 'Change codec' },
  {
    id: 'transcript',
    index: '04',
    label: 'Transcript',
    route: 'AUDIO → TEXT',
    hint: 'Extract speech',
  },
];

const ACCEPT = {
  document: '.tex',
  image: '.jpg,.jpeg,.png,.webp,.bmp,.tiff,.gif',
  audio: '.ogg,.opus,.mp3,.wav,.m4a,.aac,.flac',
  transcript: '.ogg,.opus,.mp3,.wav,.m4a,.aac,.flac',
};

function filenameStem(filename) {
  return filename?.replace(/\.[^.]+$/, '') || 'mill-output';
}

function saveBlob(response, filename) {
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function TransformationApp() {
  const [authenticated, setAuthenticated] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [activeRoute, setActiveRoute] = useState('document');
  const [files, setFiles] = useState({});
  const [results, setResults] = useState({});
  const [errors, setErrors] = useState({});
  const [processing, setProcessing] = useState(null);
  const [progress, setProgress] = useState(0);
  const [autoFix, setAutoFix] = useState(false);
  const [imageFormat, setImageFormat] = useState('webp');
  const [imageQuality, setImageQuality] = useState('high');
  const [audioFormat, setAudioFormat] = useState('mp3');
  const [bitrate, setBitrate] = useState('192k');
  const [history, setHistory] = useState([]);
  const [sessionHistory, setSessionHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const authGenerationRef = useRef(0);

  const refreshHistory = useCallback(async () => {
    if (!authenticated) return;
    const generation = authGenerationRef.current;
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const response = await conversionAPI.getTransformationHistory();
      if (generation === authGenerationRef.current) setHistory(response.data);
    } catch (error) {
      if (generation === authGenerationRef.current) {
        setHistoryError(error.message || 'History is temporarily unavailable.');
      }
    } finally {
      if (generation === authGenerationRef.current) setHistoryLoading(false);
    }
  }, [authenticated]);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  const handleAuthChange = useCallback(value => {
    if (!value) {
      authGenerationRef.current += 1;
      setFiles({});
      setResults({});
      setErrors({});
      setHistory([]);
      setSessionHistory([]);
      setProcessing(null);
      setProgress(0);
    }
    setAuthenticated(value);
  }, []);

  const chooseRoute = route => {
    setActiveRoute(route);
    requestAnimationFrame(() => document.getElementById(`${route}-input`)?.focus());
  };

  const handleRailKeyDown = event => {
    if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const index = ROUTES.findIndex(route => route.id === activeRoute);
    const direction = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : -1;
    chooseRoute(ROUTES[(index + direction + ROUTES.length) % ROUTES.length].id);
  };

  const setFile = file => {
    setFiles(current => ({ ...current, [activeRoute]: file || null }));
    setResults(current => ({ ...current, [activeRoute]: null }));
    setErrors(current => ({ ...current, [activeRoute]: '' }));
  };

  const runTransformation = async () => {
    const file = files[activeRoute];
    if (!file) return;
    const route = activeRoute;
    const generation = authGenerationRef.current;
    setProcessing(route);
    setProgress(15);
    setErrors(current => ({ ...current, [route]: '' }));
    setResults(current => ({ ...current, [route]: null }));
    const timer = setInterval(() => setProgress(value => Math.min(value + 12, 88)), 450);
    try {
      let response;
      if (route === 'document') response = await conversionAPI.convertLaTeX(file, autoFix);
      if (route === 'image')
        response = await conversionAPI.convertImage(file, imageFormat, imageQuality);
      if (route === 'audio')
        response = await conversionAPI.convertAudio(file, audioFormat, bitrate);
      if (route === 'transcript') response = await conversionAPI.transcribeAudio(file, null, false);
      clearInterval(timer);
      if (generation !== authGenerationRef.current) return;
      setProgress(100);
      setResults(current => ({ ...current, [route]: response.data }));
      if (route === 'transcript' && response.data.success) {
        setSessionHistory(current => [
          {
            id: response.data.id,
            kind: 'transcript',
            filename: file.name,
            input_format: 'audio',
            output_format: 'text',
            success: true,
            timestamp: response.data.timestamp || new Date().toISOString(),
            downloadable: false,
            retained: false,
            detail: response.data.language,
          },
          ...current,
        ]);
      } else {
        await refreshHistory();
      }
    } catch (error) {
      clearInterval(timer);
      if (generation !== authGenerationRef.current) return;
      const message = error.message || 'Transformation failed. Please try again.';
      setErrors(current => ({ ...current, [route]: message }));
    } finally {
      if (generation === authGenerationRef.current) {
        setProcessing(null);
        setTimeout(() => setProgress(0), 700);
      }
    }
  };

  const download = async item => {
    try {
      let response;
      if (item.kind === 'document') response = await conversionAPI.downloadPDF(item.id);
      if (item.kind === 'image') response = await conversionAPI.downloadImage(item.id);
      if (item.kind === 'audio') response = await conversionAPI.downloadAudio(item.id);
      saveBlob(response, `${filenameStem(item.filename)}.${item.output_format}`);
    } catch (error) {
      setHistoryError(error.message || 'Download failed.');
    }
  };

  const authControl = (
    <AuthStatus
      onAuthChange={handleAuthChange}
      onAuthReady={() => setAuthReady(true)}
      variant={authenticated ? 'workspace' : 'landing'}
    />
  );

  if (!authenticated) {
    return (
      <MarketingPage
        authControl={authControl}
        checkingSession={!authReady}
        oidcConfigured={isMystiraOidcConfigured()}
      />
    );
  }

  const route = ROUTES.find(item => item.id === activeRoute);
  const result = results[activeRoute];
  const allHistory = [...sessionHistory, ...history].sort(
    (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
  );

  return (
    <div className="workspace-page transformation-workbench">
      <a href="#transform-stage" className="skip-link">
        Skip to transformation
      </a>
      <div className="workspace-shell workbench-shell">
        <header className="workspace-header">
          <a className="marketing-wordmark" href="/" aria-label="Mill workspace home">
            <img className="wordmark-icon" src="/mill-mark.svg" alt="" />
            <span>Mill</span>
          </a>
          <div className="workspace-heading">
            <p>Private transformation workbench</p>
            <h1>Choose a transformation.</h1>
          </div>
          <div className="workspace-account">{authControl}</div>
        </header>

        <main className="workbench-grid">
          <nav className="transformation-rail" aria-label="Transformations">
            <div className="rail-intro">
              <span>04 paths</span>
              <p>One source in. One useful format out.</p>
            </div>
            <div role="tablist" aria-orientation="vertical" onKeyDown={handleRailKeyDown}>
              {ROUTES.map(item => (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  id={`${item.id}-tab`}
                  aria-selected={activeRoute === item.id}
                  aria-controls={`${item.id}-panel`}
                  tabIndex={activeRoute === item.id ? 0 : -1}
                  className={activeRoute === item.id ? 'is-active' : ''}
                  onClick={() => chooseRoute(item.id)}
                >
                  <span className="rail-index">{item.index}</span>
                  <strong>{item.label}</strong>
                  <small>{item.route}</small>
                  <em>{item.hint}</em>
                </button>
              ))}
            </div>
          </nav>

          <section
            id="transform-stage"
            className="transform-stage"
            role="tabpanel"
            aria-labelledby={`${activeRoute}-tab`}
          >
            <div className="stage-heading">
              <div>
                <p className="eyebrow">
                  Path {route.index} / {route.route}
                </p>
                <h2>{route.label} transformation</h2>
              </div>
              <span className="privacy-mark">Private by default</span>
            </div>
            <label className="source-drop" htmlFor={`${activeRoute}-input`}>
              <span className="source-symbol">＋</span>
              <strong>
                {files[activeRoute]?.name || `Choose a ${route.label.toLowerCase()} source`}
              </strong>
              <small>{ACCEPT[activeRoute].split(',').join(' · ')} · one file per run</small>
              <input
                id={`${activeRoute}-input`}
                type="file"
                accept={ACCEPT[activeRoute]}
                onChange={event => setFile(event.target.files?.[0])}
              />
            </label>

            <div className="route-settings">
              {activeRoute === 'document' && (
                <label className="toggle-setting">
                  <input
                    type="checkbox"
                    checked={autoFix}
                    onChange={event => setAutoFix(event.target.checked)}
                  />
                  <span>
                    <strong>Repair common LaTeX structure</strong>
                    <small>Add missing document wrappers when safe.</small>
                  </span>
                </label>
              )}
              {activeRoute === 'image' && (
                <>
                  <label>
                    Output format
                    <select value={imageFormat} onChange={e => setImageFormat(e.target.value)}>
                      {['webp', 'jpeg', 'png', 'gif', 'tiff', 'bmp'].map(value => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Quality
                    <select value={imageQuality} onChange={e => setImageQuality(e.target.value)}>
                      {['high', 'medium', 'low', 'web'].map(value => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                  </label>
                </>
              )}
              {activeRoute === 'audio' && (
                <>
                  <label>
                    Output format
                    <select value={audioFormat} onChange={e => setAudioFormat(e.target.value)}>
                      {['mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac'].map(value => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Bitrate
                    <select value={bitrate} onChange={e => setBitrate(e.target.value)}>
                      {['128k', '192k', '256k', '320k'].map(value => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                  </label>
                </>
              )}
              {activeRoute === 'transcript' && (
                <div className="ephemeral-note">
                  <strong>Session-only transcript</strong>
                  <p>
                    The text is not retained in server history. It disappears when you sign out or
                    close this session.
                  </p>
                </div>
              )}
            </div>

            {processing === activeRoute && (
              <ProgressBar
                value={progress}
                label="Transformation progress"
                ariaLabel="Transformation progress"
              />
            )}
            {errors[activeRoute] && (
              <p className="stage-error" role="alert">
                {errors[activeRoute]}
              </p>
            )}
            <button
              className="run-button"
              type="button"
              disabled={!files[activeRoute] || processing}
              onClick={runTransformation}
            >
              <span>
                {processing === activeRoute ? 'Working…' : `Run ${route.label.toLowerCase()} path`}
              </span>
              <span>{route.route}</span>
            </button>

            {result && (
              <div
                className={`stage-result ${result.success ? 'is-success' : 'is-failed'}`}
                aria-live="polite"
              >
                <div>
                  <p className="eyebrow">Latest result</p>
                  <h3>{result.success ? 'Transformation complete' : 'Transformation failed'}</h3>
                </div>
                {activeRoute === 'transcript' && result.text && (
                  <p className="transcript-copy">{result.text}</p>
                )}
                {result.success && activeRoute !== 'transcript' && (
                  <button
                    type="button"
                    onClick={() =>
                      download({
                        id: result.id,
                        kind: activeRoute,
                        filename: result.filename,
                        output_format: result.target_format || 'pdf',
                      })
                    }
                  >
                    Download output
                  </button>
                )}
                {!result.success && (
                  <p>{result.errors?.join(' ') || 'The source could not be transformed.'}</p>
                )}
              </div>
            )}
          </section>

          <TransformationHistory
            items={allHistory}
            loading={historyLoading}
            error={historyError}
            onRefresh={refreshHistory}
            onDownload={download}
          />
        </main>
      </div>
    </div>
  );
}

export default TransformationApp;
