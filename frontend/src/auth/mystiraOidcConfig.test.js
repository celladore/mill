/* global afterAll, beforeEach, describe, expect, it, jest */

describe('Mystira OIDC configuration', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    delete process.env.REACT_APP_MYSTIRA_OIDC_ISSUER;
    delete process.env.REACT_APP_MYSTIRA_OIDC_CLIENT_ID;
    delete process.env.REACT_APP_MYSTIRA_OIDC_REDIRECT_URI;
    delete process.env.REACT_APP_MYSTIRA_OIDC_POST_LOGOUT_REDIRECT_URI;
    delete process.env.REACT_APP_MYSTIRA_OIDC_SCOPES;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('stays disabled until both issuer and client id are configured', () => {
    process.env.REACT_APP_MYSTIRA_OIDC_ISSUER = 'https://identity.mystira.app/';

    const { isMystiraOidcConfigured } = require('./mystiraOidcConfig');

    expect(isMystiraOidcConfigured()).toBe(false);
  });

  it('builds the Public + PKCE client settings for celladore-xtox', () => {
    process.env.REACT_APP_MYSTIRA_OIDC_ISSUER = 'https://identity.mystira.app/';
    process.env.REACT_APP_MYSTIRA_OIDC_CLIENT_ID = 'celladore-xtox';

    const { getMystiraOidcSettings, isMystiraOidcConfigured } = require('./mystiraOidcConfig');
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
