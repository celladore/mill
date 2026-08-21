import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const indexHtml = readFileSync(resolve('index.html'), 'utf8');

describe('browser chrome', () => {
  it('uses XtOX metadata and contains no Emergent badge', () => {
    expect(indexHtml).toContain('<title>XtOX — Convert documents and audio</title>');
    expect(indexHtml).toContain('href="/xtox-mark.svg"');
    expect(indexHtml).not.toContain('emergent-badge');
    expect(indexHtml).not.toContain('Made with Emergent');
  });
});
