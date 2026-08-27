import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import TransformationApp, { safeBlobUrl } from './TransformationApp';

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
  convertImage: vi.fn(() =>
    Promise.resolve({
      data: {
        id: 'image-1',
        filename: 'source',
        success: true,
        target_format: 'webp',
      },
    })
  ),
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
Object.defineProperty(window.URL, 'createObjectURL', {
  configurable: true,
  value: vi.fn(() => `blob:${window.location.origin}/image-preview`),
});
Object.defineProperty(window.URL, 'revokeObjectURL', {
  configurable: true,
  value: vi.fn(),
});

let container;
let root;

function button(label) {
  return [...container.querySelectorAll('button')].find(item => item.textContent.includes(label));
}

function setInputValue(input, value) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

afterEach(() => {
  act(() => root?.unmount());
  container?.remove();
  apiMocks.getTransformationHistory.mockClear();
  apiMocks.transcribeAudio.mockClear();
  apiMocks.convertText.mockClear();
  apiMocks.convertImage.mockClear();
});

describe('transformation workbench', () => {
  it('preserves a valid IPv6-origin blob URL and rejects a different origin', () => {
    const ipv6BlobUrl = 'blob:http://[::1]:5173/8d9a545e-0000-4000-8000-aba792740000';

    expect(safeBlobUrl(ipv6BlobUrl, 'http://[::1]:5173')).toBe(ipv6BlobUrl);
    expect(safeBlobUrl(ipv6BlobUrl, 'http://localhost:5173')).toBe('');
  });

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
    expect(container.textContent).toContain('05 live / 02 next');
    expect(container.textContent).toContain('STORY YAML → IMAGE / VIDEO');
    expect(container.textContent).toContain('IMAGE → 3D MODEL');
    expect(container.querySelectorAll('.upcoming-route')).toHaveLength(2);
    expect(container.querySelectorAll('.status-coming-soon')).toHaveLength(2);

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

  it('previews a selected image and submits privacy-safe image defaults', async () => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => button('Image').click());

    const input = container.querySelector('#image-input');
    const file = new File([new Uint8Array(2048)], 'a-very-long-source-filename.png', {
      type: 'image/png',
    });
    Object.defineProperty(input, 'files', { value: [file] });
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));

    expect(container.querySelector('.image-source-preview img').src).toBe(
      `blob:${window.location.origin}/image-preview`
    );
    expect(container.textContent).toContain('2.0 KB');
    expect(container.textContent).toContain('Advanced image settings');

    const quality = [...container.querySelectorAll('.route-settings select')].find(select =>
      select.parentElement.textContent.includes('Quality')
    );
    await act(async () => {
      quality.value = 'custom';
      quality.dispatchEvent(new Event('change', { bubbles: true }));
    });
    const range = container.querySelector('input[type="range"]');
    const [maxWidth, maxHeight] = container.querySelectorAll('input[type="number"]');
    await act(async () => {
      setInputValue(range, '72');
      setInputValue(maxWidth, '1200');
      setInputValue(maxHeight, '800');
    });

    await act(async () => button('Run image path').click());
    expect(apiMocks.convertImage).toHaveBeenCalledWith(file, 'webp', 72, {
      maxWidth: 1200,
      maxHeight: 800,
      stripMetadata: true,
    });
  });

  it('rejects an invalid image dimension instead of silently omitting it', async () => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => button('Image').click());

    const input = container.querySelector('#image-input');
    Object.defineProperty(input, 'files', {
      value: [new File(['pixels'], 'source.png', { type: 'image/png' })],
    });
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));

    const [maxWidth] = container.querySelectorAll('input[type="number"]');
    await act(async () => setInputValue(maxWidth, '0'));
    await act(async () => button('Run image path').click());

    expect(apiMocks.convertImage).not.toHaveBeenCalled();
    expect(container.textContent).toContain(
      'Maximum dimensions must be whole numbers from 1 to 16384.'
    );
  });
});
