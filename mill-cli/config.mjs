import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import product from '../product.json' with { type: 'json' };

export const CONFIG_FILENAME = '.millrc.json';

export function configPath(cwd = process.cwd()) {
  return path.join(cwd, CONFIG_FILENAME);
}

export async function readConfig(cwd = process.cwd()) {
  const filename = configPath(cwd);
  try {
    const value = JSON.parse(await readFile(filename, 'utf8'));
    return {
      path: filename,
      exists: true,
      value: {
        schemaVersion: 1,
        apiUrl: product.apiUrl,
        pythonExecutable: product.pythonExecutable,
        ...value,
      },
    };
  } catch (error) {
    if (error.code === 'ENOENT') {
      return {
        path: filename,
        exists: false,
        value: {
          schemaVersion: 1,
          apiUrl: product.apiUrl,
          pythonExecutable: product.pythonExecutable,
        },
      };
    }
    if (error instanceof SyntaxError) {
      throw new Error(`${filename} is not valid JSON`);
    }
    throw error;
  }
}

export async function writeConfig(cwd, value, { force = false } = {}) {
  const current = await readConfig(cwd);
  if (current.exists && !force) {
    const error = new Error(`${current.path} already exists; use --force to replace it`);
    error.exitCode = 2;
    throw error;
  }
  const next = {
    schemaVersion: 1,
    apiUrl: value.apiUrl || product.apiUrl,
    pythonExecutable: product.pythonExecutable,
  };
  await writeFile(current.path, `${JSON.stringify(next, null, 2)}\n`, {
    encoding: 'utf8',
    flag: force ? 'w' : 'wx',
  });
  return { path: current.path, value: next };
}

export function normalizeApiUrl(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`Invalid API URL: ${value}`);
  }
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('API URL must use http or https');
  }
  return url.toString().replace(/\/$/, '');
}
