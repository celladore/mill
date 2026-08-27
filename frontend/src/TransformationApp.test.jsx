import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import TransformationApp from './TransformationApp';

const apiMocks = vi.hoisted(() => ({
  getTransformationHistory: vi.fn(() =>
    Promise.resolve({
      data: [
        {
          id: 'nullable-format',
          kind: 'audio',
          filename: 'recording.wav',
          input_format: 'wav',
          output_format: null,
          success: true,
          timestamp: '2026-08-27T06:00:00Z',
          downloadable: false,
          retained: true,
        },
      ],
    })
  ),
  transcribeAudio: vi.fn(() =>
    Promise.resolve({
      data: {
        id: 'transcript-1',
        filename: 'voice.ogg',
        success: true,
        text: 'Session private text',
        language: 'en',
        timestamp: '2026-08-27T07:00:00Z',
      },
    })
  ),
  convertText: vi.fn(() =>
    Promise.resolve({
      data: {
        id: 'text-1',
        filename: 'notes',
        original_format: 'md',
        target_format: 'docx',
        success: true,
        timestamp: '2026-08-27T07:05:00Z',
      },
    })
  ),
  downloadText: vi.fn(),
}));

vi.mock('./utils/apiClient', () => ({ conversionAPI: apiMocks }));
vi.mock('./auth/mystiraOidcConfig', () => ({ isMystiraOidcConfigured: () => true }));
vi.mock('./components/AuthStatus', () => ({
  AuthStatus: ({ onAuthChange, onAuthReady }) => (
    <button
      type="button"
      onClick={() => {
        onAuthReady();
        onAuthChange(true);
      }}
    >
      Authenticate
    </button>
  ),
}));
vi.mock('./components/MarketingPage', () => ({ MarketingPage: ({ authControl }) => authControl }));
vi.mock('./components/ProgressBar', () => ({ ProgressBar: () => null }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.requestAnimationFrame = callback => callback();

let container;
let root;

function button(label) {
  return [...container.querySelectorAll('button')].find(item => item.textContent.includes(label));
}

afterEach(() => {
  act(() => root?.unmount());
  container?.remove();
  apiMocks.getTransformationHistory.mockClear();
  apiMocks.transcribeAudio.mockClear();
  apiMocks.convertText.mockClear();
});

describe('transformation workbench', () => {
  it('exposes every transformation and keeps ephemeral transcripts in session history', async () => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());

    const tabs = [...container.querySelectorAll('[role="tab"]')];
    expect(tabs.map(tab => tab.textContent)).toEqual(
      expect.arrayContaining([
        expect.stringContaining('Document'),
        expect.stringContaining('Image'),
        expect.stringContaining('Text'),
        expect.stringContaining('Audio'),
        expect.stringContaining('Transcript'),
      ])
    );

    await act(async () =>
      tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
    );
    expect(document.activeElement).toBe(tabs[1]);
    expect(container.textContent).toContain('WAV→FILE');

    await act(async () => button('Transcript').click());
    const input = container.querySelector('#transcript-input');
    Object.defineProperty(input, 'files', { value: [new File(['voice'], 'voice.ogg')] });
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
    await act(async () => button('Run transcript path').click());

    expect(container.textContent).toContain('Session private text');
    expect(container.textContent).toContain('This session');
    expect(apiMocks.transcribeAudio).toHaveBeenCalledWith(expect.any(File), null, false);
    expect(apiMocks.getTransformationHistory).toHaveBeenCalledTimes(1);
  });

  it('exposes the deterministic text capability matrix and selected output', async () => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => button('Text').click());

    expect(container.textContent).toContain('MD · HTML · TXT · DOCX');
    expect(container.textContent).toContain('No generative model is used');
    const select = container.querySelector('.text-format-panel select');
    await act(async () => {
      select.value = 'docx';
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    const input = container.querySelector('#text-input');
    Object.defineProperty(input, 'files', { value: [new File(['# Notes'], 'notes.md')] });
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
    await act(async () => button('Run text path').click());

    expect(apiMocks.convertText).toHaveBeenCalledWith(expect.any(File), 'docx');
    expect(container.textContent).toContain('Transformation complete');
  });
});
