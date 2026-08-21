const env = import.meta.env;

function configuredScopes() {
  return (env.VITE_MYSTIRA_OIDC_SCOPES || 'openid profile email offline_access').trim();
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
    response_type: 'code',
    scope: configuredScopes(),
    loadUserInfo: false,
    automaticSilentRenew: true,
  };
}
