import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TransformationHistory } from './TransformationHistory';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const items = [
  {
    id: 'image-1',
    kind: 'image',
    filename: 'hero.png',
    input_format: 'png',
    output_format: 'webp',
    input_size_kb: 400,
    output_size_kb: 100,
    quality: 'custom',
    quality_value: 72,
    success: true,
    downloadable: true,
    timestamp: '2026-08-27T10:07:00Z',
  },
  ...Array.from({ length: 6 }, (_, index) => ({
    id: `document-${index}`,
    kind: 'document',
    filename: `paper-${index}.tex`,
    input_format: 'tex',
    output_format: 'pdf',
    success: true,
    downloadable: false,
    timestamp: `2026-08-27T10:0${6 - index}:00Z`,
  })),
];

function setInputValue(input, value) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

describe('TransformationHistory', () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('highlights outcomes and supports paging, searching, and type filtering', async () => {
    await act(async () =>
      root.render(
        <TransformationHistory
          items={items}
          loading={false}
          error=""
          onRefresh={vi.fn()}
          onDownload={vi.fn()}
        />
      )
    );

    expect(container.textContent).toContain('Showing 1–6 of 7');
    expect(container.textContent).toContain('75% smaller');
    expect(container.textContent).toContain('400.0 KB → 100.0 KB');
    expect(container.textContent).toContain('Custom quality · 72%');

    const next = Array.from(container.querySelectorAll('button')).find(
      button => button.textContent === 'Next'
    );
    await act(async () => next.click());
    expect(container.textContent).toContain('Showing 7–7 of 7');

    const search = container.querySelector('input[type="search"]');
    await act(async () => {
      setInputValue(search, 'hero');
    });
    expect(container.textContent).toContain('Showing 1–1 of 1');
    expect(container.textContent).toContain('hero.png');

    const filter = container.querySelector('.history-filter select');
    await act(async () => {
      setInputValue(search, '');
      filter.value = 'image';
      filter.dispatchEvent(new Event('change', { bubbles: true }));
    });
    expect(container.textContent).toContain('Showing 1–1 of 1');
    expect(container.textContent).not.toContain('paper-0.tex');
  });
});
