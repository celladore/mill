import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import TransformationApp, { safeBlobUrl, sha256File, validateFiles } from './TransformationApp';

const apiMocks = vi.hoisted(() => ({
  getCapabilities: vi.fn(() =>
    Promise.resolve({
      data: {
        routes: {
          document: { extensions: ['.tex'], max_file_size: 10485760, batch_enabled: true },
          image: { extensions: ['.png', '.jpg'], max_file_size: 20971520, batch_enabled: true },
          text: { extensions: ['.md', '.html', '.txt', '.docx'], max_file_size: 10485760, batch_enabled: true },
          audio: { extensions: ['.ogg', '.mp3'], max_file_size: 52428800, batch_enabled: true },
          transcript: { extensions: ['.ogg', '.mp3'], max_file_size: 52428800, batch_enabled: false },
          video: { extensions: ['.mp4', '.mov'], max_file_size: 104857600, batch_enabled: true },
        },
        batch: { max_items: 10, max_aggregate_size: 209715200 },
      },
    })
  ),
  getBatches: vi.fn(() => Promise.resolve({ data: [] })),
  createBatch: vi.fn(),
  executeBatchItem: vi.fn(),
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
  downloadImage: vi.fn(() => Promise.resolve({ data: '<svg></svg>' })),
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
        input_file_size_kb: 2048,
        file_size_kb: 512,
        width: 1200,
        height: 800,
        quality: 'custom',
        quality_value: 72,
      },
    })
  ),
  convertVideo: vi.fn(() =>
    Promise.resolve({
      data: {
        id: 'video-1',
        filename: 'clip',
        success: true,
        target_format: 'mp4',
        input_file_size_kb: 4096,
        file_size_kb: 2048,
        duration: 12.4,
        width: 1280,
        height: 720,
        video_codec: 'h264',
        audio_codec: 'aac',
        quality: 'balanced',
      },
    })
  ),
  downloadVideo: vi.fn(),
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
vi.mock('./components/ProgressBar', () => ({
  ProgressBar: ({ label, detail, indeterminate }) => (
    <div data-testid="progress" data-indeterminate={String(Boolean(indeterminate))}>
      {label} {detail}
    </div>
  ),
}));

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
Object.defineProperty(globalThis.crypto, 'subtle', {
  configurable: true,
  value: {
    digest: vi.fn(async (_algorithm, data) => {
      const output = new Uint8Array(32);
      output[0] = new Uint8Array(data).reduce((sum, value) => (sum + value) % 256, 0);
      return output.buffer;
    }),
  },
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
  apiMocks.downloadImage.mockClear();
  apiMocks.convertVideo.mockClear();
  apiMocks.getCapabilities.mockClear();
  apiMocks.getBatches.mockClear();
  apiMocks.createBatch.mockReset();
  apiMocks.executeBatchItem.mockReset();
});

describe('transformation workbench', () => {
  it('validates route compatibility, duplicate names, and batch limits', () => {
    const capabilities = {
      routes: { text: { extensions: ['.md'], max_file_size: 5 } },
      batch: { max_items: 2, max_aggregate_size: 20 },
    };
    const entries = validateFiles(
      'text',
      [
        new File(['one'], 'same.md'),
        new File(['two'], 'same.md'),
        new File(['three'], 'notes.txt'),
      ],
      capabilities
    );

    expect(entries[0].error).toContain('Duplicate');
    expect(entries[1].error).toContain('Duplicate');
    expect(entries[2].error).toContain('Unsupported');

    const oversized = new File(['x'], 'large.md');
    Object.defineProperty(oversized, 'size', { value: 200 * 1024 * 1024 + 1 });
    expect(validateFiles('text', [oversized], null)[0].error).toContain('200.0 MB');
  });

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

    expect(container.querySelector('.transformation-rail.is-collapsed')).not.toBeNull();
    expect(container.textContent).toContain('Current path');
    expect(container.querySelector('.history-ledger')).not.toBeNull();
    await act(async () => button('Show paths').click());

    const tabs = [...container.querySelectorAll('[role="tab"]')];
    expect(tabs.map(tab => tab.textContent)).toEqual(
      expect.arrayContaining([
        expect.stringContaining('Document'),
        expect.stringContaining('Image'),
        expect.stringContaining('Text'),
        expect.stringContaining('Audio'),
        expect.stringContaining('Transcript'),
        expect.stringContaining('Video'),
      ])
    );
    expect(container.textContent).toContain('6 live · 3 coming soon');
    expect(container.textContent).toContain('WORDS → NEW WORDS');
    expect(container.textContent).toContain('STORY YAML → IMAGE / VIDEO');
    expect(container.textContent).toContain('IMAGE → 3D MODEL');
    expect(container.querySelectorAll('.upcoming-route')).toHaveLength(3);
    expect(container.querySelectorAll('.status-coming-soon')).toHaveLength(3);

    await act(async () => button('Hide history').click());
    expect(container.querySelector('.history-ledger')).toBeNull();
    await act(async () => button('Show history').click());

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
    expect(container.textContent).toContain('Download transcript');
    expect(apiMocks.transcribeAudio).toHaveBeenCalledWith(expect.any(File), null, false);
    expect(apiMocks.getTransformationHistory).toHaveBeenCalledTimes(1);

    const transcriptHistoryItem = [...container.querySelectorAll('.history-list li')].find(item =>
      item.textContent.includes('voice.ogg')
    );
    const transcriptDownload = [...transcriptHistoryItem.querySelectorAll('button')].find(item =>
      item.textContent.includes('Download transcript')
    );
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    await act(async () => transcriptDownload.click());
    const transcriptBlob = window.URL.createObjectURL.mock.calls.at(-1)[0];
    expect(transcriptBlob).toBeInstanceOf(Blob);
    expect(transcriptBlob.type).toBe('text/plain;charset=utf-8');
    expect(await transcriptBlob.text()).toBe('Session private text');
    expect(clickSpy).toHaveBeenCalledOnce();
    clickSpy.mockRestore();
  });

  it('runs deterministic video with bounded presets and exposes outcomes', async () => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => button('Show paths').click());
    await act(async () => button('Video').click());
    expect(container.textContent).toContain('Local FFmpeg path');

    const input = container.querySelector('#video-input');
    const file = new File(['video'], 'clip.mov', { type: 'video/quicktime' });
    Object.defineProperty(input, 'files', { value: [file] });
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
    await act(async () => button('Run video path').click());

    expect(apiMocks.convertVideo).toHaveBeenCalledWith(file, 'mp4', 'balanced', 1080);
    expect(container.textContent).toContain('4.0 MB → 2.0 MB');
    expect(container.textContent).toContain('50% smaller');
    expect(container.textContent).toContain('1280 × 720 · H264');
    expect(container.textContent).toContain('AAC audio');
  });

  it('uses honest indeterminate feedback while a video transcode is pending', async () => {
    let finishVideo;
    apiMocks.convertVideo.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          finishVideo = resolve;
        })
    );
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => button('Show paths').click());
    await act(async () => button('Video').click());
    const input = container.querySelector('#video-input');
    Object.defineProperty(input, 'files', {
      value: [new File(['video'], 'clip.mov', { type: 'video/quicktime' })],
    });
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
    await act(async () => button('Run video path').click());

    const progress = container.querySelector('[data-testid="progress"]');
    expect(progress.dataset.indeterminate).toBe('true');
    expect(progress.textContent).toContain('Transcoding video · 00:00');
    expect(progress.textContent).toContain('Large videos can take several minutes');
    expect(progress.textContent).not.toContain('88%');

    await act(async () =>
      finishVideo({
        data: {
          id: 'video-pending',
          filename: 'clip',
          success: true,
          target_format: 'mp4',
          quality: 'balanced',
        },
      })
    );
  });

  it('exposes the deterministic text capability matrix and selected output', async () => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => button('Show paths').click());
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
    await act(async () => button('Show paths').click());
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
      vectorColors: 8,
      vectorDetail: 60,
      pathSmoothing: 50,
      removeBackground: false,
      vectorMaxDimension: 1024,
    });
    expect(container.textContent).toContain('2.0 MB → 512.0 KB');
    expect(container.textContent).toContain('75% smaller');
    expect(container.textContent).toContain('1200 × 800 px');
    expect(container.textContent).toContain('Custom · 72%');
  });

  it('submits bounded SVG settings and previews the retained vector result', async () => {
    let resolvePreview;
    apiMocks.downloadImage.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          resolvePreview = resolve;
        })
    );
    apiMocks.convertImage.mockResolvedValueOnce({
      data: {
        id: 'svg-1',
        filename: 'logo',
        success: true,
        target_format: 'svg',
        input_file_size_kb: 80,
        file_size_kb: 12,
        width: 512,
        height: 320,
        vector_colors: 6,
        vector_paths: 14,
        vector_detail: 70,
        path_smoothing: 35,
        background_removed: true,
      },
    });
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => button('Show paths').click());
    await act(async () => button('Image').click());

    const outputFormat = [...container.querySelectorAll('.route-settings select')].find(select =>
      select.parentElement.textContent.includes('Output format')
    );
    await act(async () => {
      outputFormat.value = 'svg';
      outputFormat.dispatchEvent(new Event('change', { bubbles: true }));
    });
    expect(container.textContent).toContain('Vector settings');
    expect(container.textContent).not.toContain('Advanced image settings');

    const [colors, detail, smoothing] = container.querySelectorAll('input[type="range"]');
    const removeBackground = container.querySelector('.metadata-setting input[type="checkbox"]');
    await act(async () => {
      setInputValue(colors, '6');
      setInputValue(detail, '70');
      setInputValue(smoothing, '35');
      removeBackground.click();
    });
    const input = container.querySelector('#image-input');
    const file = new File(['pixels'], 'logo.png', { type: 'image/png' });
    Object.defineProperty(input, 'files', { value: [file] });
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
    await act(async () => button('Run image path').click());

    expect(apiMocks.convertImage).toHaveBeenCalledWith(file, 'svg', 'high', {
      maxWidth: undefined,
      maxHeight: undefined,
      stripMetadata: true,
      vectorColors: 6,
      vectorDetail: 70,
      pathSmoothing: 35,
      removeBackground: true,
      vectorMaxDimension: 1024,
    });
    expect(apiMocks.downloadImage).toHaveBeenCalledWith('svg-1');
    expect(button('Run image path').disabled).toBe(false);
    expect(container.querySelector('.svg-result-preview img')).toBeNull();
    await act(async () => resolvePreview({ data: '<svg></svg>' }));
    expect(container.querySelector('.svg-result-preview img')).not.toBeNull();
    expect(container.textContent).toContain('6 colors · 14 paths');
    expect(container.textContent).toContain('70% detail · 35% smoothing · background removed');
  });

  it('rejects an invalid image dimension instead of silently omitting it', async () => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => button('Show paths').click());
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

  it('accepts a multi-file drop and exposes partial batch results', async () => {
    const first = new File(['# One'], 'one.md', { type: 'text/markdown' });
    const second = new File(['# Two'], 'two.md', { type: 'text/markdown' });
    const acceptedBatch = {
      id: 'batch-12345678',
      route: 'text',
      state: 'accepted',
      counts: { accepted: 2, running: 0, succeeded: 0, failed: 0 },
      items: [
        { id: 'item-1', position: 0, filename: 'one.md', state: 'accepted' },
        { id: 'item-2', position: 1, filename: 'two.md', state: 'accepted' },
      ],
    };
    apiMocks.createBatch.mockResolvedValueOnce({ data: acceptedBatch });
    apiMocks.executeBatchItem
      .mockResolvedValueOnce({
        data: {
          batch: {
            ...acceptedBatch,
            state: 'accepted',
            counts: { accepted: 1, running: 0, succeeded: 1, failed: 0 },
            items: [
              {
                ...acceptedBatch.items[0],
                state: 'succeeded',
                result_id: 'text-1',
                output_format: 'html',
              },
              acceptedBatch.items[1],
            ],
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          batch: {
            ...acceptedBatch,
            state: 'partial_success',
            counts: { accepted: 0, running: 0, succeeded: 1, failed: 1 },
            items: [
              {
                ...acceptedBatch.items[0],
                state: 'succeeded',
                result_id: 'text-1',
                output_format: 'html',
              },
              { ...acceptedBatch.items[1], state: 'failed', error: 'Invalid source.' },
            ],
          },
        },
      });
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => button('Show paths').click());
    await act(async () => button('Text').click());

    const drop = container.querySelector('.source-drop');
    const dropEvent = new Event('drop', { bubbles: true, cancelable: true });
    Object.defineProperty(dropEvent, 'dataTransfer', { value: { files: [first, second] } });
    await act(async () => drop.dispatchEvent(dropEvent));

    expect(container.textContent).toContain('2 files selected');
    expect(button('Convert 2 files').disabled).toBe(false);
    await act(async () => button('Convert 2 files').click());

    expect(apiMocks.createBatch).toHaveBeenCalledWith(
      'text',
      { target_format: 'html' },
      [
        { filename: 'one.md', size: first.size, sha256: expect.stringMatching(/^[0-9a-f]{64}$/) },
        { filename: 'two.md', size: second.size, sha256: expect.stringMatching(/^[0-9a-f]{64}$/) },
      ],
      expect.any(String)
    );
    expect(apiMocks.executeBatchItem).toHaveBeenNthCalledWith(1, 'batch-12345678', 'item-1', first);
    expect(apiMocks.executeBatchItem).toHaveBeenNthCalledWith(2, 'batch-12345678', 'item-2', second);
    expect(container.textContent).toContain('partial success');
    expect(container.textContent).toContain('Invalid source.');
    expect(button('Download')).not.toBeUndefined();
  });

  it('resumes the same accepted batch only when file content digests match', async () => {
    const first = new File(['# One'], 'one.md', { type: 'text/markdown' });
    const second = new File(['# Two'], 'two.md', { type: 'text/markdown' });
    const restored = {
      id: 'restored-batch',
      route: 'text',
      settings: { target_format: 'html' },
      state: 'accepted',
      counts: { accepted: 2, running: 0, succeeded: 0, failed: 0 },
      items: [
        {
          id: 'restored-1',
          position: 0,
          filename: first.name,
          size: first.size,
          sha256: await sha256File(first),
          state: 'accepted',
        },
        {
          id: 'restored-2',
          position: 1,
          filename: second.name,
          size: second.size,
          sha256: await sha256File(second),
          state: 'accepted',
        },
      ],
    };
    apiMocks.getBatches.mockResolvedValueOnce({ data: [restored] });
    apiMocks.executeBatchItem
      .mockResolvedValueOnce({ data: { batch: restored } })
      .mockResolvedValueOnce({
        data: {
          batch: {
            ...restored,
            state: 'succeeded',
            counts: { accepted: 0, running: 0, succeeded: 2, failed: 0 },
            items: restored.items.map(item => ({
              ...item,
              state: 'succeeded',
              result_id: `result-${item.position}`,
              output_format: 'html',
            })),
          },
        },
      });
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => root.render(<TransformationApp />));
    await act(async () => button('Authenticate').click());
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => button('Show paths').click());
    await act(async () => button('Text').click());
    expect(container.textContent).toContain('Batch restored');
    const input = container.querySelector('#text-input');
    Object.defineProperty(input, 'files', { value: [first, second] });
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
    await act(async () => button('Convert 2 files').click());

    expect(apiMocks.createBatch).not.toHaveBeenCalled();
    expect(apiMocks.executeBatchItem).toHaveBeenNthCalledWith(
      1,
      'restored-batch',
      'restored-1',
      first
    );
  });
});
