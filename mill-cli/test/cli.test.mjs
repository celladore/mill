import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import product from '../../product.json' with { type: 'json' };
import packageManifest from '../../package.json' with { type: 'json' };
import { convertAudio } from '../api.mjs';
import { parseArgs } from '../args.mjs';
import { inspectFile } from '../files.mjs';
import { resolveAuthenticatedOutput } from '../main.mjs';
import { commandAvailable } from '../process.mjs';

test('public package metadata stays synchronized', () => {
  assert.equal(packageManifest.name, product.npmPackage);
  assert.equal(packageManifest.version, product.version);
  assert.deepEqual(packageManifest.bin, { mill: 'bin/mill.js' });
  assert.equal(packageManifest.engines.node, '>=20.10.0');
});

test('argument parser preserves paths with spaces as one value', () => {
  const parsed = parseArgs(['convert', 'voice notes/input.ogg', '--output', 'converted notes/result.mp3']);
  assert.deepEqual(parsed.positionals, ['convert', 'voice notes/input.ogg']);
  assert.equal(parsed.options.output, 'converted notes/result.mp3');
});

test('init is non-interactive and writes non-secret configuration', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'mill init '));
  const result = spawnSync(process.execPath, [path.resolve('bin/mill.js'), 'init', '--json'], {
    cwd: directory,
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  const config = JSON.parse(await readFile(path.join(directory, '.millrc.json'), 'utf8'));
  assert.equal(config.apiUrl, product.apiUrl);
  assert.equal(config.pythonExecutable, product.pythonExecutable);
  assert.doesNotMatch(JSON.stringify(config), /token|secret/i);
});

test('login reports the external token boundary without storing credentials', () => {
  const environment = { ...process.env };
  delete environment.MYSTIRA_ACCESS_TOKEN;
  const result = spawnSync(process.execPath, [path.resolve('bin/mill.js'), 'login', '--json'], {
    env: environment,
    encoding: 'utf8',
  });
  assert.equal(result.status, 2);
  const report = JSON.parse(result.stdout);
  assert.equal(report.authenticatedInputPresent, false);
  assert.equal(report.storesCredentials, false);
  assert.match(report.note, /does not currently hand a token/);
});

test('doctor is useful in a clean non-TTY process', () => {
  const result = spawnSync(process.execPath, [path.resolve('bin/mill.js'), 'doctor', '--json'], {
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.node.supported, true);
  assert.equal(report.auth.storedByMill, false);
  assert.equal(report.localPython.compatibilityImport, 'xtox');
});

test('executable diagnostics probe the command directly', async () => {
  assert.equal(await commandAvailable(process.execPath), true);
  assert.equal(await commandAvailable('mill-command-that-does-not-exist'), false);
});

test('unknown options fail actionably instead of being ignored', () => {
  const result = spawnSync(
    process.execPath,
    [path.resolve('bin/mill.js'), 'convert', 'input.md', '--formta', 'pdf'],
    { encoding: 'utf8' },
  );
  assert.equal(result.status, 2);
  assert.match(result.stderr, /Unknown option for convert: --formta/);
});

test('extra positional arguments are rejected', () => {
  const result = spawnSync(
    process.execPath,
    [path.resolve('bin/mill.js'), 'inspect', 'first.md', 'second.md'],
    { encoding: 'utf8' },
  );
  assert.equal(result.status, 2);
  assert.match(result.stderr, /inspect expects exactly one input file/);
});

test('local conversion rejects unsupported JSON output explicitly', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'mill local json '));
  const input = path.join(directory, 'input file.md');
  await writeFile(input, '# fixture');
  const result = spawnSync(
    process.execPath,
    [path.resolve('bin/mill.js'), 'convert', input, '--format', 'html', '--json'],
    { encoding: 'utf8' },
  );
  assert.equal(result.status, 2);
  assert.match(result.stderr, /--json is not available for the local xtotext compatibility engine/);
});

test('inspect routes audio to the authenticated API boundary', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'mill inspect '));
  const input = path.join(directory, 'voice note.ogg');
  await writeFile(input, 'fixture');
  const result = await inspectFile(input);
  assert.equal(result.execution, 'authenticated-api');
  assert.equal(result.path, input);
});

test('audio conversion fails closed without Mystira identity', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'mill auth '));
  const input = path.join(directory, 'voice note.ogg');
  await writeFile(input, 'fixture');
  await assert.rejects(
    convertAudio({ input, apiUrl: product.apiUrl, token: '' }),
    /operator-provided Mystira access token in MYSTIRA_ACCESS_TOKEN/,
  );
});

test('audio conversion never overwrites its input, even with force', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'mill same path '));
  const input = path.join(directory, 'voice note.ogg');
  await writeFile(input, 'fixture');
  await assert.rejects(
    convertAudio({
      input,
      output: input,
      apiUrl: product.apiUrl,
      token: 'test-token',
      force: true,
    }),
    /Output path must differ from the input path/,
  );
  assert.equal(await readFile(input, 'utf8'), 'fixture');
});

test('authenticated output-dir preserves the derived filename and spaces', () => {
  const output = resolveAuthenticatedOutput(
    path.join('source notes', 'voice note.ogg'),
    { 'output-dir': path.join('converted notes', 'release output') },
    'mp3',
  );
  assert.equal(
    output,
    path.resolve('converted notes', 'release output', 'voice note.mp3'),
  );
  assert.throws(
    () =>
      resolveAuthenticatedOutput(
        'voice.ogg',
        { output: 'voice.mp3', 'output-dir': 'converted' },
        'mp3',
      ),
    /Use either --output or --output-dir, not both/,
  );
});

test('audio conversion uses the API contract and retrieves the output', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'mill api '));
  const input = path.join(directory, 'voice note.ogg');
  const output = path.join(directory, 'result file.mp3');
  await writeFile(input, 'audio');
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    if (calls.length === 1) {
      return new Response(JSON.stringify({ id: 'conversion-1', filename: 'voice note.ogg', success: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    }
    return new Response('converted-audio', { status: 200 });
  };
  const result = await convertAudio({
    input,
    output,
    apiUrl: product.apiUrl,
    token: 'test-token',
    fetchImpl,
  });
  assert.match(calls[0].url, /\/api\/convert-audio\?target_format=mp3&bitrate=192k$/);
  assert.equal(calls[0].options.headers.Authorization, 'Bearer test-token');
  assert.match(calls[1].url, /\/api\/download-audio\/conversion-1$/);
  assert.equal(await readFile(output, 'utf8'), 'converted-audio');
  assert.equal(result.output, output);
});
