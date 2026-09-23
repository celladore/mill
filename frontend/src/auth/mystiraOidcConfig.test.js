import { afterEach, describe, expect, it, vi } from 'vitest';

async function loadConfig() {
  vi.resetModules();
  return import('./mystiraOidcConfig');
}

describe('Mystira OIDC configuration', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('stays disabled until both issuer and client id are configured', async () => {
    vi.stubEnv('VITE_MYSTIRA_OIDC_ISSUER', 'https://identity.mystira.app/');
    vi.stubEnv('VITE_MYSTIRA_OIDC_CLIENT_ID', '');

    const { isMystiraOidcConfigured } = await loadConfig();

    expect(isMystiraOidcConfigured()).toBe(false);
  });

  it('builds the Public + PKCE client settings for celladore-xtox', async () => {
    vi.stubEnv('VITE_MYSTIRA_OIDC_ISSUER', 'https://identity.mystira.app/');
    vi.stubEnv('VITE_MYSTIRA_OIDC_CLIENT_ID', 'celladore-xtox');

    const { getMystiraOidcSettings, isMystiraOidcConfigured } = await loadConfig();
    const settings = getMystiraOidcSettings();

    expect(isMystiraOidcConfigured()).toBe(true);
    expect(settings).toMatchObject({
      authority: 'https://identity.mystira.app/',
      client_id: 'celladore-xtox',
      redirect_uri: window.location.origin,
      post_logout_redirect_uri: window.location.origin,
      response_type: 'code',
      disablePKCE: false,
      scope: 'openid profile email',
      loadUserInfo: false,
      automaticSilentRenew: true,
    });
  });

  it('never requests offline_access by default', async () => {
    vi.stubEnv('VITE_MYSTIRA_OIDC_ISSUER', 'https://identity.mystira.app/');
    vi.stubEnv('VITE_MYSTIRA_OIDC_CLIENT_ID', 'celladore-xtox');

    const { getMystiraOidcSettings } = await loadConfig();

    // A refresh token issued to a public client is a pure bearer in
    // browser-reachable storage — PKCE binds the code hop, not the refresh
    // exchange. Asserted as a substring so an unrelated scope being added
    // later does not silently disarm the check.
    expect(getMystiraOidcSettings().scope).not.toContain('offline_access');
  });

  it('still honours an explicit scope override', async () => {
    vi.stubEnv('VITE_MYSTIRA_OIDC_ISSUER', 'https://identity.mystira.app/');
    vi.stubEnv('VITE_MYSTIRA_OIDC_CLIENT_ID', 'celladore-xtox');
    vi.stubEnv('VITE_MYSTIRA_OIDC_SCOPES', 'openid custom.scope');

    const { getMystiraOidcSettings } = await loadConfig();

    // Positive control for the assertion above: without this, that test would
    // pass just as well if configuredScopes() stopped reading the environment
    // and returned a hardcoded constant.
    expect(getMystiraOidcSettings().scope).toBe('openid custom.scope');
  });
});
