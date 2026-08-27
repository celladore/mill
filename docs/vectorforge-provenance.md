# VectorForge conversion-core provenance

Mill's deterministic raster-to-SVG path is a Python/Pillow adaptation of conversion concepts audited from [JustAGhosT/vectorforge](https://github.com/JustAGhosT/vectorforge) on 2026-08-27. It is not a verbatim copy of the original TypeScript implementation.

Selected source history:

- `21f46077a298063231ebd8be9ba9ef74716bd8b4` - exercised converter improvements
- `dfe44599a0ed9648eeae40dbb238c3bfad8e932e` - Potrace integration and tracing behavior
- `6f6c5f91946947acb9894f3741e2ae5a6fee860d` - background-removal behavior
- `e1067b1943bb7a2e85989108a88e0e5eb34ba9f1` - background color-threshold correction

The adapted scope is limited to deterministic quantization, color-layer extraction, contour tracing, path simplification/smoothing, SVG generation, and optional flat-background removal. Mill supplies its own bounded settings, owner-scoped records, private artifact storage, preview, and download behavior.

Not absorbed: the Netlify application shell, UI/component dependency graph, direct Azure/OpenAI integrations, provider keys, or the unreferenced `src/lib/pipeline` implementation. No direct AI-provider fallback was introduced.

## Upstream license notice

MIT License

Copyright GitHub, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
