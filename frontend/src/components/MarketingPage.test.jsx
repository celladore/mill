import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { MarketingPage } from './MarketingPage';

describe('MarketingPage', () => {
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
    expect(markup).toContain('AI &amp; LLM-Ready Ingestion');
    expect(markup).toContain('Precision LaTeX Typesetting');

    // Default preview tab is Markdown to PDF
    expect(markup).toContain('Markdown → PDF');
    expect(markup).toContain('.MD');
    expect(markup).toContain('Quarterly Research Brief');

    // Format support ticker
    expect(markup).toContain('SUPPORTED FORMATS');
    expect(markup).toContain('AI-Ready Text');
  });

  it('renders trust metrics, developer code snippets, route inspector, and FAQ accordion', () => {
    const markup = renderToStaticMarkup(
      <MarketingPage authControl={<button>Sign in</button>} oidcConfigured={true} />
    );

    // Trust metrics band
    expect(markup).toContain('Median Rendering Latency');
    expect(markup).toContain('Persistent Disk Retention');
    expect(markup).toContain('Mystira Authenticated Sessions');

    // Developer section & code tabs
    expect(markup).toContain('API-First Architecture');
    expect(markup).toContain('Python SDK');
    expect(markup).toContain('TypeScript / Node');
    expect(markup).toContain('api.xtox.celladoresystems.com');

    // Interactive Route Matrix
    expect(markup).toContain('Interactive Route Inspector');
    expect(markup).toContain('FROM SOURCE:');
    expect(markup).toContain('Typography &amp; Layout Engine');

    // FAQ Accordion
    expect(markup).toContain('Frequently Asked Questions');
    expect(markup).toContain('What input and output formats does XtOX support?');
    expect(markup).toContain('What are the maximum file upload limits?');
    expect(markup).toContain('zero data retention');

    // Blueprint theme switcher
    expect(markup).toContain('🌙 Blueprint');
  });
});
