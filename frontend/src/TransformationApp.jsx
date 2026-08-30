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

const DEFAULT_LIMITS = {
  max_items: 10,
  max_aggregate_size: 200 * 1024 * 1024,
};

function extensionOf(filename) {
  const match = filename.toLowerCase().match(/\.[^.]+$/);
  return match?.[0] || '';
}

export function validateFiles(route, fileList, capabilities) {
  const files = [...fileList];
  const routeCapability = capabilities?.routes?.[route];
  const extensions = routeCapability?.extensions || ACCEPT[route].split(',');
  const maxItems = route === 'transcript' ? 1 : capabilities?.batch?.max_items || 10;
  const maxFileSize = routeCapability?.max_file_size || Number.POSITIVE_INFINITY;
  const aggregateLimit = capabilities?.batch?.max_aggregate_size || Number.POSITIVE_INFINITY;
  const nameCounts = files.reduce((counts, file) => {
    const key = file.name.toLowerCase();
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
  const aggregateSize = files.reduce((total, file) => total + file.size, 0);
  return files.map((file, index) => {
    let error = '';
    if (!extensions.includes(extensionOf(file.name))) error = `Unsupported ${route} file type.`;
    else if (file.size <= 0) error = 'The file is empty.';
    else if (file.size > maxFileSize) error = `File exceeds the ${formatBytes(maxFileSize)} limit.`;
    else if (nameCounts[file.name.toLowerCase()] > 1) error = 'Duplicate filename in this batch.';
    else if (index >= maxItems) error = `A batch is limited to ${maxItems} files.`;
    else if (aggregateSize > aggregateLimit) error = `Batch exceeds the ${formatBytes(aggregateLimit)} limit.`;
    return {
      id: `${file.name}:${file.size}:${file.lastModified}:${index}`,
      file,
      error,
    };
  });
}

export async function sha256File(file) {
  if (!crypto.subtle) throw new Error('This browser cannot verify file content safely.');
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join('');
}

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

function saveBlob(response, filename, mimeType) {
  const url = window.URL.createObjectURL(new Blob([response.data], { type: mimeType }));
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
  const [svgPreviewUrl, setSvgPreviewUrl] = useState('');
  const [vectorColors, setVectorColors] = useState(8);
  const [vectorDetail, setVectorDetail] = useState(60);
  const [pathSmoothing, setPathSmoothing] = useState(50);
  const [removeVectorBackground, setRemoveVectorBackground] = useState(false);
  const [vectorMaxDimension, setVectorMaxDimension] = useState(1024);
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
  const [capabilities, setCapabilities] = useState(null);
  const [batches, setBatches] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const authGenerationRef = useRef(0);
  const imagePreviewUrlRef = useRef('');
  const svgPreviewUrlRef = useRef('');
  const svgPreviewTokenRef = useRef('');

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

  const refreshBatches = useCallback(async () => {
    if (!authenticated) return;
    const generation = authGenerationRef.current;
    try {
      const [capabilityResponse, batchResponse] = await Promise.all([
        conversionAPI.getCapabilities(),
        conversionAPI.getBatches(),
      ]);
      if (generation === authGenerationRef.current) {
        setCapabilities(capabilityResponse.data);
        setBatches(batchResponse.data);
      }
    } catch (error) {
      if (generation === authGenerationRef.current) {
        setHistoryError(error.message || 'Batch capabilities are temporarily unavailable.');
      }
    }
  }, [authenticated]);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    refreshBatches();
  }, [refreshBatches]);

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
      if (svgPreviewUrlRef.current) {
        window.URL.revokeObjectURL(svgPreviewUrlRef.current);
      }
      svgPreviewTokenRef.current = '';
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
      setBatches([]);
      setCapabilities(null);
      setDragActive(false);
      setProcessing(null);
      setProgress(0);
      if (imagePreviewUrlRef.current) {
        window.URL.revokeObjectURL(imagePreviewUrlRef.current);
        imagePreviewUrlRef.current = '';
        setImagePreviewUrl('');
      }
      if (svgPreviewUrlRef.current) {
        window.URL.revokeObjectURL(svgPreviewUrlRef.current);
        svgPreviewUrlRef.current = '';
        setSvgPreviewUrl('');
      }
      svgPreviewTokenRef.current = '';
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

  const setRouteFiles = fileList => {
    const entries = validateFiles(activeRoute, fileList || [], capabilities);
    const previewFile = entries.find(entry => !entry.error)?.file;
    if (activeRoute === 'image') {
      if (imagePreviewUrlRef.current) {
        window.URL.revokeObjectURL(imagePreviewUrlRef.current);
      }
      imagePreviewUrlRef.current = previewFile ? window.URL.createObjectURL(previewFile) : '';
      setImagePreviewUrl(imagePreviewUrlRef.current);
      if (svgPreviewUrlRef.current) {
        window.URL.revokeObjectURL(svgPreviewUrlRef.current);
        svgPreviewUrlRef.current = '';
        setSvgPreviewUrl('');
      }
      svgPreviewTokenRef.current = '';
    }
    setFiles(current => ({ ...current, [activeRoute]: entries }));
    setResults(current => ({ ...current, [activeRoute]: null }));
    setErrors(current => ({ ...current, [activeRoute]: '' }));
  };

  const removeFile = entryId => {
    const remaining = (files[activeRoute] || []).filter(entry => entry.id !== entryId);
    setRouteFiles(remaining.map(entry => entry.file));
  };

  const batchSettings = route => {
    if (route === 'document') return { auto_fix: autoFix };
    if (route === 'image')
      return {
        target_format: imageFormat,
        quality: imageQuality === 'custom' ? customImageQuality : imageQuality,
        max_width: imageFormat === 'svg' ? undefined : parseMaxDimension(imageMaxWidth),
        max_height: imageFormat === 'svg' ? undefined : parseMaxDimension(imageMaxHeight),
        strip_metadata: stripImageMetadata,
        vector_colors: vectorColors,
        vector_detail: vectorDetail,
        path_smoothing: pathSmoothing,
        remove_background: removeVectorBackground,
        vector_max_dimension: vectorMaxDimension,
      };
    if (route === 'text') return { target_format: textFormat };
    if (route === 'audio') return { target_format: audioFormat, bitrate };
    return {
      target_format: videoFormat,
      quality: videoQuality,
      max_height: videoMaxHeight ? Number(videoMaxHeight) : null,
    };
  };

  const runBatch = async (route, selectedFiles, generation) => {
    const settings = batchSettings(route);
    const descriptors = await Promise.all(
      selectedFiles.map(async file => ({
        filename: file.name,
        size: file.size,
        sha256: await sha256File(file),
      }))
    );
    const resumable = batches.find(
      batch =>
        batch.route === route &&
        ['accepted', 'running'].includes(batch.state) &&
        JSON.stringify(batch.settings) === JSON.stringify(settings) &&
        batch.items.length === selectedFiles.length &&
        batch.items.every(item => {
          const descriptor = descriptors[item.position];
          return (
            descriptor?.filename === item.filename &&
            descriptor?.size === item.size &&
            descriptor?.sha256 === item.sha256
          );
        })
    );
    let batch = resumable;
    if (!batch) {
      const idempotencyKey = crypto.randomUUID();
      batch = (
        await conversionAPI.createBatch(route, settings, descriptors, idempotencyKey)
      ).data;
    }
    setBatches(current => [batch, ...current.filter(item => item.id !== batch.id)]);
    for (const item of batch.items) {
      if (generation !== authGenerationRef.current) return;
      if (item.state === 'succeeded') continue;
      if (!['accepted', 'running'].includes(item.state)) {
        throw new Error(`${item.filename} cannot be resumed safely.`);
      }
      const file = selectedFiles[item.position];
      const response = await conversionAPI.executeBatchItem(batch.id, item.id, file);
      batch = response.data.batch;
      setBatches(current => [batch, ...current.filter(existing => existing.id !== batch.id)]);
      setProgress(Math.round(((item.position + 1) / selectedFiles.length) * 100));
    }
    await refreshHistory();
  };

  const runTransformation = async () => {
    const entries = files[activeRoute] || [];
    const selectedFiles = entries.filter(entry => !entry.error).map(entry => entry.file);
    if (!selectedFiles.length || entries.some(entry => entry.error)) return;
    const file = selectedFiles[0];
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
      if (selectedFiles.length > 1) {
        await runBatch(route, selectedFiles, generation);
        if (timer) clearInterval(timer);
        return;
      }
      let response;
      if (route === 'document') response = await conversionAPI.convertLaTeX(file, autoFix);
      if (route === 'image')
        response = await conversionAPI.convertImage(
          file,
          imageFormat,
          imageQuality === 'custom' ? customImageQuality : imageQuality,
          {
            maxWidth: imageFormat === 'svg' ? undefined : parseMaxDimension(imageMaxWidth),
            maxHeight: imageFormat === 'svg' ? undefined : parseMaxDimension(imageMaxHeight),
            stripMetadata: stripImageMetadata,
            vectorColors,
            vectorDetail,
            pathSmoothing,
            removeBackground: removeVectorBackground,
            vectorMaxDimension,
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
      if (route === 'image' && response.data.success && response.data.target_format === 'svg') {
        const previewToken = `${generation}:${response.data.id}`;
        svgPreviewTokenRef.current = previewToken;
        void conversionAPI
          .downloadImage(response.data.id)
          .then(previewResponse => {
            if (
              generation === authGenerationRef.current &&
              svgPreviewTokenRef.current === previewToken
            ) {
              const previewUrl = window.URL.createObjectURL(
                new Blob([previewResponse.data], { type: 'image/svg+xml' })
              );
              if (svgPreviewUrlRef.current) {
                window.URL.revokeObjectURL(svgPreviewUrlRef.current);
              }
              svgPreviewUrlRef.current = previewUrl;
              setSvgPreviewUrl(previewUrl);
            }
          })
          .catch(() => {
            // Preview is supplementary; the retained result remains downloadable.
          });
      }
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
            downloadable: true,
            retained: false,
            detail: response.data.language,
            text: response.data.text,
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
      if (item.kind === 'transcript') {
        saveBlob(
          { data: item.text },
          `${filenameStem(item.filename)}-transcript.txt`,
          'text/plain;charset=utf-8'
        );
        return;
      }
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
  const selectedEntries = files[activeRoute] || [];
  const validEntries = selectedEntries.filter(entry => !entry.error);
  const activeBatch = batches.find(batch => batch.route === activeRoute);
  const routeCapability = capabilities?.routes?.[activeRoute];
  const accept = routeCapability?.extensions?.join(',') || ACCEPT[activeRoute];
  const batchLimit = capabilities?.batch || DEFAULT_LIMITS;
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
              aria-expanded={historyOpen}
              aria-controls="transformation-history"
              onClick={() => setHistoryOpen(value => !value)}
            >
              {historyOpen ? 'Hide history' : 'Show history'}
              <span>{allHistory.length} saved</span>
            </button>
          </div>

          <nav
            id="transformation-paths"
            className={`transformation-rail ${pathsOpen ? '' : 'is-collapsed'}`}
            aria-label="Transformations"
          >
            <div className="rail-intro">
              <div>
                <span>{pathsOpen ? '6 live · 3 coming soon' : 'Current path'}</span>
                <p>
                  {pathsOpen
                    ? 'One source in. One useful format out.'
                    : `${route.label} · ${route.route}`}
                </p>
              </div>
              <button
                type="button"
                aria-expanded={pathsOpen}
                aria-controls="transformation-path-options"
                onClick={() => setPathsOpen(value => !value)}
              >
                {pathsOpen ? 'Collapse paths' : 'Show paths'}
              </button>
            </div>
            {pathsOpen && (
              <div id="transformation-path-options">
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
              </div>
            )}
          </nav>

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
              className={`source-drop ${activeRoute === 'image' ? 'source-drop-image' : ''} ${dragActive ? 'is-dragging' : ''}`}
              htmlFor={`${activeRoute}-input`}
              onDragEnter={event => {
                event.preventDefault();
                setDragActive(true);
              }}
              onDragOver={event => {
                event.preventDefault();
                event.dataTransfer.dropEffect = 'copy';
                setDragActive(true);
              }}
              onDragLeave={event => {
                if (!event.currentTarget.contains(event.relatedTarget)) setDragActive(false);
              }}
              onDrop={event => {
                event.preventDefault();
                setDragActive(false);
                if (event.dataTransfer.files.length) setRouteFiles(event.dataTransfer.files);
                else {
                  setErrors(current => ({
                    ...current,
                    [activeRoute]: 'Drop supported files, not folders or other content.',
                  }));
                }
              }}
            >
              <span className="source-copy">
                <span className="source-symbol">＋</span>
                <strong title={validEntries.length === 1 ? validEntries[0].file.name : undefined}>
                  {selectedEntries.length === 1
                    ? selectedEntries[0].file.name
                    : selectedEntries.length > 1
                      ? `${selectedEntries.length} files selected`
                      : `Drop or choose ${route.label.toLowerCase()} source files`}
                </strong>
                {selectedEntries.length === 1 && (
                  <span className="source-size">{formatBytes(selectedEntries[0].file.size)}</span>
                )}
                <small>
                  {accept.split(',').join(' · ')} ·{' '}
                  {activeRoute === 'transcript'
                    ? 'one file per run'
                    : `up to ${batchLimit.max_items} files`}
                </small>
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
                accept={accept}
                multiple={activeRoute !== 'transcript'}
                onChange={event => setRouteFiles(event.target.files)}
              />
            </label>

            {selectedEntries.length > 0 && (
              <ul className="source-file-list" aria-live="polite" aria-label="Selected files">
                {selectedEntries.map(entry => (
                  <li key={entry.id} className={entry.error ? 'is-invalid' : ''}>
                    <span>
                      <strong>{entry.file.name}</strong>
                      <small>{entry.error || formatBytes(entry.file.size)}</small>
                    </span>
                    <button
                      type="button"
                      onClick={() => removeFile(entry.id)}
                      aria-label={`Remove ${entry.file.name}`}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}

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
                      {['webp', 'jpeg', 'png', 'gif', 'tiff', 'bmp', 'svg'].map(value => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                  </label>
                  {imageFormat !== 'svg' && (
                    <label>
                      Quality
                      <select value={imageQuality} onChange={e => setImageQuality(e.target.value)}>
                        {['high', 'medium', 'low', 'web', 'custom'].map(value => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                  )}
                  <details className="image-advanced">
                    <summary>
                      {imageFormat === 'svg' ? 'Vector settings' : 'Advanced image settings'}
                    </summary>
                    <div className="advanced-setting-grid">
                      {imageFormat === 'svg' ? (
                        <>
                          <label>
                            Palette colors: {vectorColors}
                            <input
                              type="range"
                              min="2"
                              max="32"
                              value={vectorColors}
                              onChange={event => setVectorColors(Number(event.target.value))}
                            />
                          </label>
                          <label>
                            Shape detail: {vectorDetail}%
                            <input
                              type="range"
                              min="1"
                              max="100"
                              value={vectorDetail}
                              onChange={event => setVectorDetail(Number(event.target.value))}
                            />
                          </label>
                          <label>
                            Path smoothing: {pathSmoothing}%
                            <input
                              type="range"
                              min="0"
                              max="100"
                              value={pathSmoothing}
                              onChange={event => setPathSmoothing(Number(event.target.value))}
                            />
                          </label>
                          <label>
                            Maximum dimension
                            <select
                              value={vectorMaxDimension}
                              onChange={event => setVectorMaxDimension(Number(event.target.value))}
                            >
                              <option value="512">512 px</option>
                              <option value="1024">1024 px</option>
                              <option value="2048">2048 px</option>
                            </select>
                          </label>
                          <label className="metadata-setting">
                            <input
                              type="checkbox"
                              checked={removeVectorBackground}
                              onChange={event => setRemoveVectorBackground(event.target.checked)}
                            />
                            <span>
                              <strong>Remove flat background</strong>
                              <small>Uses border-connected color detection; no AI provider.</small>
                            </span>
                          </label>
                        </>
                      ) : imageQuality === 'custom' ? (
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
                      ) : null}
                      {imageFormat !== 'svg' && (
                        <>
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
                        </>
                      )}
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
                  validEntries.length > 1
                    ? `Converting ${validEntries.length} files`
                    : activeRoute === 'video'
                    ? `Transcoding video · ${formatElapsed(elapsedSeconds)}`
                    : 'Transformation progress'
                }
                ariaLabel={
                  activeRoute === 'video'
                    ? 'Video transcoding in progress'
                    : 'Transformation progress'
                }
                indeterminate={activeRoute === 'video' && validEntries.length === 1}
                showPercentage={activeRoute !== 'video' || validEntries.length > 1}
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
              disabled={!validEntries.length || selectedEntries.some(entry => entry.error) || processing}
              onClick={runTransformation}
            >
              <span>
                {processing === activeRoute
                  ? 'Working…'
                  : validEntries.length > 1
                    ? `Convert ${validEntries.length} files`
                    : `Run ${route.label.toLowerCase()} path`}
              </span>
              <span>{route.route}</span>
            </button>

            {activeBatch && (
              <section className="batch-result" aria-live="polite" aria-label="Latest batch">
                <header>
                  <div>
                    <p className="eyebrow">Batch {activeBatch.id.slice(0, 8)}</p>
                    <h3>{activeBatch.state.replace('_', ' ')}</h3>
                  </div>
                  <span>
                    {activeBatch.counts.succeeded}/{activeBatch.items.length} complete
                  </span>
                </header>
                <ul>
                  {activeBatch.items.map(item => (
                    <li key={item.id} className={`is-${item.state}`}>
                      <span>
                        <strong>{item.filename}</strong>
                        <small>{item.error || item.state.replace('_', ' ')}</small>
                      </span>
                      {item.state === 'succeeded' && (
                        <button
                          type="button"
                          onClick={() =>
                            download({
                              id: item.result_id,
                              kind: activeBatch.route,
                              filename: item.filename,
                              output_format: item.output_format,
                            })
                          }
                        >
                          Download
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}

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
                  <>
                    {result.target_format === 'svg' && svgPreviewUrl && (
                      <figure className="svg-result-preview">
                        <img src={safeBlobUrl(svgPreviewUrl)} alt="Converted SVG preview" />
                        <figcaption>Converted vector preview</figcaption>
                      </figure>
                    )}
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
                      {result.target_format === 'svg' ? (
                        <div className="result-outcome">
                          <span>Vector output</span>
                          <strong>
                            {result.vector_colors} colors · {result.vector_paths} paths
                          </strong>
                          <em>
                            {result.vector_detail}% detail · {result.path_smoothing}% smoothing
                            {result.background_removed ? ' · background removed' : ''}
                          </em>
                        </div>
                      ) : result.quality || result.quality_value ? (
                        <div className="result-outcome">
                          <span>Quality</span>
                          <strong>
                            {result.quality === 'custom' ? 'Custom' : result.quality || 'Custom'}
                            {result.quality_value ? ` · ${result.quality_value}%` : ''}
                          </strong>
                        </div>
                      ) : null}
                    </div>
                  </>
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
                {result.success && (
                  <button
                    type="button"
                    onClick={() =>
                      download({
                        id: result.id,
                        kind: activeRoute,
                        filename: result.filename,
                        output_format: result.target_format || 'pdf',
                        text: result.text,
                      })
                    }
                  >
                    {activeRoute === 'transcript' ? 'Download transcript' : 'Download output'}
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
