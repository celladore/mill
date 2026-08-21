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
      scope: 'openid profile email offline_access',
      loadUserInfo: false,
      automaticSilentRenew: true,
    });
  });
});
