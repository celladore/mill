import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { defaultAudioOutput } from './files.mjs';

async function responseError(response) {
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    detail = body.detail || body.message || detail;
  } catch {
    // The status line is sufficient when the body is not JSON.
  }
  const error = new Error(`Mill API request failed: ${detail}`);
  error.exitCode = response.status === 401 || response.status === 403 ? 2 : 1;
  return error;
}

export async function convertAudio({
  input,
  output,
  targetFormat = 'mp3',
  bitrate = '192k',
  sampleRate,
  apiUrl,
  token,
  force = false,
  fetchImpl = fetch,
}) {
  if (!token) {
    const error = new Error(
      'Audio conversion requires an operator-provided Mystira access token in MYSTIRA_ACCESS_TOKEN. Web login does not currently hand a token to this CLI; the alpha CLI does not implement a separate OAuth client or store credentials.',
    );
    error.exitCode = 2;
    throw error;
  }

  const inputPath = path.resolve(input);
  const outputPath = path.resolve(output || defaultAudioOutput(input, targetFormat));
  if (path.relative(inputPath, outputPath) === '') {
    const error = new Error('Output path must differ from the input path');
    error.exitCode = 2;
    throw error;
  }
  if (!force) {
    try {
      await readFile(outputPath);
      const error = new Error(`${outputPath} already exists; use --force to replace it`);
      error.exitCode = 2;
      throw error;
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }

  const source = await readFile(inputPath);
  const form = new FormData();
  form.append('file', new Blob([source]), path.basename(inputPath));
  const query = new URLSearchParams({ target_format: targetFormat, bitrate });
  if (sampleRate) query.set('sample_rate', String(sampleRate));
  const headers = { Authorization: `Bearer ${token}`, 'X-Request-ID': crypto.randomUUID() };
  const conversion = await fetchImpl(`${apiUrl}/api/convert-audio?${query}`, {
    method: 'POST',
    headers,
    body: form,
  });
  if (!conversion.ok) throw await responseError(conversion);
  const result = await conversion.json();
  if (!result.id || result.success === false) {
    throw new Error(`Mill API did not complete the conversion: ${(result.errors || []).join('; ') || 'missing conversion id'}`);
  }

  const download = await fetchImpl(`${apiUrl}/api/download-audio/${encodeURIComponent(result.id)}`, { headers });
  if (!download.ok) throw await responseError(download);
  await writeFile(outputPath, Buffer.from(await download.arrayBuffer()));
  return { ...result, output: outputPath };
}

export async function probeApiDocs(apiUrl, fetchImpl = fetch) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetchImpl(`${apiUrl}/docs`, { signal: controller.signal });
    return {
      available: response.ok,
      status: response.status,
      note: 'This checks API documentation availability, not application readiness.',
    };
  } catch (error) {
    return { available: false, error: error.message, note: 'No readiness claim is made.' };
  } finally {
    clearTimeout(timeout);
  }
}
