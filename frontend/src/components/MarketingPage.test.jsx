import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketingPage } from './MarketingPage';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe('MarketingPage', () => {
  let container;
  let root;
  let originalClipboardDescriptor;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    originalClipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    container = null;

    if (originalClipboardDescriptor) {
      Object.defineProperty(navigator, 'clipboard', originalClipboardDescriptor);
    } else {
      delete navigator.clipboard;
    }
  });

  it('keeps workspace tools off the public marketing surface', () => {
    const markup = renderToStaticMarkup(
      <MarketingPage authControl={<button>Sign in with Mystira</button>} oidcConfigured={true} />
    );

    expect(markup).toContain('Sign in with Mystira');
    expect(markup).toContain('Private by default');
    expect(markup).not.toContain('Upload LaTeX File');
    expect(markup).not.toContain('Convert Audio');
  });

  it('announces session restoration while authentication initializes', () => {
    const markup = renderToStaticMarkup(
      <MarketingPage
        authControl={<button disabled>Checking session</button>}
        checkingSession
        oidcConfigured={true}
      />
    );

    expect(markup).toContain('Checking your Mystira session');
  });

  it('starts Mystira sign-in directly from the header workspace action', async () => {
    const onOpenWorkspace = vi.fn();
    await act(async () => {
      root.render(
        <MarketingPage
          authControl={<button>Sign in</button>}
          oidcConfigured={true}
          onOpenWorkspace={onOpenWorkspace}
        />
      );
    });

    const openWorkspace = Array.from(container.querySelectorAll('button')).find(
      item => item.textContent === 'Open workspace'
    );
    await act(async () => openWorkspace.click());

    expect(onOpenWorkspace).toHaveBeenCalledTimes(1);
  });

  it('does not promise workspace access when Mystira sign-in is unconfigured', () => {
    const markup = renderToStaticMarkup(
      <MarketingPage
        authControl={<span>Authentication is not configured.</span>}
        oidcConfigured={false}
      />
    );

    expect(markup).toContain('workspace remains unavailable');
    expect(markup).not.toContain('workspace opens after Mystira Identity verifies');
  });

  it('highlights multi-format document and media capabilities without making LaTeX the flagship', () => {
    const markup = renderToStaticMarkup(
      <MarketingPage authControl={<button>Sign in</button>} oidcConfigured={true} />
    );

    // Flagship emphasis is on universal format & media transformation
    expect(markup).toContain('Universal Format &amp; Media Transformation');
    expect(markup).toContain('Universal Document Publishing');
    expect(markup).toContain('High-Fidelity Audio Reshaping');
    expect(markup).toContain('Ephemeral Voice Transcription');
    expect(markup).toContain('Deterministic Text Reshaping');
    expect(markup).toContain('Precision LaTeX Typesetting');

    // Default preview tab is Markdown to PDF
    expect(markup).toContain('Markdown → PDF');
    expect(markup).toContain('.MD');
    expect(markup).toContain('Quarterly Research Brief');

    // Format support ticker
    expect(markup).toContain('Supported formats');
    expect(markup).toContain('[Document / Text]');
    expect(markup).toContain('[Image]');
    expect(markup).toContain('[Audio / Speech]');
    expect(markup).toContain('Plain text');
    expect(markup).toContain('SVG');
    expect(markup).toContain('[Video]');
    expect(markup).toContain('[New]');
    expect(markup).toContain('MP4');
    expect(markup).toContain('WebM');
    expect(markup).toContain('MOV');
    expect(markup).not.toContain('Mystira Story YAML');
    expect(markup).not.toContain('GLB · GLTF · OBJ');
    expect(markup).not.toContain('Docs → AI Context');
    expect(markup).not.toContain('RAG-optimized chunking');
  });

  it('renders trust metrics, developer code snippets, route inspector, and FAQ accordion', () => {
    const markup = renderToStaticMarkup(
      <MarketingPage authControl={<button>Sign in</button>} oidcConfigured={true} />
    );

    // Trust metrics band
    expect(markup).toContain('Frontend &amp; API');
    expect(markup).toContain('Ephemeral Transcription');
    expect(markup).toContain('Current Release Track');

    // Developer section & code tabs
    expect(markup).toContain('API-First Architecture');
    expect(markup).toContain('Python package');
    expect(markup).toContain('TypeScript / REST');
    expect(markup).toContain('npx @celladore/mill --help');
    expect(markup).toContain('npx mill');
    expect(markup).toContain('api.mill.celladoresystems.com');

    // Interactive Route Matrix
    expect(markup).toContain('Interactive Route Inspector');
    expect(markup).toContain('FROM SOURCE:');
    expect(markup).toContain('Typography &amp; Layout Engine');

    // FAQ Accordion
    expect(markup).toContain('Frequently Asked Questions');
    expect(markup).toContain('What input and output formats does Mill support?');
    expect(markup).toContain('What are the maximum file upload limits?');
    expect(markup).toContain(
      'How is privacy and data retention handled for audio and transcripts?'
    );

    // Blueprint theme switcher
    expect(markup).toContain('🌙 Blueprint');
  });

  it('handles client interactions: tab switching, route matrix, theme toggle, FAQ accordion, audio playback, and copy feedback', async () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

    await act(async () => {
      root.render(<MarketingPage authControl={<button>Sign In</button>} oidcConfigured={true} />);
    });

    const pageElement = container.querySelector('.marketing-page');
    expect(pageElement.classList.contains('theme-paper')).toBe(true);

    // 1. Theme toggle button
    const themeBtn = container.querySelector('.theme-toggle-btn');
    expect(themeBtn.textContent).toContain('🌙 Blueprint');

    await act(async () => {
      themeBtn.click();
    });

    expect(pageElement.classList.contains('theme-blueprint')).toBe(true);
    expect(themeBtn.textContent).toContain('☀️ Paper');

    // 2. Workbench preview tabs switching
    const audioTab = container.querySelector('#tab-audio');
    const audioPanel = container.querySelector('#panel-audio');
    const markdownPanel = container.querySelector('#panel-markdown');

    expect(markdownPanel.hidden).toBe(false);
    expect(audioPanel.hidden).toBe(true);

    await act(async () => {
      audioTab.click();
    });

    expect(markdownPanel.hidden).toBe(true);
    expect(audioPanel.hidden).toBe(false);

    // 3. Audio simulation playback button
    const playBtn = container.querySelector('.audio-sample-play-btn');
    expect(playBtn.textContent).toContain('▶ Play audio snippet');
    expect(playBtn.getAttribute('aria-pressed')).toBe('false');
    expect(playBtn.getAttribute('aria-label')).toBe('Play audio snippet');

    await act(async () => {
      playBtn.click();
    });

    expect(playBtn.textContent).toContain('⏸ Playing sample…');
    expect(playBtn.getAttribute('aria-pressed')).toBe('true');
    expect(playBtn.getAttribute('aria-label')).toBe('Pause audio snippet');

    // 4. Interactive Route Selector changes
    const latexRouteBtn = Array.from(container.querySelectorAll('.route-btn')).find(btn =>
      btn.textContent.includes('LaTeX Source (.tex)')
    );

    await act(async () => {
      latexRouteBtn.click();
    });

    expect(container.querySelector('.route-engine-name').textContent).toContain(
      'TeX Live Compiler + Syntax Auto-Fix'
    );
    expect(container.querySelector('.route-metric-pill').textContent).toContain('Execution:');

    const videoRouteBtn = Array.from(container.querySelectorAll('.route-btn')).find(btn =>
      btn.textContent.includes('Video (.mp4/.mov/.mkv/.webm/...)')
    );

    await act(async () => {
      videoRouteBtn.click();
    });

    expect(container.querySelector('.route-metric-pill').textContent).toContain(
      'Processing bound: ≤ 5 min bound'
    );

    // 5. Code tabs selection and copy-to-clipboard feedback
    const pythonTab = container.querySelector('#code-tab-python');
    const curlPanel = container.querySelector('#code-panel-curl');
    const pythonPanel = container.querySelector('#code-panel-python');

    expect(curlPanel.hidden).toBe(false);
    expect(pythonPanel.hidden).toBe(true);

    await act(async () => {
      pythonTab.click();
    });

    expect(curlPanel.hidden).toBe(true);
    expect(pythonPanel.hidden).toBe(false);

    const copyBtn = container.querySelector('.copy-code-btn');
    expect(copyBtn.textContent).toContain('Copy snippet');

    await act(async () => {
      copyBtn.click();
    });

    expect(navigator.clipboard.writeText).toHaveBeenCalled();
    expect(copyBtn.textContent).toContain('✓ Copied');

    // 6. FAQ accordion expand & collapse
    const firstFaqBtn = container.querySelector('.faq-question-btn');
    expect(container.querySelector('#faq-answer-0')).toBeNull();

    await act(async () => {
      firstFaqBtn.click();
    });

    const faqAnswer = container.querySelector('#faq-answer-0');
    expect(faqAnswer).not.toBeNull();
    expect(faqAnswer.textContent).toContain(
      'Markdown, HTML, plain text, DOCX, and LaTeX document routes',
    );

    await act(async () => {
      firstFaqBtn.click();
    });

    expect(container.querySelector('#faq-answer-0')).toBeNull();
  });
});
