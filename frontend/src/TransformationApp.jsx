import { useCallback, useEffect, useRef, useState } from 'react';
import './App.css';
import { AuthStatus } from './components/AuthStatus';
import { MarketingPage } from './components/MarketingPage';
import { ProgressBar } from './components/ProgressBar';
import { TransformationHistory } from './components/TransformationHistory';
import { isMystiraOidcConfigured } from './auth/mystiraOidcConfig';
import { loginWithMystira } from './auth/mystiraOidcInstance';
import { conversionAPI } from './utils/apiClient';

const ROUTES = [
  { id: 'document', label: 'Document', route: '.TEX → .PDF', hint: 'Typeset source' },
  { id: 'image', label: 'Image', route: 'IMAGE → IMAGE', hint: 'Reformat pixels' },
  { id: 'text', label: 'Text', route: 'TEXT ↔ DOCX', hint: 'Reshape words' },
  { id: 'audio', label: 'Audio', route: 'AUDIO → AUDIO', hint: 'Change codec' },
  {
    id: 'transcript',
    label: 'Transcript',
    route: 'AUDIO → TEXT',
    hint: 'Extract speech',
  },
  { id: 'video', label: 'Video', route: 'VIDEO → VIDEO', hint: 'Transcode locally' },
];

const UPCOMING_ROUTES = [
  {
    id: 'generate-rewrite',
    label: 'Generate / Rewrite',
    route: 'WORDS → NEW WORDS',
    hint: 'Governed AI through Sluice',
  },
  {
    id: 'story-media',
    label: 'Story media',
    route: 'STORY YAML → IMAGE / VIDEO',
    hint: 'Managed Mystira Story pipeline',
  },
  {
    id: 'image-3d',
    label: '3D model',
    route: 'IMAGE → 3D MODEL',
    hint: 'Managed multi-step model pipeline',
  },
];

const ACCEPT = {
  document: '.tex',
  image: '.jpg,.jpeg,.png,.webp,.bmp,.tiff,.gif',
  text: '.md,.markdown,.html,.htm,.txt,.docx',
  audio: '.ogg,.opus,.mp3,.wav,.m4a,.aac,.flac',
  transcript: '.ogg,.opus,.mp3,.wav,.m4a,.aac,.flac',
  video: '.mp4,.mov,.mkv,.webm,.avi,.m4v',
};

function filenameStem(filename) {
  return filename?.replace(/\.[^.]+$/, '') || 'mill-output';
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatElapsed(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

export function safeBlobUrl(url, expectedOrigin = window.location.origin) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'blob:' || parsed.origin !== expectedOrigin) return '';
    return url.replace(/[^a-zA-Z0-9:./_%\x5B\x5D-]/g, '');
  } catch {
    return '';
  }
}

function parseMaxDimension(value) {
  if (value === '') return undefined;
  const dimension = Number(value);
  if (!Number.isInteger(dimension) || dimension < 1 || dimension > 16384) {
    throw new Error('Maximum dimensions must be whole numbers from 1 to 16384.');
  }
  return dimension;
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
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [pathsOpen, setPathsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [autoFix, setAutoFix] = useState(false);
  const [imageFormat, setImageFormat] = useState('webp');
  const [imageQuality, setImageQuality] = useState('high');
  const [customImageQuality, setCustomImageQuality] = useState(85);
  const [imageMaxWidth, setImageMaxWidth] = useState('');
  const [imageMaxHeight, setImageMaxHeight] = useState('');
  const [stripImageMetadata, setStripImageMetadata] = useState(true);
  const [imagePreviewUrl, setImagePreviewUrl] = useState('');
  const [textFormat, setTextFormat] = useState('html');
  const [audioFormat, setAudioFormat] = useState('mp3');
  const [bitrate, setBitrate] = useState('192k');
  const [videoFormat, setVideoFormat] = useState('mp4');
  const [videoQuality, setVideoQuality] = useState('balanced');
  const [videoMaxHeight, setVideoMaxHeight] = useState('1080');
  const [history, setHistory] = useState([]);
  const [sessionHistory, setSessionHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const authGenerationRef = useRef(0);
  const imagePreviewUrlRef = useRef('');

  const refreshHistory = useCallback(async () => {
    if (!authenticated) return;
    const generation = authGenerationRef.current;
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const response = await conversionAPI.getTransformationHistory(100);
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

  useEffect(() => {
    if (processing !== 'video') return undefined;
    const startedAt = Date.now();
    const timer = window.setInterval(
      () => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)),
      1000
    );
    return () => window.clearInterval(timer);
  }, [processing]);

  useEffect(
    () => () => {
      if (imagePreviewUrlRef.current) {
        window.URL.revokeObjectURL(imagePreviewUrlRef.current);
      }
    },
    []
  );

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
      if (imagePreviewUrlRef.current) {
        window.URL.revokeObjectURL(imagePreviewUrlRef.current);
        imagePreviewUrlRef.current = '';
        setImagePreviewUrl('');
      }
    }
    setAuthenticated(value);
  }, []);

  const handleAuthReady = useCallback(() => {
    setAuthReady(true);
  }, []);

  const chooseRoute = (route, focusTarget = 'input') => {
    setActiveRoute(route);
    const targetId = focusTarget === 'tab' ? `${route}-tab` : `${route}-input`;
    requestAnimationFrame(() => document.getElementById(targetId)?.focus());
  };

  const handleRailKeyDown = event => {
    if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const index = ROUTES.findIndex(route => route.id === activeRoute);
    const direction = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : -1;
    chooseRoute(ROUTES[(index + direction + ROUTES.length) % ROUTES.length].id, 'tab');
  };

  const setFile = file => {
    if (activeRoute === 'image') {
      if (imagePreviewUrlRef.current) {
        window.URL.revokeObjectURL(imagePreviewUrlRef.current);
      }
      imagePreviewUrlRef.current = file ? window.URL.createObjectURL(file) : '';
      setImagePreviewUrl(imagePreviewUrlRef.current);
    }
    setFiles(current => ({ ...current, [activeRoute]: file || null }));
    setResults(current => ({ ...current, [activeRoute]: null }));
    setErrors(current => ({ ...current, [activeRoute]: '' }));
  };

  const runTransformation = async () => {
    const file = files[activeRoute];
    if (!file) return;
    const route = activeRoute;
    const generation = authGenerationRef.current;
    if (route === 'video') setElapsedSeconds(0);
    setProcessing(route);
    setProgress(15);
    setErrors(current => ({ ...current, [route]: '' }));
    setResults(current => ({ ...current, [route]: null }));
    const timer =
      route === 'video'
        ? null
        : setInterval(() => setProgress(value => Math.min(value + 12, 88)), 450);
    try {
      let response;
      if (route === 'document') response = await conversionAPI.convertLaTeX(file, autoFix);
      if (route === 'image')
        response = await conversionAPI.convertImage(
          file,
          imageFormat,
          imageQuality === 'custom' ? customImageQuality : imageQuality,
          {
            maxWidth: parseMaxDimension(imageMaxWidth),
            maxHeight: parseMaxDimension(imageMaxHeight),
            stripMetadata: stripImageMetadata,
          }
        );
      if (route === 'text') response = await conversionAPI.convertText(file, textFormat);
      if (route === 'audio')
        response = await conversionAPI.convertAudio(file, audioFormat, bitrate);
      if (route === 'transcript') response = await conversionAPI.transcribeAudio(file, null, false);
      if (route === 'video')
        response = await conversionAPI.convertVideo(
          file,
          videoFormat,
          videoQuality,
          videoMaxHeight ? Number(videoMaxHeight) : null
        );
      if (timer) clearInterval(timer);
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
      if (timer) clearInterval(timer);
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
      if (item.kind === 'text') response = await conversionAPI.downloadText(item.id);
      if (item.kind === 'generation') response = await conversionAPI.downloadGeneratedText(item.id);
      if (item.kind === 'audio') response = await conversionAPI.downloadAudio(item.id);
      if (item.kind === 'video') response = await conversionAPI.downloadVideo(item.id);
      saveBlob(response, `${filenameStem(item.filename)}.${item.output_format}`);
    } catch (error) {
      setHistoryError(error.message || 'Download failed.');
    }
  };

  const authControl = (
    <AuthStatus
      onAuthChange={handleAuthChange}
      onAuthReady={handleAuthReady}
      variant={authenticated ? 'workspace' : 'landing'}
    />
  );

  if (!authenticated) {
    return (
      <MarketingPage
        authControl={authControl}
        checkingSession={!authReady}
        oidcConfigured={isMystiraOidcConfigured()}
        onOpenWorkspace={() => loginWithMystira()}
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

        <main className={`workbench-grid ${historyOpen ? 'has-history' : ''}`}>
          <div className="workbench-layout-controls" aria-label="Workbench panels">
            <button
              type="button"
              aria-expanded={pathsOpen}
              aria-controls="transformation-paths"
              onClick={() => setPathsOpen(value => !value)}
            >
              {pathsOpen ? 'Hide paths' : 'Show paths'}
              <span>
                {route.label} · {route.route}
              </span>
            </button>
            <button
              type="button"
              aria-expanded={historyOpen}
              aria-controls="transformation-history"
              onClick={() => setHistoryOpen(value => !value)}
            >
              {historyOpen ? 'Hide history' : 'Show history'}
              <span>{allHistory.length} saved</span>
            </button>
          </div>

          {pathsOpen && (
            <nav
              id="transformation-paths"
              className="transformation-rail"
              aria-label="Transformations"
            >
              <div className="rail-intro">
                <div>
                  <span>6 live · 3 coming soon</span>
                  <p>One source in. One useful format out.</p>
                </div>
                <button type="button" onClick={() => setPathsOpen(false)}>
                  Collapse paths
                </button>
              </div>
              <div
                role="tablist"
                aria-label="Available transformations"
                onKeyDown={handleRailKeyDown}
              >
                {ROUTES.map(item => (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    id={`${item.id}-tab`}
                    aria-selected={activeRoute === item.id}
                    aria-controls="transform-stage"
                    tabIndex={activeRoute === item.id ? 0 : -1}
                    className={activeRoute === item.id ? 'is-active' : ''}
                    onClick={() => {
                      chooseRoute(item.id);
                      setPathsOpen(false);
                    }}
                  >
                    <strong>{item.label}</strong>
                    <small>{item.route}</small>
                    <em>{item.hint}</em>
                  </button>
                ))}
              </div>
              <div className="upcoming-routes" aria-label="Coming soon transformations">
                {UPCOMING_ROUTES.map(item => (
                  <article key={item.id} className="upcoming-route">
                    <div>
                      <span className="status-pill status-coming-soon">[Coming soon]</span>
                      <strong>{item.label}</strong>
                      <small>{item.route}</small>
                      <em>{item.hint}</em>
                    </div>
                  </article>
                ))}
              </div>
            </nav>
          )}

          <section
            id="transform-stage"
            className="transform-stage"
            role="tabpanel"
            aria-label={`${route.label} transformation`}
          >
            <div className="stage-heading">
              <div>
                <p className="eyebrow">
                  {route.label} / {route.route}
                </p>
                <h2>{route.label} transformation</h2>
              </div>
              <span className="privacy-mark">Private by default</span>
            </div>
            <label
              className={`source-drop ${activeRoute === 'image' ? 'source-drop-image' : ''}`}
              htmlFor={`${activeRoute}-input`}
            >
              <span className="source-copy">
                <span className="source-symbol">＋</span>
                <strong title={files[activeRoute]?.name}>
                  {files[activeRoute]?.name || `Choose a ${route.label.toLowerCase()} source`}
                </strong>
                {files[activeRoute] && (
                  <span className="source-size">{formatBytes(files[activeRoute].size)}</span>
                )}
                <small>{ACCEPT[activeRoute].split(',').join(' · ')} · one file per run</small>
              </span>
              {activeRoute === 'image' && imagePreviewUrl && (
                <span className="image-source-preview">
                  <img src={safeBlobUrl(imagePreviewUrl)} alt="Selected source preview" />
                  <small>Source preview</small>
                </span>
              )}
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
                      {['high', 'medium', 'low', 'web', 'custom'].map(value => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                  </label>
                  <details className="image-advanced">
                    <summary>Advanced image settings</summary>
                    <div className="advanced-setting-grid">
                      {imageQuality === 'custom' && (
                        <label>
                          Compression quality: {customImageQuality}%
                          <input
                            type="range"
                            min="1"
                            max="100"
                            value={customImageQuality}
                            onChange={event => setCustomImageQuality(Number(event.target.value))}
                          />
                        </label>
                      )}
                      <label>
                        Maximum width (px)
                        <input
                          type="number"
                          min="1"
                          max="16384"
                          placeholder="Original"
                          value={imageMaxWidth}
                          onChange={event => setImageMaxWidth(event.target.value)}
                        />
                      </label>
                      <label>
                        Maximum height (px)
                        <input
                          type="number"
                          min="1"
                          max="16384"
                          placeholder="Original"
                          value={imageMaxHeight}
                          onChange={event => setImageMaxHeight(event.target.value)}
                        />
                      </label>
                      <label className="metadata-setting">
                        <input
                          type="checkbox"
                          checked={stripImageMetadata}
                          onChange={event => setStripImageMetadata(event.target.checked)}
                        />
                        <span>
                          <strong>Strip embedded metadata</strong>
                          <small>
                            Recommended for privacy; removes EXIF and embedded profiles.
                          </small>
                        </span>
                      </label>
                    </div>
                  </details>
                </>
              )}
              {activeRoute === 'text' && (
                <div className="text-format-panel">
                  <label>
                    Output format
                    <select
                      value={textFormat}
                      onChange={event => setTextFormat(event.target.value)}
                    >
                      <option value="md">Markdown (.md)</option>
                      <option value="html">HTML (.html)</option>
                      <option value="txt">Plain text (.txt)</option>
                      <option value="docx">Word document (.docx)</option>
                    </select>
                  </label>
                  <div className="capability-map" aria-label="Supported deterministic text formats">
                    <div>
                      <span>Inputs</span>
                      <strong>MD · HTML · TXT · DOCX</strong>
                    </div>
                    <span className="capability-arrow" aria-hidden="true">
                      →
                    </span>
                    <div>
                      <span>Outputs</span>
                      <strong>MD · HTML · TXT · DOCX</strong>
                    </div>
                  </div>
                  <p>
                    Every listed input can produce every listed output. No generative model is used.
                  </p>
                </div>
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
              {activeRoute === 'video' && (
                <>
                  <label>
                    Output format
                    <select
                      value={videoFormat}
                      onChange={event => setVideoFormat(event.target.value)}
                    >
                      <option value="mp4">MP4 · H.264</option>
                      <option value="webm">WebM · VP9</option>
                      <option value="mov">MOV · H.264</option>
                    </select>
                  </label>
                  <label>
                    Quality
                    <select
                      value={videoQuality}
                      onChange={event => setVideoQuality(event.target.value)}
                    >
                      <option value="high">High fidelity</option>
                      <option value="balanced">Balanced</option>
                      <option value="small">Small file</option>
                    </select>
                  </label>
                  <label>
                    Maximum height
                    <select
                      value={videoMaxHeight}
                      onChange={event => setVideoMaxHeight(event.target.value)}
                    >
                      <option value="">Original</option>
                      <option value="2160">2160p</option>
                      <option value="1440">1440p</option>
                      <option value="1080">1080p</option>
                      <option value="720">720p</option>
                      <option value="480">480p</option>
                    </select>
                  </label>
                  <p className="deterministic-note">
                    Local FFmpeg path · metadata and audio tracks preserved when present.
                  </p>
                </>
              )}
            </div>

            {processing === activeRoute && (
              <ProgressBar
                value={progress}
                label={
                  activeRoute === 'video'
                    ? `Transcoding video · ${formatElapsed(elapsedSeconds)}`
                    : 'Transformation progress'
                }
                ariaLabel={
                  activeRoute === 'video'
                    ? 'Video transcoding in progress'
                    : 'Transformation progress'
                }
                indeterminate={activeRoute === 'video'}
                showPercentage={activeRoute !== 'video'}
                detail={
                  activeRoute === 'video'
                    ? 'Large videos can take several minutes. Keep this tab open.'
                    : undefined
                }
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
                {result.success && activeRoute === 'image' && (
                  <div className="result-outcomes" aria-label="Image conversion outcomes">
                    {result.input_file_size_kb != null && result.file_size_kb != null && (
                      <div className="result-outcome result-outcome-primary">
                        <span>File size</span>
                        <strong>
                          {formatBytes(result.input_file_size_kb * 1024)} →{' '}
                          {formatBytes(result.file_size_kb * 1024)}
                        </strong>
                        <em>
                          {result.file_size_kb <= result.input_file_size_kb
                            ? `${Math.round((1 - result.file_size_kb / result.input_file_size_kb) * 100)}% smaller`
                            : `${Math.round((result.file_size_kb / result.input_file_size_kb - 1) * 100)}% larger`}
                        </em>
                      </div>
                    )}
                    {result.width && result.height && (
                      <div className="result-outcome">
                        <span>Output dimensions</span>
                        <strong>
                          {result.width} × {result.height} px
                        </strong>
                      </div>
                    )}
                    {(result.quality || result.quality_value) && (
                      <div className="result-outcome">
                        <span>Quality</span>
                        <strong>
                          {result.quality === 'custom' ? 'Custom' : result.quality || 'Custom'}
                          {result.quality_value ? ` · ${result.quality_value}%` : ''}
                        </strong>
                      </div>
                    )}
                  </div>
                )}
                {result.success && activeRoute === 'video' && (
                  <div className="result-outcomes" aria-label="Video conversion outcomes">
                    {result.input_file_size_kb != null && result.file_size_kb != null && (
                      <div className="result-outcome result-outcome-primary">
                        <span>File size</span>
                        <strong>
                          {formatBytes(result.input_file_size_kb * 1024)} →{' '}
                          {formatBytes(result.file_size_kb * 1024)}
                        </strong>
                        <em>
                          {result.file_size_kb <= result.input_file_size_kb
                            ? `${Math.round((1 - result.file_size_kb / result.input_file_size_kb) * 100)}% smaller`
                            : `${Math.round((result.file_size_kb / result.input_file_size_kb - 1) * 100)}% larger`}
                        </em>
                      </div>
                    )}
                    {result.width && result.height && (
                      <div className="result-outcome">
                        <span>Output video</span>
                        <strong>
                          {result.width} × {result.height} · {result.video_codec?.toUpperCase()}
                        </strong>
                        <em>{result.duration ? `${Math.round(result.duration)}s` : ''}</em>
                      </div>
                    )}
                    <div className="result-outcome">
                      <span>Preset</span>
                      <strong>{result.quality}</strong>
                      <em>
                        {result.audio_codec
                          ? `${result.audio_codec.toUpperCase()} audio`
                          : 'No audio track'}
                      </em>
                    </div>
                  </div>
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

          {historyOpen && (
            <TransformationHistory
              items={allHistory}
              loading={historyLoading}
              error={historyError}
              onRefresh={refreshHistory}
              onDownload={download}
              onCollapse={() => setHistoryOpen(false)}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default TransformationApp;
