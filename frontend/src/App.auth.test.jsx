import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';

const apiMocks = vi.hoisted(() => ({
  convertLaTeX: vi.fn(),
}));

vi.mock('./utils/apiClient', () => ({
  conversionAPI: apiMocks,
}));

vi.mock('./auth/mystiraOidcConfig', () => ({
  isMystiraOidcConfigured: () => true,
}));

vi.mock('./components/AuthStatus', () => ({
  AuthStatus: ({ onAuthChange, onAuthReady }) => (
    <div>
      <button
        type="button"
        onClick={() => {
          onAuthReady();
          onAuthChange(true);
        }}
      >
        Authenticate
      </button>
      <button type="button" onClick={() => onAuthChange(false)}>
        Log out
      </button>
    </div>
  ),
}));

vi.mock('./components/AccessibleFileUpload', () => ({
  AccessibleFileUpload: ({ accept, onFileSelect }) => (
    <button
      type="button"
      onClick={() =>
        onFileSelect(
          new File(['\\documentclass{article}'], accept === '.tex' ? 'document.tex' : 'voice.ogg')
        )
      }
    >
      Choose {accept === '.tex' ? 'document' : 'audio'}
    </button>
  ),
}));

vi.mock('./components/AccessibleAlert', () => ({
  AccessibleAlert: ({ title }) => <div>{title}</div>,
}));

vi.mock('./components/ProgressBar', () => ({
  ProgressBar: () => null,
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;

function button(label) {
  return [...container.querySelectorAll('button')].find(item => item.textContent.trim() === label);
}

afterEach(() => {
  act(() => root?.unmount());
  container?.remove();
  apiMocks.convertLaTeX.mockReset();
});

describe('authenticated workspace lifecycle', () => {
  it('clears private state and ignores a conversion that completes after logout', async () => {
    let finishConversion;
    apiMocks.convertLaTeX.mockImplementation(
      () => new Promise(resolve => (finishConversion = resolve))
    );

    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<App />));
    await act(async () => button('Authenticate').click());
    await act(async () => button('Choose document').click());
    await act(async () => button('Convert to PDF').click());

    await act(async () => button('Log out').click());
    await act(async () => button('Authenticate').click());

    await act(async () => {
      finishConversion({ data: { success: true, id: 'stale', filename: 'private' } });
      await Promise.resolve();
    });

    expect(container.textContent).not.toContain('Conversion Successful!');
    expect(button('Convert to PDF').disabled).toBe(true);
  });
});
