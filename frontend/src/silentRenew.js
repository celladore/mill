import { UserManager } from 'oidc-client-ts';

import { getMystiraOidcSettings } from './auth/mystiraOidcConfig';

// Loaded only inside the hidden iframe oidc-client-ts opens for
// automaticSilentRenew. Keeping this a minimal, dedicated page (instead of
// letting silent_redirect_uri default to the full SPA) avoids re-running
// app bootstrap/analytics in that iframe and completes the renewal against
// this exact origin, which is what Mystira Identity's dmn_chk_ domain-check
// cookie expects.
new UserManager(getMystiraOidcSettings()).signinSilentCallback().catch(error => {
  console.error('[MystiraOidc] Silent renew callback failed:', error);
});
