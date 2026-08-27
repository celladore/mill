import { useEffect, useRef, useState } from 'react';
import {
  getActiveMystiraUser,
  initializeMystiraOidc,
  loginWithMystira,
  logoutFromMystira,
  subscribeToMystiraUser,
} from '../auth/mystiraOidcInstance';
import { isMystiraOidcConfigured } from '../auth/mystiraOidcConfig';

export function AuthStatus({ onAuthChange, onAuthReady, variant = 'workspace' }) {
  const configured = isMystiraOidcConfigured();
  const [user, setUser] = useState(() => getActiveMystiraUser());
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);
  const onAuthChangeRef = useRef(onAuthChange);
  const onAuthReadyRef = useRef(onAuthReady);
  onAuthChangeRef.current = onAuthChange;
  onAuthReadyRef.current = onAuthReady;

  useEffect(() => {
    let initializationComplete = false;
    const unsubscribe = subscribeToMystiraUser(nextUser => {
      setUser(nextUser);
      if (initializationComplete) {
        onAuthChangeRef.current(Boolean(nextUser));
      }
    });

    initializeMystiraOidc()
      .then(() => {
        initializationComplete = true;
        const activeUser = getActiveMystiraUser();
        setUser(activeUser);
        setReady(true);
        onAuthChangeRef.current(Boolean(activeUser));
        onAuthReadyRef.current?.();
      })
      .catch(initializationError => {
        initializationComplete = true;
        console.error('[MystiraOidc] Initialization failed:', initializationError);
        setError('Sign-in could not be completed. Please try again.');
        setReady(true);
        onAuthChangeRef.current(false);
        onAuthReadyRef.current?.();
      });

    return unsubscribe;
  }, [configured]);

  const landing = variant === 'landing';

  if (configured && !ready) {
    return (
      <button
        type="button"
        className={
          landing ? 'marketing-login-button' : 'mt-4 rounded-lg bg-gray-300 px-4 py-2 text-gray-600'
        }
        disabled
      >
        Checking session…
      </button>
    );
  }

  if (!configured) {
    return (
      <p
        className={landing ? 'auth-message auth-message-warning' : 'mt-4 text-sm text-amber-800'}
        role="status"
      >
        Sign-in is not configured for this deployment. Conversion requests remain disabled.
      </p>
    );
  }

  if (error) {
    return (
      <div className={landing ? 'auth-error' : 'mt-4'} role="alert">
        <p className={landing ? 'auth-message auth-message-error' : 'text-sm text-red-700'}>
          {error}
        </p>
        <button
          type="button"
          onClick={() => loginWithMystira()}
          className={
            landing
              ? 'marketing-login-button'
              : 'mt-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
          }
        >
          Try sign-in again
        </button>
      </div>
    );
  }

  if (!user) {
    return (
      <button
        type="button"
        onClick={() => loginWithMystira()}
        className={
          landing
            ? 'marketing-login-button'
            : 'mt-4 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
        }
      >
        Sign in with Mystira
      </button>
    );
  }

  return (
    <div className="mt-4 flex flex-col items-center gap-2 sm:flex-row sm:justify-center">
      <span className="text-sm text-gray-700" role="status">
        Signed in
      </span>
      <button
        type="button"
        onClick={() => logoutFromMystira()}
        className="rounded-lg border border-gray-400 px-3 py-1 text-sm text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
      >
        Sign out
      </button>
    </div>
  );
}
