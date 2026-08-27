import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AuthStatus } from './AuthStatus';

const oidcMocks = vi.hoisted(() => ({
  activeUser: { expired: false },
  initializeMystiraOidc: vi.fn(() => Promise.resolve()),
  listener: null,
  subscribeToMystiraUser: vi.fn(listener => {
    oidcMocks.listener = listener;
    listener(oidcMocks.activeUser);
    return vi.fn();
  }),
  loginWithMystira: vi.fn(),
  logoutFromMystira: vi.fn(),
}));

vi.mock('../auth/mystiraOidcConfig', () => ({ isMystiraOidcConfigured: () => true }));
vi.mock('../auth/mystiraOidcInstance', () => ({
  getActiveMystiraUser: () => oidcMocks.activeUser,
  initializeMystiraOidc: oidcMocks.initializeMystiraOidc,
  loginWithMystira: oidcMocks.loginWithMystira,
  logoutFromMystira: oidcMocks.logoutFromMystira,
  subscribeToMystiraUser: oidcMocks.subscribeToMystiraUser,
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;

afterEach(() => {
  act(() => root?.unmount());
  container?.remove();
  oidcMocks.initializeMystiraOidc.mockClear();
  oidcMocks.subscribeToMystiraUser.mockClear();
  oidcMocks.listener = null;
  oidcMocks.activeUser = { expired: false };
});

describe('AuthStatus lifecycle', () => {
  it('does not reinitialize OIDC when parent callback identities change', async () => {
    const firstChange = vi.fn();
    const firstReady = vi.fn();
    const latestChange = vi.fn();
    const latestReady = vi.fn();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () =>
      root.render(<AuthStatus onAuthChange={firstChange} onAuthReady={firstReady} />)
    );
    await act(async () =>
      root.render(<AuthStatus onAuthChange={latestChange} onAuthReady={latestReady} />)
    );

    expect(oidcMocks.initializeMystiraOidc).toHaveBeenCalledTimes(1);
    expect(oidcMocks.subscribeToMystiraUser).toHaveBeenCalledTimes(1);

    await act(async () => oidcMocks.listener(null));
    expect(latestChange).toHaveBeenCalledWith(false);
    expect(firstChange).not.toHaveBeenCalledWith(false);
  });
});
