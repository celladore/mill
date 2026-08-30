import { beforeEach, describe, expect, it, vi } from 'vitest';

const oidc = vi.hoisted(() => ({
  configured: true,
  instances: [],
}));

vi.mock('./mystiraOidcConfig', () => ({
  getMystiraOidcSettings: () => ({ authority: 'https://identity.mystira.app/' }),
  isMystiraOidcConfigured: () => oidc.configured,
}));

vi.mock('oidc-client-ts', () => ({
  UserManager: class UserManager {
    constructor() {
      this.events = {
        addUserLoaded: vi.fn(listener => {
          this.onUserLoaded = listener;
        }),
        addUserUnloaded: vi.fn(listener => {
          this.onUserUnloaded = listener;
        }),
      };
      this.getUser = vi.fn().mockResolvedValue(null);
      this.signinRedirectCallback = vi.fn().mockResolvedValue(null);
      this.signinSilent = vi.fn().mockResolvedValue(null);
      this.signinRedirect = vi.fn().mockResolvedValue(null);
      this.signoutRedirect = vi.fn().mockResolvedValue(null);
      this.removeUser = vi.fn().mockResolvedValue(null);
      oidc.instances.push(this);
    }
  },
}));

async function loadInstance() {
  vi.resetModules();
  return import('./mystiraOidcInstance');
}

describe('Mystira OIDC lifecycle', () => {
  beforeEach(() => {
    oidc.configured = true;
    oidc.instances.length = 0;
    window.history.replaceState({}, '', '/');
  });

  it('fails closed without identity configuration', async () => {
    oidc.configured = false;
    const auth = await loadInstance();

    await auth.initializeMystiraOidc();

    expect(oidc.instances).toHaveLength(0);
    await expect(auth.getMystiraAccessToken()).resolves.toBe('');
    await expect(auth.loginWithMystira()).resolves.toBeUndefined();
    await expect(auth.logoutFromMystira()).resolves.toBeUndefined();
  });

  it('handles the authorization callback and restores a valid session', async () => {
    window.history.replaceState({}, '', '/?code=code-value&state=state-value');
    const replaceState = vi.spyOn(window.history, 'replaceState');
    const auth = await loadInstance();
    const user = { expired: false, access_token: 'access-token' };

    const initialization = auth.initializeMystiraOidc();
    const manager = oidc.instances[0];
    manager.getUser.mockResolvedValue(user);
    await initialization;

    expect(manager.signinRedirectCallback).toHaveBeenCalledOnce();
    expect(replaceState).toHaveBeenCalledWith({}, document.title, '/');
    expect(auth.getActiveMystiraUser()).toBe(user);
    await expect(auth.getMystiraAccessToken()).resolves.toBe('access-token');
  });

  it('starts redirect login and logout through the configured manager', async () => {
    const auth = await loadInstance();
    await auth.initializeMystiraOidc();
    const manager = oidc.instances[0];

    await auth.loginWithMystira();
    await auth.logoutFromMystira();

    expect(manager.signinRedirect).toHaveBeenCalledOnce();
    expect(manager.signoutRedirect).toHaveBeenCalledOnce();
    expect(auth.getActiveMystiraUser()).toBeNull();
  });
});
