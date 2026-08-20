import { UserManager } from 'oidc-client-ts';
import { getMystiraOidcSettings, isMystiraOidcConfigured } from './mystiraOidcConfig';

let userManager = null;
let activeUser = null;
let initializationPromise = null;
const listeners = new Set();

function syncActiveUser(user) {
  activeUser = user && !user.expired ? user : null;
  listeners.forEach(listener => listener(activeUser));
}

export function subscribeToMystiraUser(listener) {
  listeners.add(listener);
  listener(activeUser);
  return () => listeners.delete(listener);
}

export function initializeMystiraOidc() {
  if (!isMystiraOidcConfigured()) return Promise.resolve();
  if (initializationPromise) return initializationPromise;

  initializationPromise = (async () => {
    userManager = new UserManager(getMystiraOidcSettings());
    userManager.events.addUserLoaded(syncActiveUser);
    userManager.events.addUserUnloaded(() => syncActiveUser(null));

    const params = new URLSearchParams(window.location.search);
    if (params.has('code') && params.has('state')) {
      try {
        await userManager.signinRedirectCallback();
      } finally {
        window.history.replaceState({}, document.title, '/');
      }
    }

    syncActiveUser(await userManager.getUser());
  })();

  return initializationPromise;
}

export function getActiveMystiraUser() {
  return activeUser;
}

export async function getMystiraAccessToken() {
  if (!userManager) return '';

  const storedUser = await userManager.getUser();
  if (storedUser && !storedUser.expired) {
    syncActiveUser(storedUser);
    return storedUser.access_token;
  }

  try {
    const renewedUser = await userManager.signinSilent();
    syncActiveUser(renewedUser);
    return renewedUser?.access_token || '';
  } catch {
    syncActiveUser(null);
    return '';
  }
}

export async function loginWithMystira() {
  if (!userManager) return;
  await userManager.signinRedirect();
}

export async function logoutFromMystira() {
  if (!userManager) return;
  await userManager.signoutRedirect();
  syncActiveUser(null);
}

export async function clearMystiraUser() {
  if (userManager) await userManager.removeUser();
  syncActiveUser(null);
}
