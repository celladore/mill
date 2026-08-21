import { useEffect, useState } from 'react';

const PREVIEW_MODES = [
  { id: 'markdown', label: 'Markdown → PDF', category: 'Document', key: '1' },
  { id: 'audio', label: 'Voice → Transcript', category: 'Voice & Audio', key: '2' },
  { id: 'ai', label: 'Docs → AI Context', category: 'LLM Ready', key: '3' },
  { id: 'latex', label: 'LaTeX → Typeset', category: 'Technical', key: '4' },
];

const CODE_SNIPPETS = {
  curl: `# Convert Markdown to Publication PDF
curl -X POST https://api.xtox.celladoresystems.com/api/convert \\
  -H "Authorization: Bearer $MYSTIRA_ACCESS_TOKEN" \\
  -F "file=@research_brief.md" \\
  -F "target_format=pdf" \\
  -F "auto_style=true" \\
  --output research_brief.pdf

# Transcribe voice memo with zero data retention
curl -X POST https://api.xtox.celladoresystems.com/api/transcribe-audio \\
  -H "Authorization: Bearer $MYSTIRA_ACCESS_TOKEN" \\
  -F "file=@voice_memo.ogg" \\
  -F "ephemeral=true"`,
  python: `from xtox import DocumentConverter

# Initialize authenticated client
converter = DocumentConverter()

# 1. Transform Markdown into a styled publication PDF
pdf_path = converter.markdown_to_pdf(
    "research_brief.md",
    output_dir="./dist",
    quality="publication"
)

# 2. Extract token-optimized semantic context for RAG / Claude
ai_context = converter.to_ai_text(
    "research_brief.md",
    target_model="claude-3-opus",
    preserve_hierarchy=True
)

# 3. Ephemeral voice transcription (zero retention)
transcript = converter.transcribe_audio("voice_memo.ogg", ephemeral=True)
print(transcript.text)`,
  typescript: `import { XtoxClient } from '@celladore/xtox';

const client = new XtoxClient({
  accessToken: process.env.MYSTIRA_ACCESS_TOKEN,
  endpoint: 'https://api.xtox.celladoresystems.com',
});

// Convert document or audio with full type safety
const pdfStream = await client.documents.convert({
  file: documentBuffer,
  filename: 'quarterly_report.md',
  format: 'pdf',
});

// Transcribe audio note with strict privacy guarantees
const transcript = await client.audio.transcribe({
  file: audioBuffer,
  filename: 'standup_note.ogg',
  ephemeral: true,
});

console.log(\`Words detected: \${transcript.words.length}\`);`,
};

const FORMAT_ROUTES = {
  markdown: {
    name: 'Markdown (.md)',
    targets: ['PDF Publication', 'AI-Ready Context', 'Plain Text'],
    engine: 'Typography & Layout Engine',
    latency: '< 320ms',
    badges: ['Automated CSS/PDF Layout', 'Header Hierarchy', 'Table Styling'],
  },
  docx: {
    name: 'Word Document (.docx)',
    targets: ['PDF Publication', 'AI-Ready Context', 'Clean Markdown'],
    engine: 'Document Structural Parser',
    latency: '< 450ms',
    badges: ['Lossless Table Extraction', 'Font Normalization', 'Clean Metadata'],
  },
  ogg: {
    name: 'WhatsApp / Voice (.ogg/.opus)',
    targets: ['Formatted Transcript (.txt)', 'MP3 Audio (320k)', 'WAV Lossless'],
    engine: 'Foundry Whisper & FFmpeg Pipeline',
    latency: '< 1.2s',
    badges: ['Zero Data Retention', 'Speech Diarization', '48kHz Resampling'],
  },
  latex: {
    name: 'LaTeX Source (.tex)',
    targets: ['Typeset PDF', 'AI-Ready Text'],
    engine: 'TeX Live Compiler + Syntax Auto-Fix',
    latency: '< 650ms',
    badges: ['Math Formula Rendering', 'Syntax Error Recovery', 'Vector Graphics'],
  },
  flac: {
    name: 'Lossless Audio (.flac/.wav)',
    targets: ['MP3 Delivery (192k/320k)', 'OGG Opus (Streaming)', 'Formatted Transcript'],
    engine: 'High-Fidelity Audio Transcoder',
    latency: '< 800ms',
    badges: ['Bitrate Shaping', 'Dynamic Range Control', 'Sample Rate Normalization'],
  },
};

const FAQ_ITEMS = [
  {
    question: 'What input and output formats does XtOX support?',
    answer:
      'XtOX supports Markdown (.md), Microsoft Word (.docx), LaTeX (.tex), PDF, and rich text documents for publishing and AI extraction. For audio, XtOX processes OGG, Opus, WAV, MP3, M4A, AAC, and FLAC for transcoding and speech-to-text transcription.',
  },
  {
    question: 'What are the maximum file upload limits?',
    answer:
      'Audio files up to 50 MB and document files up to 10 MB are supported per conversion in the standard workspace.',
  },
  {
    question: 'What does "zero data retention" mean for my audio and transcripts?',
    answer:
      'Audio processing and voice transcription run strictly in ephemeral memory pipelines. Audio buffers and transcription outputs are immediately freed upon response delivery and are never written to long-term database storage unless you explicitly choose to save them.',
  },
  {
    question: 'How does automated syntax repair (auto-fix) work?',
    answer:
      'When enabled, XtOX analyzes document structure and automatically resolves common formatting syntax errors—such as missing documentclass headers, unclosed math blocks, broken markdown fences, and encoding artifacts—ensuring reliable compilation on the first pass.',
  },
  {
    question: 'How is workspace access secured with Mystira Identity?',
    answer:
      'XtOX is natively integrated with Mystira Identity OIDC. All conversion tools and API endpoints require cryptographically verified access tokens with strict scope isolation, guaranteeing enterprise-grade identity boundaries.',
  },
];

export function MarketingPage({ authControl, checkingSession = false, oidcConfigured = false }) {
  const [activePreview, setActivePreview] = useState('markdown');
  const [theme, setTheme] = useState('paper'); // 'paper' | 'blueprint'
  const [activeCodeLang, setActiveCodeLang] = useState('curl');
  const [copiedCode, setCopiedCode] = useState(false);
  const [selectedRoute, setSelectedRoute] = useState('markdown');
  const [openFaq, setOpenFaq] = useState(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  // Keyboard shortcut listener (1, 2, 3, 4 for preview tabs)
  useEffect(() => {
    const handleKeyDown = e => {
      // Ignore if user is typing in an input/textarea
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;

      if (e.key === '1') setActivePreview('markdown');
      if (e.key === '2') setActivePreview('audio');
      if (e.key === '3') setActivePreview('ai');
      if (e.key === '4') setActivePreview('latex');
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(CODE_SNIPPETS[activeCodeLang]);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const toggleTheme = () => {
    setTheme(prev => (prev === 'paper' ? 'blueprint' : 'paper'));
  };

  const toggleAudioSimulation = () => {
    setIsPlayingAudio(prev => !prev);
    if (!isPlayingAudio) {
      setTimeout(() => setIsPlayingAudio(false), 3500);
    }
  };

  const routeData = FORMAT_ROUTES[selectedRoute];

  return (
    <div className={`marketing-page theme-${theme}`}>
      <a href="#marketing-main" className="skip-link">
        Skip to main content
      </a>

      {/* Navigation */}
      <header className="marketing-nav" aria-label="Primary navigation">
        <a className="marketing-wordmark" href="/" aria-label="XtOX home">
          <img className="wordmark-icon" src="/xtox-mark.svg" alt="" aria-hidden="true" />
          <span>XtOX</span>
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
          <a className="marketing-nav-link" href="#sign-in">
            Open workspace
          </a>
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
              Transform Markdown and documents into publication-ready PDFs, transcode and transcribe
              voice recordings with zero data retention, and convert technical sources into AI-ready
              context—all within a private, authenticated workspace.
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
          <div className="format-workbench" aria-label="Interactive document and media transformation preview">
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
            {activePreview === 'markdown' && (
              <div
                id="panel-markdown"
                role="tabpanel"
                aria-labelledby="tab-markdown"
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
                      Cleanly formatted typography, headers, and metadata compiled into a
                      shareable document.
                    </p>
                  </article>
                </div>
                <div className="preview-footer-strip">
                  <span className="strip-tag">DOCUMENTS</span>
                  <span className="strip-detail">Automated typography, margins & header styling</span>
                  <span className="strip-status">READY</span>
                </div>
              </div>
            )}

            {/* Audio to Text / Transcode Preview */}
            {activePreview === 'audio' && (
              <div
                id="panel-audio"
                role="tabpanel"
                aria-labelledby="tab-audio"
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
                      <div className={`waveform-display ${isPlayingAudio ? 'is-playing' : ''}`} aria-hidden="true">
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
                        aria-label={isPlayingAudio ? 'Simulating audio playback' : 'Simulate audio snippet'}
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
                    <div className="pdf-badge audio-badge">ZERO DATA RETENTION</div>
                    <div className="transcript-box">
                      <p className="transcript-meta">00:01 • Speaker 1</p>
                      <p className={`transcript-quote ${isPlayingAudio ? 'is-highlighted' : ''}`}>
                        “We completed the format pipeline migration with complete fidelity.”
                      </p>
                      <div className="audio-options-tag">Available: MP3 • WAV • FLAC • Transcript</div>
                    </div>
                  </article>
                </div>
                <div className="preview-footer-strip">
                  <span className="strip-tag">AUDIO & VOICE</span>
                  <span className="strip-detail">Lossless transcode & private transcription</span>
                  <span className="strip-status">EPHEMERAL</span>
                </div>
              </div>
            )}

            {/* AI Context / LLM Ingestion Preview */}
            {activePreview === 'ai' && (
              <div
                id="panel-ai"
                role="tabpanel"
                aria-labelledby="tab-ai"
                className="workbench-stage"
              >
                <div className="format-track">
                  <article className="format-sheet source-sheet ai-source-sheet">
                    <span className="format-tab">RAW DOC / PDF</span>
                    <div className="code-block">
                      <p className="code-heading">54-Page Complex PDF</p>
                      <p className="code-meta">Nested tables, images & footnotes</p>
                      <p className="code-line code-line-long">Unstructured binary payload</p>
                      <p className="code-line code-line-mid">Non-semantic layout tokens</p>
                      <p className="code-badge">[Tokens: ~34,800 raw]</p>
                    </div>
                  </article>
                  <div className="transform-beam" aria-hidden="true">
                    <span className="beam-arrow">→</span>
                    <span className="beam-label">Token Optimizer</span>
                  </div>
                  <article className="format-sheet output-sheet ai-output-sheet">
                    <span className="format-tab">AI-READY MD</span>
                    <div className="pdf-badge ai-badge">⚡ -38% TOKENS SAVED</div>
                    <div className="ai-preview-box">
                      <p className="ai-frontmatter">---<br />title: System Architecture<br />tokens: 21,400<br />---</p>
                      <p className="ai-clean-sample"># Clean Semantic Hierarchy<br />• Key entities extracted<br />• RAG-optimized chunking</p>
                    </div>
                  </article>
                </div>
                <div className="preview-footer-strip">
                  <span className="strip-tag">LLM INGESTION</span>
                  <span className="strip-detail">Token compression & semantic markdown structure</span>
                  <span className="strip-status">OPTIMIZED</span>
                </div>
              </div>
            )}

            {/* LaTeX to PDF Preview (Technical) */}
            {activePreview === 'latex' && (
              <div
                id="panel-latex"
                role="tabpanel"
                aria-labelledby="tab-latex"
                className="workbench-stage"
              >
                <div className="format-track">
                  <article className="format-sheet source-sheet latex-sheet">
                    <span className="format-tab">.TEX</span>
                    <p className="code-line code-line-long">\documentclass&#123;article&#125;</p>
                    <p className="code-line code-line-short">\begin&#123;document&#125;</p>
                    <p className="code-line code-line-mid">\int_&#123;0&#125;^&#123;\infty&#125; e^&#123;-x^2&#125; dx = \frac&#123;\sqrt&#123;\pi&#125;&#125;&#123;2&#125;</p>
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
            )}
          </div>
        </section>

        {/* Performance & Trust Metrics Banner */}
        <section className="trust-metrics-band" aria-label="Performance and security metrics">
          <div className="metric-item">
            <span className="metric-value">&lt; 400ms</span>
            <span className="metric-label">Median Rendering Latency</span>
          </div>
          <div className="metric-divider" aria-hidden="true" />
          <div className="metric-item">
            <span className="metric-value">0-Byte</span>
            <span className="metric-label">Persistent Disk Retention</span>
          </div>
          <div className="metric-divider" aria-hidden="true" />
          <div className="metric-item">
            <span className="metric-value">48 kHz</span>
            <span className="metric-label">Lossless Audio Resampling</span>
          </div>
          <div className="metric-divider" aria-hidden="true" />
          <div className="metric-item">
            <span className="metric-value">100% OIDC</span>
            <span className="metric-label">Mystira Authenticated Sessions</span>
          </div>
        </section>

        {/* Format Support Ticker */}
        <section className="format-ticker-band" aria-label="Supported formats matrix">
          <div className="ticker-label">SUPPORTED FORMATS</div>
          <div className="ticker-chips">
            <span className="format-chip">Markdown</span>
            <span className="format-chip">PDF</span>
            <span className="format-chip">DOCX</span>
            <span className="format-chip">LaTeX</span>
            <span className="format-chip">OGG</span>
            <span className="format-chip">Opus</span>
            <span className="format-chip">MP3</span>
            <span className="format-chip">WAV</span>
            <span className="format-chip">M4A</span>
            <span className="format-chip">AAC</span>
            <span className="format-chip">FLAC</span>
            <span className="format-chip">AI-Ready Text</span>
          </div>
        </section>

        {/* Capabilities Grid Section */}
        <section className="workflow-section" id="capabilities" aria-labelledby="capabilities-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Core Capabilities</p>
              <h2 id="capabilities-title">Engineered for clean, faithful transformations.</h2>
            </div>
            <p className="section-lead">
              XtOX converts complex sources into clean, actionable formats without data bloat,
              leaky storage, or lost meaning.
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
                Transform Markdown, formatted briefs, and documentation into pristine, publication-grade
                PDFs with clean typographic hierarchy and page formatting.
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
                Convert spoken audio, interviews, and voice memos into structured text with zero
                server retention unless explicitly saved by your workspace.
              </p>
            </article>

            <article className="capability-card">
              <div className="card-top">
                <span className="workflow-symbol" aria-hidden="true">
                  ⚡
                </span>
                <span className="card-badge">LLM Ready</span>
              </div>
              <h3>AI & LLM-Ready Ingestion</h3>
              <p>
                Extract clean, structured Markdown from multi-page PDFs and docs with automated
                token compression and semantic context tagging for AI workflows.
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
                Compile scientific papers, math formulas, and TeX documents with automated syntax
                repair and instant PDF generation.
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
              Inspect how XtOX routes and transforms various file formats.
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
                <div className="route-metric-pill">Avg. Speed: {routeData.latency}</div>
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
              <h2 id="dev-title">Integrate conversion into your pipelines in seconds.</h2>
            </div>
            <p className="section-lead">
              Every feature in the workspace is backed by our authenticated REST API and Python/TypeScript SDKs.
            </p>
          </div>

          <div className="code-showcase-box">
            <div className="code-header">
              <div className="code-tabs" role="tablist" aria-label="Code language selection">
                <button
                  role="tab"
                  aria-selected={activeCodeLang === 'curl'}
                  onClick={() => setActiveCodeLang('curl')}
                  className={`code-tab ${activeCodeLang === 'curl' ? 'is-active' : ''}`}
                >
                  cURL
                </button>
                <button
                  role="tab"
                  aria-selected={activeCodeLang === 'python'}
                  onClick={() => setActiveCodeLang('python')}
                  className={`code-tab ${activeCodeLang === 'python' ? 'is-active' : ''}`}
                >
                  Python SDK
                </button>
                <button
                  role="tab"
                  aria-selected={activeCodeLang === 'typescript'}
                  onClick={() => setActiveCodeLang('typescript')}
                  className={`code-tab ${activeCodeLang === 'typescript' ? 'is-active' : ''}`}
                >
                  TypeScript / Node
                </button>
              </div>

              <button onClick={handleCopyCode} className="copy-code-btn" aria-label="Copy code to clipboard">
                {copiedCode ? '✓ Copied' : 'Copy snippet'}
              </button>
            </div>

            <pre className="code-content">
              <code>{CODE_SNIPPETS[activeCodeLang]}</code>
            </pre>
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
              <p>Drag and drop your document or audio file into the authenticated workbench or stream via API.</p>
            </div>
            <div className="step-card">
              <span className="step-number">02</span>
              <h4>Select & Optimize</h4>
              <p>Choose your target format, enable automated syntax repair, token compression, or audio bitrate tuning.</p>
            </div>
            <div className="step-card">
              <span className="step-number">03</span>
              <h4>Instant Export</h4>
              <p>Download your publication PDF, transcoded audio, or copy clean text with complete privacy guarantees.</p>
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
            <p className="section-lead">
              Everything you need to know about working with XtOX.
            </p>
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
              <li>Ephemeral memory pipelines with zero unauthorized data retention</li>
              <li>Encrypted transport and isolated conversion environments</li>
            </ul>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="marketing-footer">
        <div className="footer-left">
          <span className="footer-brand">XtOX by Celladore</span>
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
