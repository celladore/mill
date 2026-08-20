const issuer = process.env.REACT_APP_MYSTIRA_OIDC_ISSUER || '';
const clientId = process.env.REACT_APP_MYSTIRA_OIDC_CLIENT_ID || '';

function configuredScopes() {
  return (
    process.env.REACT_APP_MYSTIRA_OIDC_SCOPES || 'openid profile email offline_access'
  ).trim();
}

export function isMystiraOidcConfigured() {
  return Boolean(issuer && clientId);
}

export function getMystiraOidcSettings() {
  const origin = window.location.origin;

  return {
    authority: issuer,
    client_id: clientId,
    redirect_uri: process.env.REACT_APP_MYSTIRA_OIDC_REDIRECT_URI || origin,
    post_logout_redirect_uri: process.env.REACT_APP_MYSTIRA_OIDC_POST_LOGOUT_REDIRECT_URI || origin,
    response_type: 'code',
    scope: configuredScopes(),
    loadUserInfo: false,
    automaticSilentRenew: true,
  };
}
