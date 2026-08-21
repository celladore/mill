import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { MarketingPage } from './MarketingPage';

describe('MarketingPage', () => {
  it('keeps workspace tools off the public marketing surface', () => {
    const markup = renderToStaticMarkup(
      <MarketingPage authControl={<button>Sign in with Mystira</button>} />
    );

    expect(markup).toContain('Sign in with Mystira');
    expect(markup).toContain('Private by default');
    expect(markup).not.toContain('Upload LaTeX File');
    expect(markup).not.toContain('Convert Audio');
  });

  it('announces session restoration while authentication initializes', () => {
    const markup = renderToStaticMarkup(
      <MarketingPage authControl={<button disabled>Checking session</button>} checkingSession />
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
});
