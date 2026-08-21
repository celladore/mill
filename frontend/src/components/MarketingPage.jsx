export function MarketingPage({ authControl, checkingSession = false }) {
  return (
    <div className="marketing-page">
      <a href="#marketing-main" className="skip-link">
        Skip to main content
      </a>

      <header className="marketing-nav" aria-label="Primary navigation">
        <a className="marketing-wordmark" href="/" aria-label="XtOX home">
          <span className="wordmark-mark" aria-hidden="true">
            X→X
          </span>
          <span>XtOX</span>
        </a>
        <a className="marketing-nav-link" href="#sign-in">
          Open workspace
        </a>
      </header>

      <main id="marketing-main">
        <section className="marketing-hero">
          <div className="hero-copy">
            <p className="hero-kicker">Document conversion workbench</p>
            <h1>
              Move the meaning.
              <span>Change the format.</span>
            </h1>
            <p className="hero-summary">
              Convert LaTeX into clean PDFs, reshape voice notes for delivery, or turn spoken audio
              into text—all from one private workspace.
            </p>
            <div className="hero-action-row" id="sign-in">
              {authControl}
              <a className="text-link" href="#how-it-works">
                See the workflow <span aria-hidden="true">↓</span>
              </a>
            </div>
            <p className="session-note" role="status">
              {checkingSession
                ? 'Checking your Mystira session…'
                : 'Your workspace opens after Mystira Identity verifies your session.'}
            </p>
          </div>

          <div className="format-workbench" aria-label="Example document transformation">
            <div className="workbench-ruler" aria-hidden="true">
              <span>INPUT</span>
              <span>TRANSFORM</span>
              <span>OUTPUT</span>
            </div>
            <div className="format-track">
              <article className="format-sheet source-sheet">
                <span className="format-tab">.TEX</span>
                <p className="code-line code-line-long">\documentclass&#123;article&#125;</p>
                <p className="code-line code-line-short">\begin&#123;document&#125;</p>
                <p className="code-line code-line-mid">Meaning, typeset.</p>
                <p className="code-line code-line-short">\end&#123;document&#125;</p>
              </article>
              <div className="transform-beam" aria-hidden="true">
                <span>→</span>
              </div>
              <article className="format-sheet output-sheet">
                <span className="format-tab">.PDF</span>
                <div className="pdf-heading">Meaning, typeset.</div>
                <div className="pdf-rule" />
                <p>A finished document, ready to share.</p>
              </article>
            </div>
            <div className="audio-strip">
              <span className="audio-label">VOICE.OGG</span>
              <span className="waveform" aria-hidden="true">
                ▁▃▆▂▇▄▂▅▁▆▃▇▂▄
              </span>
              <span className="audio-result">TEXT</span>
            </div>
          </div>
        </section>

        <section className="workflow-section" id="how-it-works" aria-labelledby="workflow-title">
          <div className="section-heading">
            <p className="section-kicker">One file in. The format you need out.</p>
            <h2 id="workflow-title">A focused path from source to useful.</h2>
          </div>
          <div className="workflow-grid">
            <article>
              <span className="workflow-symbol" aria-hidden="true">
                &#123; &#125;
              </span>
              <h3>Typeset LaTeX</h3>
              <p>
                Upload a .tex source, repair common structure errors when you choose, and download
                the PDF.
              </p>
            </article>
            <article>
              <span className="workflow-symbol" aria-hidden="true">
                ◖◗
              </span>
              <h3>Convert audio</h3>
              <p>
                Change OGG, Opus, WAV, MP3, M4A, AAC, or FLAC into the format and quality you need.
              </p>
            </article>
            <article>
              <span className="workflow-symbol" aria-hidden="true">
                “ ”
              </span>
              <h3>Transcribe privately</h3>
              <p>
                Send audio for transcription without retaining the transcript in XtOX unless
                retention is explicitly requested.
              </p>
            </article>
          </div>
        </section>

        <section className="privacy-band" aria-labelledby="privacy-title">
          <div>
            <p className="section-kicker">Private by default</p>
            <h2 id="privacy-title">The tools stay behind your identity.</h2>
          </div>
          <p>
            The public page explains the workbench. Files, conversion controls, and results appear
            only after sign-in, and API requests require a valid Mystira-issued access token.
          </p>
        </section>
      </main>

      <footer className="marketing-footer">
        <span>XtOX by Celladore</span>
        <span>Formats change. Meaning stays.</span>
      </footer>
    </div>
  );
}
