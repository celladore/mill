import { useEffect, useRef, useState } from 'react';

const PREVIEW_MODES = [
  { id: 'markdown', label: 'Markdown → PDF', category: 'Document', key: '1' },
  { id: 'audio', label: 'Voice → Transcript', category: 'Voice & Audio', key: '2' },
  { id: 'latex', label: 'LaTeX → Typeset', category: 'Technical', key: '3' },
  { id: 'image', label: 'JPEG → WebP', category: 'Images', key: '4' },
];

const SUPPORTED_FORMAT_GROUPS = [
  {
    id: 'document-text',
    label: 'Document / Text',
    formats: ['Markdown', 'HTML', 'Plain text', 'DOCX', 'LaTeX'],
  },
  {
    id: 'image',
    label: 'Image',
    formats: ['JPEG', 'PNG', 'WebP', 'GIF', 'BMP', 'TIFF', 'SVG'],
    isNew: true,
  },
  {
    id: 'audio-speech',
    label: 'Audio / Speech',
    formats: ['OGG', 'Opus', 'MP3', 'WAV', 'M4A', 'AAC', 'FLAC'],
  },
  { id: 'video', label: 'Video', formats: ['MP4', 'WebM', 'MOV'], isNew: true },
];

const CODE_SNIPPETS = {
  curl: `# 1. Compile LaTeX document to publication PDF
CONVERSION_ID=$(curl -s -X POST "https://api.mill.celladoresystems.com/api/convert?auto_fix=true" \\
  -H "Authorization: Bearer $MYSTIRA_ACCESS_TOKEN" \\
  -F "file=@document.tex" | jq -r '.id')

# 2. Download the rendered publication PDF
curl -H "Authorization: Bearer $MYSTIRA_ACCESS_TOKEN" \\
  "https://api.mill.celladoresystems.com/api/download/$CONVERSION_ID" \\
  --output document.pdf

# 3. Transcode audio note (e.g. OGG to MP3)
AUDIO_ID=$(curl -s -X POST "https://api.mill.celladoresystems.com/api/convert-audio?target_format=mp3&bitrate=192k" \\
  -H "Authorization: Bearer $MYSTIRA_ACCESS_TOKEN" \\
  -F "file=@voice_memo.ogg" | jq -r '.id')

curl -H "Authorization: Bearer $MYSTIRA_ACCESS_TOKEN" \\
  "https://api.mill.celladoresystems.com/api/download-audio/$AUDIO_ID" \\
  --output voice_memo.mp3

# 4. Convert an image (e.g. PNG screenshot to lean WebP)
IMAGE_ID=$(curl -s -X POST "https://api.mill.celladoresystems.com/api/convert-image?target_format=webp&quality=web" \\
  -H "Authorization: Bearer $MYSTIRA_ACCESS_TOKEN" \\
  -F "file=@banner.png" | jq -r '.id')

curl -H "Authorization: Bearer $MYSTIRA_ACCESS_TOKEN" \\
  "https://api.mill.celladoresystems.com/api/download-image/$IMAGE_ID" \\
  --output banner.webp`,
  python: `from xtox.core import DocumentConverter

# Initialize converter with local output directory
converter = DocumentConverter(output_dir="./dist")

# 1. Compile LaTeX into publication PDF with syntax error recovery
pdf_path = converter.latex_to_pdf("research_brief.tex")

# 2. Transform Markdown document to publication PDF
md_pdf_path = converter.markdown_to_pdf("brief.md", refinement_level=2)

# 3. Transcode audio formats via authenticated REST API
# POST /api/convert-audio with target_format and bitrate

# 4. Convert JPEG, PNG, WebP, BMP, TIFF, or GIF input to SVG output
# POST /api/convert-image with target_format and quality ('high'|'medium'|'low'|'web')`,
  typescript: `// 1. Submit audio transcoding task
const formData = new FormData();
formData.append('file', audioFile);
formData.append('target_format', 'mp3');
formData.append('bitrate', '192k');

const response = await fetch('https://api.mill.celladoresystems.com/api/convert-audio', {
  method: 'POST',
  headers: {
    Authorization: \`Bearer \${accessToken}\`,
  },
  body: formData,
});

const { id } = await response.json();

// 2. Download the transcoded audio
const audioBlob = await fetch(\`https://api.mill.celladoresystems.com/api/download-audio/\${id}\`, {
  headers: {
    Authorization: \`Bearer \${accessToken}\`,
  },
}).then(res => res.blob());

// 3. Convert an image the same way — swap the endpoint and form fields
const imageForm = new FormData();
imageForm.append('file', imageFile);

const imageResponse = await fetch(
  'https://api.mill.celladoresystems.com/api/convert-image?target_format=webp&quality=web',
  {
    method: 'POST',
    headers: { Authorization: \`Bearer \${accessToken}\` },
    body: imageForm,
  }
);

const { id: imageId } = await imageResponse.json();`,
};

const FORMAT_ROUTES = {
  markdown: {
    name: 'Markdown (.md)',
    targets: ['PDF Publication', 'HTML', 'DOCX'],
    engine: 'Typography & Layout Engine',
    latency: 'Toolchain dependent',
    badges: ['Automated PDF Layout', 'Header Hierarchy', 'Table Styling'],
  },
  latex: {
    name: 'LaTeX Source (.tex)',
    targets: ['Typeset PDF'],
    engine: 'TeX Live Compiler + Syntax Auto-Fix',
    latency: 'Toolchain dependent',
    badges: ['Math Formula Rendering', 'Syntax Error Recovery', 'Vector Graphics'],
  },
  ogg: {
    name: 'WhatsApp / Voice (.ogg/.opus)',
    targets: ['Formatted Transcript (.txt)', 'MP3 Audio (320k)', 'WAV Lossless'],
    engine: 'Foundry Whisper & FFmpeg Pipeline',
    latency: 'Provider dependent',
    badges: ['Ephemeral by Default', 'Language Detection', 'Scoped Delegation'],
  },
  audio: {
    name: 'Standard Audio (.mp3/.wav/.flac)',
    targets: ['MP3 Delivery (192k/320k)', 'OGG Opus (Streaming)', 'Formatted Transcript'],
    engine: 'High-Fidelity Audio Transcoder',
    latency: 'File dependent',
    badges: ['Bitrate Selection', 'Format Conversion', 'Sample Rate Selection'],
  },
  image: {
    name: 'Images (.jpg/.png/.webp/...)',
    targets: [
      'WebP (Lossy/Lossless)',
      'JPEG (Quality Tuned)',
      'PNG (Lossless)',
      'BMP / TIFF / GIF',
      'SVG (Deterministic Vector)',
    ],
    engine: 'Pillow Transcoder & Vectorizer',
    latency: 'File dependent',
    badges: ['EXIF Auto-Orientation', 'Quality & Target-Size Presets', 'Aspect-Preserving Resize'],
  },
  video: {
    name: 'Video (.mp4/.mov/.mkv/.webm/...)',
    targets: ['MP4 (H.264)', 'WebM (VP9)', 'MOV (H.264)'],
    engine: 'Bounded Local FFmpeg Pipeline',
    latency: '≤ 5 min bound',
    badges: ['ffprobe Metadata', 'Resolution Ceiling', 'Private 7-Day Artifact'],
  },
};

const FAQ_ITEMS = [
  {
    question: 'What input and output formats does Mill support?',
    answer:
      'Mill supports Markdown, HTML, plain text, DOCX, and LaTeX document routes. Audio supports OGG, Opus, WAV, MP3, M4A, AAC, and FLAC; images support JPEG, PNG, WebP, BMP, TIFF, GIF, and deterministic raster-to-SVG output; and deterministic local video transcoding supports MP4, WebM, and MOV outputs from common video sources.',
  },
  {
    question: 'What are the maximum file upload limits?',
    answer:
      'Video files up to 100 MB, audio files up to 50 MB, image files up to 20 MB, and document files up to 10 MB are supported per conversion in the standard workspace.',
  },
  {
    question: 'How do image quality presets work?',
    answer:
      'Choose from four quality presets—high, medium, low, or web—or set an exact quality from 1–100. EXIF orientation is corrected automatically, and JPEG output is flattened cleanly from transparent PNG or WebP sources.',
  },
  {
    question: 'How is privacy and data retention handled for audio and transcripts?',
    answer:
      'Voice transcription is ephemeral by default, processing audio in memory and persisting transcripts only when retain=true is explicitly requested. Workspace documents and converted artifacts are isolated within your private Mystira authenticated session.',
  },
  {
    question: 'How does automated syntax repair (auto-fix) work?',
    answer:
      'When enabled, Mill attempts bounded repairs for common LaTeX structural errors before compilation. Results depend on the source document and local TeX toolchain, and unsuccessful repairs are returned as explicit errors.',
  },
  {
    question: 'How is workspace access secured with Mystira Identity?',
    answer:
      'Mill uses Mystira Identity Authorization Code with PKCE for the private workspace. Conversion routes require validated bearer tokens, while public API documentation and health routes remain intentionally unauthenticated.',
  },
];

export function MarketingPage({
  authControl,
  checkingSession = false,
  oidcConfigured = false,
  onOpenWorkspace = () => {},
}) {
  const [activePreview, setActivePreview] = useState('markdown');
  const [theme, setTheme] = useState('paper'); // 'paper' | 'blueprint'
  const [activeCodeLang, setActiveCodeLang] = useState('curl');
  const [copiedCode, setCopiedCode] = useState(false);
  const [selectedRoute, setSelectedRoute] = useState('markdown');
  const [openFaq, setOpenFaq] = useState(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const playbackTimerRef = useRef(null);
  const copyTimerRef = useRef(null);

  // Clean up all timers on unmount
  useEffect(() => {
    return () => {
      if (playbackTimerRef.current) clearTimeout(playbackTimerRef.current);
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  // Audio simulation playback completion effect
  useEffect(() => {
    if (isPlayingAudio) {
      playbackTimerRef.current = setTimeout(() => {
        setIsPlayingAudio(false);
        playbackTimerRef.current = null;
      }, 3500);
    } else if (playbackTimerRef.current) {
      clearTimeout(playbackTimerRef.current);
      playbackTimerRef.current = null;
    }

    return () => {
      if (playbackTimerRef.current) {
        clearTimeout(playbackTimerRef.current);
        playbackTimerRef.current = null;
      }
    };
  }, [isPlayingAudio]);

  // Keyboard shortcut listener (1, 2, 3, 4 for preview tabs)
  useEffect(() => {
    const handleKeyDown = e => {
      // Ignore if user is typing in an input/textarea
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;

      if (e.key === '1') setActivePreview('markdown');
      if (e.key === '2') setActivePreview('audio');
      if (e.key === '3') setActivePreview('latex');
      if (e.key === '4') setActivePreview('image');
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleCopyCode = async () => {
    if (copyTimerRef.current) {
      clearTimeout(copyTimerRef.current);
      copyTimerRef.current = null;
    }

    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(CODE_SNIPPETS[activeCodeLang]);
        setCopiedCode(true);
        copyTimerRef.current = setTimeout(() => {
          setCopiedCode(false);
          copyTimerRef.current = null;
        }, 2000);
      } else {
        setCopiedCode(false);
      }
    } catch {
      setCopiedCode(false);
    }
  };

  const toggleTheme = () => {
    setTheme(prev => (prev === 'paper' ? 'blueprint' : 'paper'));
  };

  const toggleAudioSimulation = () => {
    setIsPlayingAudio(prev => !prev);
  };

  const routeData = FORMAT_ROUTES[selectedRoute] || FORMAT_ROUTES.markdown;

  return (
    <div className={`marketing-page theme-${theme}`}>
      <a href="#marketing-main" className="skip-link">
        Skip to main content
      </a>

      {/* Navigation */}
      <header className="marketing-nav" aria-label="Primary navigation">
        <a className="marketing-wordmark" href="/" aria-label="Mill home">
          <img className="wordmark-icon" src="/mill-mark.svg" alt="" aria-hidden="true" />
          <span>Mill</span>
        </a>

        <div className="marketing-nav-links">
          <a className="marketing-nav-anchor" href="#capabilities">
            Capabilities
          </a>
          <a className="marketing-nav-anchor" href="#matrix">
            Format Matrix
          </a>
          <a className="marketing-nav-anchor" href="#developers">
            API & SDK
          </a>
          <a className="marketing-nav-anchor" href="#faq">
            FAQ
          </a>
          <button
            onClick={toggleTheme}
            className="theme-toggle-btn"
            aria-label={`Switch to ${theme === 'paper' ? 'Blueprint' : 'Paper'} mode`}
            title={`Switch to ${theme === 'paper' ? 'Blueprint' : 'Paper'} mode`}
          >
            {theme === 'paper' ? '🌙 Blueprint' : '☀️ Paper'}
          </button>
          <button
            className="marketing-nav-link"
            type="button"
            onClick={onOpenWorkspace}
            disabled={!oidcConfigured || checkingSession}
          >
            Open workspace
          </button>
        </div>
      </header>

      <main id="marketing-main">
        {/* Hero Section */}
        <section className="marketing-hero">
          <div className="hero-copy">
            <div className="hero-badge">
              <span className="badge-pulse" aria-hidden="true" />
              <span className="hero-kicker">Universal Format & Media Transformation</span>
            </div>
            <h1>
              Move the meaning.
              <span>Perfect the format.</span>
            </h1>
            <p className="hero-summary">
              Reshape Markdown, HTML, plain text, and DOCX; transcode audio and transcribe voice
              notes; or convert images with a live source preview, exact quality controls,
              privacy-safe metadata handling, and useful size history—all within a private,
              authenticated workspace.
            </p>
            <div className="hero-action-row" id="sign-in">
              {authControl}
              <a className="text-link" href="#capabilities">
                Explore capabilities <span aria-hidden="true">↓</span>
              </a>
            </div>
            <p className="session-note" role="status">
              {!oidcConfigured
                ? 'Mystira sign-in is not configured for this deployment. The workspace remains unavailable.'
                : checkingSession
                  ? 'Checking your Mystira session…'
                  : 'Your workspace opens after Mystira Identity verifies your session.'}
            </p>
          </div>

          {/* Interactive Transformation Showcase Sandbox */}
          <div
            className="format-workbench"
            aria-label="Interactive document and media transformation preview"
          >
            <div className="workbench-header">
              <div className="workbench-ruler" aria-hidden="true">
                <span>INPUT</span>
                <span>ENGINE</span>
                <span>OUTPUT</span>
              </div>
              <div
                className="preview-tab-row"
                role="tablist"
                aria-label="Interactive conversion showcase"
              >
                {PREVIEW_MODES.map(mode => (
                  <button
                    key={mode.id}
                    role="tab"
                    id={`tab-${mode.id}`}
                    aria-selected={activePreview === mode.id}
                    aria-controls={`panel-${mode.id}`}
                    onClick={() => setActivePreview(mode.id)}
                    className={`preview-tab-button ${activePreview === mode.id ? 'is-active' : ''}`}
                  >
                    <div className="preview-tab-header-row">
                      <span className="preview-tab-category">{mode.category}</span>
                      <span className="preview-tab-key" aria-hidden="true">
                        [{mode.key}]
                      </span>
                    </div>
                    <span className="preview-tab-title">{mode.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Markdown to PDF Preview (Flagship) */}
            <div
              id="panel-markdown"
              role="tabpanel"
              aria-labelledby="tab-markdown"
              hidden={activePreview !== 'markdown'}
              className="workbench-stage"
            >
              <div className="format-track">
                <article className="format-sheet source-sheet doc-preview">
                  <span className="format-tab">.MD</span>
                  <div className="code-block">
                    <p className="code-heading"># Quarterly Research Brief</p>
                    <p className="code-meta">**Author:** Engineering Team</p>
                    <p className="code-line code-line-long">Transform unstructured content</p>
                    <p className="code-line code-line-mid">into publication-grade documents.</p>
                    <p className="code-badge">[Status: Ready for Review]</p>
                  </div>
                </article>
                <div className="transform-beam" aria-hidden="true">
                  <span className="beam-arrow">→</span>
                  <span className="beam-label">Typography & Layout</span>
                </div>
                <article className="format-sheet output-sheet doc-output">
                  <span className="format-tab">.PDF</span>
                  <div className="pdf-badge">PUBLICATION READY</div>
                  <div className="pdf-heading">Quarterly Research Brief</div>
                  <div className="pdf-author">Engineering Team • Verified Output</div>
                  <div className="pdf-rule" />
                  <p className="pdf-summary">
                    Cleanly formatted typography, headers, and metadata compiled into a shareable
                    document.
                  </p>
                </article>
              </div>
              <div className="preview-footer-strip">
                <span className="strip-tag">DOCUMENTS</span>
                <span className="strip-detail">Automated typography, margins & header styling</span>
                <span className="strip-status">READY</span>
              </div>
            </div>

            {/* Audio to Text / Transcode Preview */}
            <div
              id="panel-audio"
              role="tabpanel"
              aria-labelledby="tab-audio"
              hidden={activePreview !== 'audio'}
              className="workbench-stage"
            >
              <div className="format-track">
                <article className="format-sheet source-sheet audio-source-sheet">
                  <span className="format-tab">VOICE.OGG</span>
                  <div className="audio-spec-box">
                    <span className="audio-icon-glyph" aria-hidden="true">
                      🎙️
                    </span>
                    <p className="audio-spec-title">Field Recording 04</p>
                    <p className="audio-spec-meta">48 kHz • 192 kbps • 02:45</p>
                    <div
                      className={`waveform-display ${isPlayingAudio ? 'is-playing' : ''}`}
                      aria-hidden="true"
                    >
                      <span> </span>
                      <span>▂</span>
                      <span>▃</span>
                      <span>▅</span>
                      <span>▇</span>
                      <span>▅</span>
                      <span>▃</span>
                      <span>▆</span>
                      <span>█</span>
                      <span>▆</span>
                      <span>▃</span>
                      <span>▅</span>
                      <span>▂</span>
                    </div>
                    <button
                      onClick={toggleAudioSimulation}
                      className="audio-sample-play-btn"
                      aria-pressed={isPlayingAudio}
                      aria-label={isPlayingAudio ? 'Pause audio snippet' : 'Play audio snippet'}
                    >
                      {isPlayingAudio ? '⏸ Playing sample…' : '▶ Play audio snippet'}
                    </button>
                  </div>
                </article>
                <div className="transform-beam" aria-hidden="true">
                  <span className="beam-arrow">→</span>
                  <span className="beam-label">Whisper & Transcode</span>
                </div>
                <article className="format-sheet output-sheet audio-output-sheet">
                  <span className="format-tab">.TXT / .MP3</span>
                  <div className="pdf-badge audio-badge">EPHEMERAL TRANSCRIPTION</div>
                  <div className="transcript-box">
                    <p className="transcript-meta">00:01 • Speaker 1</p>
                    <p className={`transcript-quote ${isPlayingAudio ? 'is-highlighted' : ''}`}>
                      “We completed the format pipeline migration with complete fidelity.”
                    </p>
                    <div className="audio-options-tag">
                      Available: MP3 • WAV • FLAC • Transcript
                    </div>
                  </div>
                </article>
              </div>
              <div className="preview-footer-strip">
                <span className="strip-tag">AUDIO & VOICE</span>
                <span className="strip-detail">Format transcode & private transcription</span>
                <span className="strip-status">EPHEMERAL</span>
              </div>
            </div>

            {/* LaTeX to PDF Preview (Technical) */}
            <div
              id="panel-latex"
              role="tabpanel"
              aria-labelledby="tab-latex"
              hidden={activePreview !== 'latex'}
              className="workbench-stage"
            >
              <div className="format-track">
                <article className="format-sheet source-sheet latex-sheet">
                  <span className="format-tab">.TEX</span>
                  <p className="code-line code-line-long">\documentclass&#123;article&#125;</p>
                  <p className="code-line code-line-short">\begin&#123;document&#125;</p>
                  <p className="code-line code-line-mid">
                    \int_&#123;0&#125;^&#123;\infty&#125; e^&#123;-x^2&#125; dx =
                    \frac&#123;\sqrt&#123;\pi&#125;&#125;&#123;2&#125;
                  </p>
                  <p className="code-line code-line-short">\end&#123;document&#125;</p>
                </article>
                <div className="transform-beam" aria-hidden="true">
                  <span className="beam-arrow">→</span>
                  <span className="beam-label">Auto-fix & Compile</span>
                </div>
                <article className="format-sheet output-sheet latex-output-sheet">
                  <span className="format-tab">.PDF</span>
                  <div className="pdf-heading">Gaussian Integral Formulation</div>
                  <div className="pdf-rule" />
                  <p className="typeset-math">∫₀^∞ e⁻ˣ² dx = √π / 2</p>
                  <p className="typeset-note">Auto-repaired documentclass & compiled</p>
                </article>
              </div>
              <div className="preview-footer-strip">
                <span className="strip-tag">TYPESETTING</span>
                <span className="strip-detail">Error auto-recovery & mathematical rendering</span>
                <span className="strip-status">COMPILED</span>
              </div>
            </div>

            {/* Image Format Conversion Preview */}
            <div
              id="panel-image"
              role="tabpanel"
              aria-labelledby="tab-image"
              hidden={activePreview !== 'image'}
              className="workbench-stage"
            >
              <div className="format-track">
                <article className="format-sheet source-sheet image-source-sheet">
                  <span className="format-tab">PHOTO.JPEG</span>
                  <div className="audio-spec-box">
                    <span className="audio-icon-glyph" aria-hidden="true">
                      🖼️
                    </span>
                    <p className="audio-spec-title">Product Hero Shot</p>
                    <p className="audio-spec-meta">4032×3024 • sRGB • 3.8 MB</p>
                    <p className="code-badge">[EXIF: Orientation 6]</p>
                  </div>
                </article>
                <div className="transform-beam" aria-hidden="true">
                  <span className="beam-arrow">→</span>
                  <span className="beam-label">Pillow Transcoder</span>
                </div>
                <article className="format-sheet output-sheet image-output-sheet">
                  <span className="format-tab">PHOTO.WEBP</span>
                  <div className="pdf-badge image-badge">-71% FILE SIZE</div>
                  <div className="audio-spec-box">
                    <p className="audio-spec-meta">3024×4032 • Auto-Oriented • 1.1 MB</p>
                    <div className="audio-options-tag">
                      Available: JPEG • PNG • WebP • BMP • TIFF • GIF • SVG
                    </div>
                  </div>
                </article>
              </div>
              <div className="preview-footer-strip">
                <span className="strip-tag">IMAGES</span>
                <span className="strip-detail">
                  EXIF auto-orient, quality presets & target-size compression
                </span>
                <span className="strip-status">OPTIMIZED</span>
              </div>
            </div>
          </div>
        </section>

        {/* Verifiable release and privacy properties */}
        <section className="trust-metrics-band" aria-label="Release and security properties">
          <div className="metric-item">
            <span className="metric-value">Live</span>
            <span className="metric-label">Frontend & API</span>
          </div>
          <div className="metric-divider" aria-hidden="true" />
          <div className="metric-item">
            <span className="metric-value">Default</span>
            <span className="metric-label">Ephemeral Transcription</span>
          </div>
          <div className="metric-divider" aria-hidden="true" />
          <div className="metric-item">
            <span className="metric-value">Scoped</span>
            <span className="metric-label">Delegated API Access</span>
          </div>
          <div className="metric-divider" aria-hidden="true" />
          <div className="metric-item">
            <span className="metric-value">Alpha</span>
            <span className="metric-label">Current Release Track</span>
          </div>
        </section>

        {/* Supported formats grouped by media type */}
        <section className="format-ticker-band" aria-label="Supported formats matrix">
          <h2 className="ticker-label">Supported formats</h2>
          <div className="format-groups">
            {SUPPORTED_FORMAT_GROUPS.map(group => (
              <section
                key={group.id}
                className={`format-group${group.isNew ? ' format-group-new' : ''}`}
                aria-labelledby={`format-${group.id}`}
              >
                <h3 id={`format-${group.id}`}>
                  <span>[{group.label}]</span>
                  {group.isNew && <span className="status-pill status-new">[New]</span>}
                </h3>
                <div className="ticker-chips">
                  {group.formats.map(format => (
                    <span key={format} className="format-chip">
                      {format}
                    </span>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </section>

        {/* Capabilities Grid Section */}
        <section
          className="workflow-section"
          id="capabilities"
          aria-labelledby="capabilities-title"
        >
          <div className="section-heading">
            <div>
              <p className="section-kicker">Core Capabilities</p>
              <h2 id="capabilities-title">Engineered for clean, faithful transformations.</h2>
            </div>
            <p className="section-lead">
              Mill routes supported sources through explicit local or authenticated conversion
              boundaries and returns concrete output artifacts.
            </p>
          </div>
          <div className="capabilities-grid">
            <article className="capability-card">
              <div className="card-top">
                <span className="workflow-symbol" aria-hidden="true">
                  ¶
                </span>
                <span className="card-badge">Document</span>
              </div>
              <h3>Universal Document Publishing</h3>
              <p>
                Transform Markdown, formatted briefs, and documentation into pristine,
                publication-grade PDFs with clean typographic hierarchy and page formatting.
              </p>
            </article>

            <article className="capability-card">
              <div className="card-top">
                <span className="workflow-symbol" aria-hidden="true">
                  ▶
                </span>
                <span className="status-pill status-new">[New]</span>
              </div>
              <h3>Bounded Local Video Transcoding</h3>
              <p>
                Convert common video sources to MP4, WebM, or MOV with quality and resolution
                controls, ffprobe metadata, size outcomes, private downloads, and retained history.
              </p>
            </article>

            <article className="capability-card">
              <div className="card-top">
                <span className="workflow-symbol" aria-hidden="true">
                  ◖◗
                </span>
                <span className="card-badge">Audio Engine</span>
              </div>
              <h3>High-Fidelity Audio Reshaping</h3>
              <p>
                Transcode between OGG, Opus, MP3, WAV, M4A, AAC, and FLAC. Fine-tune bitrates and
                sample rates for delivery, archiving, or lightweight streaming.
              </p>
            </article>

            <article className="capability-card">
              <div className="card-top">
                <span className="workflow-symbol" aria-hidden="true">
                  “ ”
                </span>
                <span className="card-badge">Privacy First</span>
              </div>
              <h3>Ephemeral Voice Transcription</h3>
              <p>
                Convert spoken audio, interviews, and voice memos into structured text—ephemeral by
                default, and persisted only when retain=true is explicitly requested.
              </p>
            </article>

            <article className="capability-card">
              <div className="card-top">
                <span className="workflow-symbol" aria-hidden="true">
                  ⚡
                </span>
                <span className="card-badge">Text</span>
              </div>
              <h3>Deterministic Text Reshaping</h3>
              <p>
                Convert Markdown, HTML, plain text, and DOCX through bounded, deterministic
                transformations with downloadable results.
              </p>
            </article>

            <article className="capability-card">
              <div className="card-top">
                <span className="workflow-symbol" aria-hidden="true">
                  &#123; &#125;
                </span>
                <span className="card-badge">Technical</span>
              </div>
              <h3>Precision LaTeX Typesetting</h3>
              <p>
                Compile scientific papers, math formulas, and TeX documents with optional bounded
                syntax repair and explicit compilation errors.
              </p>
            </article>

            <article className="capability-card">
              <div className="card-top">
                <span className="workflow-symbol" aria-hidden="true">
                  🖼
                </span>
                <span className="card-badge">Images</span>
              </div>
              <h3>Image Reformatting & Vectorization</h3>
              <p>
                Convert JPEG, PNG, WebP, BMP, TIFF, and GIF into each other or generate
                deterministic SVG vectors, with previews, bounded controls, privacy-safe metadata
                handling, and input-to-output size history.
              </p>
            </article>
          </div>
        </section>

        {/* Interactive Format Route Matrix Section */}
        <section className="format-route-section" id="matrix" aria-labelledby="matrix-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Interactive Route Inspector</p>
              <h2 id="matrix-title">Choose a source format. See the conversion engine.</h2>
            </div>
            <p className="section-lead">
              Inspect how Mill routes and transforms various file formats.
            </p>
          </div>

          <div className="route-inspector-card">
            <div className="route-selector-row">
              <span className="route-select-label">FROM SOURCE:</span>
              <div className="route-buttons" role="group" aria-label="Source format selection">
                {Object.keys(FORMAT_ROUTES).map(key => (
                  <button
                    key={key}
                    onClick={() => setSelectedRoute(key)}
                    className={`route-btn ${selectedRoute === key ? 'is-active' : ''}`}
                  >
                    {FORMAT_ROUTES[key].name}
                  </button>
                ))}
              </div>
            </div>

            <div className="route-details-panel">
              <div className="route-col">
                <span className="route-subhead">ENGINE / PIPELINE</span>
                <p className="route-engine-name">{routeData.engine}</p>
                <div className="route-metric-pill">
                  {selectedRoute === 'video' ? 'Processing bound' : 'Execution'}:{' '}
                  {routeData.latency}
                </div>
              </div>

              <div className="route-col">
                <span className="route-subhead">AVAILABLE OUTPUT TARGETS</span>
                <ul className="route-targets-list">
                  {routeData.targets.map(target => (
                    <li key={target}>→ {target}</li>
                  ))}
                </ul>
              </div>

              <div className="route-col">
                <span className="route-subhead">PIPELINE GUARANTEES</span>
                <div className="route-badges-grid">
                  {routeData.badges.map(b => (
                    <span key={b} className="route-badge-chip">
                      ✓ {b}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Developer & API Section */}
        <section className="developer-section" id="developers" aria-labelledby="dev-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">API-First Architecture</p>
              <h2 id="dev-title">Integrate conversion through explicit boundaries.</h2>
            </div>
            <p className="section-lead">
              Workspace conversions use the authenticated REST API. Local document conversion is
              available through the compatible Python package. The scoped npm CLI is approved for
              this alpha and becomes installable after registry publication.
            </p>
          </div>

          <p className="section-lead">
            Scoped command after publication: <code>npx @celladore/mill --help</code>. The unrelated
            bare command <code>npx mill</code> is not supported.
          </p>

          <div className="code-showcase-box">
            <div className="code-header">
              <div className="code-tabs" role="tablist" aria-label="Code language selection">
                {['curl', 'python', 'typescript'].map(lang => (
                  <button
                    key={lang}
                    role="tab"
                    id={`code-tab-${lang}`}
                    aria-selected={activeCodeLang === lang}
                    aria-controls={`code-panel-${lang}`}
                    onClick={() => setActiveCodeLang(lang)}
                    className={`code-tab ${activeCodeLang === lang ? 'is-active' : ''}`}
                  >
                    {lang === 'curl'
                      ? 'cURL'
                      : lang === 'python'
                        ? 'Python package'
                        : 'TypeScript / REST'}
                  </button>
                ))}
              </div>

              <button
                onClick={handleCopyCode}
                className="copy-code-btn"
                aria-label="Copy code to clipboard"
              >
                {copiedCode ? '✓ Copied' : 'Copy snippet'}
              </button>
            </div>

            {['curl', 'python', 'typescript'].map(lang => (
              <pre
                key={lang}
                id={`code-panel-${lang}`}
                role="tabpanel"
                aria-labelledby={`code-tab-${lang}`}
                hidden={activeCodeLang !== lang}
                className="code-content"
              >
                <code>{CODE_SNIPPETS[lang]}</code>
              </pre>
            ))}
          </div>
        </section>

        {/* How It Works 3-Step Section */}
        <section className="how-it-works-section" id="how-it-works" aria-labelledby="how-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Simple, Transparent Flow</p>
              <h2 id="how-title">A focused path from source to useful.</h2>
            </div>
            <p className="section-lead">
              Three steps from raw input to your ideal delivery format.
            </p>
          </div>
          <div className="steps-grid">
            <div className="step-card">
              <span className="step-number">01</span>
              <h4>Ingest Source</h4>
              <p>
                Drag and drop your document or audio file into the authenticated workbench or stream
                via API.
              </p>
            </div>
            <div className="step-card">
              <span className="step-number">02</span>
              <h4>Select & Optimize</h4>
              <p>
                Choose your target format and, where supported, bounded syntax repair, image
                quality, or audio bitrate controls.
              </p>
            </div>
            <div className="step-card">
              <span className="step-number">03</span>
              <h4>Retrieve Output</h4>
              <p>
                Download the resulting PDF or media artifact, or copy generated text within your
                authenticated workspace.
              </p>
            </div>
          </div>
        </section>

        {/* FAQ Accordion Section */}
        <section className="faq-section" id="faq" aria-labelledby="faq-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Frequently Asked Questions</p>
              <h2 id="faq-title">Clear answers regarding privacy, limits & formats.</h2>
            </div>
            <p className="section-lead">Everything you need to know about working with Mill.</p>
          </div>

          <div className="faq-accordion">
            {FAQ_ITEMS.map((item, index) => {
              const isOpen = openFaq === index;
              return (
                <div key={item.question} className={`faq-item ${isOpen ? 'is-open' : ''}`}>
                  <button
                    className="faq-question-btn"
                    onClick={() => setOpenFaq(isOpen ? null : index)}
                    aria-expanded={isOpen}
                    aria-controls={`faq-answer-${index}`}
                  >
                    <span>{item.question}</span>
                    <span className="faq-icon" aria-hidden="true">
                      {isOpen ? '−' : '+'}
                    </span>
                  </button>
                  {isOpen && (
                    <div id={`faq-answer-${index}`} className="faq-answer-panel" role="region">
                      <p>{item.answer}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* Privacy Section */}
        <section className="privacy-band" aria-labelledby="privacy-title">
          <div>
            <p className="section-kicker">Private by default</p>
            <h2 id="privacy-title">The tools stay behind your identity.</h2>
          </div>
          <div className="privacy-details">
            <p>
              The public page explains the workbench. Files, conversion controls, and results appear
              only after sign-in, and API requests require a valid Mystira-issued access token.
            </p>
            <ul className="privacy-bullets">
              <li>Identity-gated workspace sessions via Mystira OIDC</li>
              <li>
                Ephemeral memory pipelines by default; persisted only when retain=true is explicitly
                requested
              </li>
              <li>Encrypted transport and isolated conversion environments</li>
            </ul>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="marketing-footer">
        <div className="footer-left">
          <span className="footer-brand">Mill by Celladore</span>
          <span className="footer-dot" aria-hidden="true">
            •
          </span>
          <span>Universal Document & Media Transformation</span>
        </div>
        <span className="footer-tagline">Formats change. Meaning stays.</span>
      </footer>
    </div>
  );
}
