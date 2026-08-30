import path from 'node:path';

import product from '../product.json' with { type: 'json' };
import { convertAudio, probeApiDocs } from './api.mjs';
import { parseArgs } from './args.mjs';
import { normalizeApiUrl, readConfig, writeConfig } from './config.mjs';
import { inspectFile } from './files.mjs';
import { commandAvailable, run } from './process.mjs';

const HELP = `Mill ${product.version} (${product.status})

Usage:
  mill init [--api-url URL] [--force] [--json]
  mill login [--json]
  mill convert INPUT [--format FORMAT] [--output FILE] [--output-dir DIR] [--force] [--json]
  mill inspect INPUT [--json]
  mill doctor [--api] [--json]
  mill --help
  mill --version

Examples:
  npx @celladore/mill init
  npx @celladore/mill convert "voice notes/input.ogg" --format mp3
  npm install --global @celladore/mill

The Python distribution/import names xtotext and xtox remain compatibility APIs.
Audio uses Mill's authenticated API and requires MYSTIRA_ACCESS_TOKEN.`;

const COMMAND_OPTIONS = {
  init: new Set(['api-url', 'force', 'json']),
  login: new Set(['json']),
  convert: new Set([
    'format',
    'output',
    'output-dir',
    'force',
    'json',
    'bitrate',
    'sample-rate',
    'api-url',
    'verbose',
  ]),
  inspect: new Set(['json']),
  doctor: new Set(['api', 'json']),
};

function validateInvocation(command, positionals, options) {
  const allowed = COMMAND_OPTIONS[command];
  if (!allowed) {
    const error = new Error(`Unknown command: ${command}. Run "mill --help".`);
    error.exitCode = 2;
    throw error;
  }
  const unknown = Object.keys(options).find(option => !allowed.has(option));
  if (unknown) {
    const error = new Error(`Unknown option for ${command}: --${unknown}. Run "mill ${command} --help".`);
    error.exitCode = 2;
    throw error;
  }
  const expected = command === 'convert' || command === 'inspect' ? 1 : 0;
  if (positionals.length !== expected) {
    const noun = expected === 1 ? 'exactly one input file' : 'no positional arguments';
    const error = new Error(`${command} expects ${noun}`);
    error.exitCode = 2;
    throw error;
  }
}

function print(value, json = false) {
  console.log(json ? JSON.stringify(value, null, 2) : value);
}

async function initCommand(options) {
  const apiUrl = normalizeApiUrl(options['api-url'] || product.apiUrl);
  const result = await writeConfig(process.cwd(), { apiUrl }, { force: options.force });
  print(options.json ? result : `Created ${result.path}\nAPI: ${result.value.apiUrl}`, options.json);
}

async function loginCommand(options, environment) {
  const tokenPresent = Boolean(environment[product.tokenEnvironmentVariable]);
  const result = {
    authenticatedInputPresent: tokenPresent,
    tokenSource: product.tokenEnvironmentVariable,
    loginUrl: product.siteUrl,
    storesCredentials: false,
    note: tokenPresent
      ? 'A Mystira access token is available to this process. The API validates it on each request.'
      : 'No operator-provided token is available. Web login does not currently hand a token to this CLI. Native CLI OAuth is not part of this alpha package; no credential is fabricated or stored.',
  };
  print(options.json ? result : `${result.note}\nLogin: ${result.loginUrl}`, options.json);
  if (!tokenPresent) process.exitCode = 2;
}

async function inspectCommand(input, options) {
  if (!input) throw new Error('inspect requires an input file');
  const file = await inspectFile(input);
  const result = {
    ...file,
    requirement:
      file.execution === 'authenticated-api'
        ? product.tokenEnvironmentVariable
        : file.execution === 'local-python'
          ? product.pythonExecutable
          : 'No alpha conversion route is defined for this format.',
  };
  print(options.json ? result : `${result.path}\nMode: ${result.execution}\nRequirement: ${result.requirement}`, options.json);
  if (file.execution === 'unsupported') process.exitCode = 2;
}

async function convertCommand(input, options, environment) {
  if (!input) throw new Error('convert requires an input file');
  const file = await inspectFile(input);
  const config = await readConfig();
  if (file.execution === 'authenticated-api') {
    const result = await convertAudio({
      input: file.path,
      output: options.output,
      targetFormat: options.format || 'mp3',
      bitrate: options.bitrate || '192k',
      sampleRate: options['sample-rate'],
      apiUrl: normalizeApiUrl(options['api-url'] || config.value.apiUrl),
      token: environment[product.tokenEnvironmentVariable],
      force: options.force,
    });
    print(options.json ? result : `Converted ${file.name}\nOutput: ${result.output}`, options.json);
    return;
  }
  if (file.execution !== 'local-python') {
    const error = new Error(`No alpha conversion route is defined for ${file.extension || 'files without an extension'}`);
    error.exitCode = 2;
    throw error;
  }
  if (options.json) {
    const error = new Error(
      '--json is not available for the local xtotext compatibility engine; omit --json or use mill inspect --json first',
    );
    error.exitCode = 2;
    throw error;
  }
  if (options.output) {
    throw new Error('Local Python conversion accepts --output-dir, not --output');
  }
  const args = [file.path];
  if (options['output-dir']) args.push('--output', path.resolve(options['output-dir']));
  if (options.format) args.push('--format', options.format);
  if (options.verbose) args.push('--verbose');
  const code = await run(config.value.pythonExecutable, args);
  if (code !== 0) {
    const error = new Error(`${config.value.pythonExecutable} exited with code ${code}`);
    error.exitCode = code;
    throw error;
  }
}

async function doctorCommand(options, environment) {
  const config = await readConfig();
  const result = {
    product: `${product.name} ${product.version} (${product.status})`,
    node: { version: process.versions.node, supported: Number(process.versions.node.split('.')[0]) >= 20 },
    config: { path: config.path, exists: config.exists, apiUrl: config.value.apiUrl },
    auth: {
      environmentVariable: product.tokenEnvironmentVariable,
      present: Boolean(environment[product.tokenEnvironmentVariable]),
      storedByMill: false,
    },
    localPython: {
      executable: config.value.pythonExecutable,
      available: await commandAvailable(config.value.pythonExecutable),
      compatibilityDistribution: product.pythonDistribution,
      compatibilityImport: product.pythonImport,
    },
  };
  if (options.api) result.apiDocs = await probeApiDocs(normalizeApiUrl(config.value.apiUrl));
  print(
    options.json
      ? result
      : [
          result.product,
          `Node: ${result.node.version} (${result.node.supported ? 'supported' : 'unsupported'})`,
          `Config: ${result.config.exists ? result.config.path : 'defaults (run mill init)'}`,
          `Mystira token: ${result.auth.present ? 'present' : 'absent'}`,
          `Local ${result.localPython.executable}: ${result.localPython.available ? 'available' : 'not found'}`,
          ...(result.apiDocs
            ? [`API docs: ${result.apiDocs.available ? `available (${result.apiDocs.status})` : 'unavailable'}`, result.apiDocs.note]
            : []),
        ].join('\n'),
    options.json,
  );
}

export async function main(argv, { environment = process.env } = {}) {
  const { positionals, options } = parseArgs(argv);
  const command = positionals.shift();
  if (options.version || command === 'version') return print(product.version);
  if (options.help || !command || command === 'help') return print(HELP);
  validateInvocation(command, positionals, options);
  if (command === 'init') return initCommand(options);
  if (command === 'login') return loginCommand(options, environment);
  if (command === 'inspect') return inspectCommand(positionals[0], options);
  if (command === 'convert') return convertCommand(positionals[0], options, environment);
  if (command === 'doctor') return doctorCommand(options, environment);
}
