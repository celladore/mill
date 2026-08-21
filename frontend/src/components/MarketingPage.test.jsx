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
});
