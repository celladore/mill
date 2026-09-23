const env = import.meta.env;

function configuredScopes() {
  // Deliberately no `offline_access`. celladore-xtox is a public client, so a
  // refresh token issued to it is a pure bearer sitting in browser-reachable
  // storage: PKCE binds the authorization-code hop only, and the refresh
  // exchange carries no verifier to prove the holder is still this app.
  // Renewal goes through the prompt=none iframe below instead. If a future
  // deployment needs it back, change the Identity client first — re-adding it
  // here alone just produces an invalid_scope at authorize.
  return (env.VITE_MYSTIRA_OIDC_SCOPES || 'openid profile email').trim();
}

export function isMystiraOidcConfigured() {
  return Boolean(env.VITE_MYSTIRA_OIDC_ISSUER && env.VITE_MYSTIRA_OIDC_CLIENT_ID);
}

export function getMystiraOidcSettings() {
  const origin = window.location.origin;

  return {
    authority: env.VITE_MYSTIRA_OIDC_ISSUER || '',
    client_id: env.VITE_MYSTIRA_OIDC_CLIENT_ID || '',
    redirect_uri: env.VITE_MYSTIRA_OIDC_REDIRECT_URI || origin,
    post_logout_redirect_uri: env.VITE_MYSTIRA_OIDC_POST_LOGOUT_REDIRECT_URI || origin,
    // Without this, oidc-client-ts falls back to redirect_uri for the hidden
    // automaticSilentRenew iframe, i.e. it reloads the full SPA in that
    // iframe just to refresh a token. Point it at a minimal dedicated page
    // instead (see src/silentRenew.js).
    silent_redirect_uri: env.VITE_MYSTIRA_OIDC_SILENT_REDIRECT_URI || `${origin}/silent-renew.html`,
    response_type: 'code',
    disablePKCE: false,
    scope: configuredScopes(),
    loadUserInfo: false,
    automaticSilentRenew: true,
  };
}
