import { spawn } from 'node:child_process';

export function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { shell: false, stdio: 'inherit', ...options });
    child.once('error', error => {
      if (error.code === 'ENOENT') {
        const wrapped = new Error(
          `Could not find ${command}. Install the compatible Python distribution with "python -m pip install xtotext".`,
        );
        wrapped.exitCode = 2;
        reject(wrapped);
        return;
      }
      reject(error);
    });
    child.once('exit', (code, signal) => {
      if (signal) reject(new Error(`${command} stopped by signal ${signal}`));
      else resolve(code ?? 1);
    });
  });
}

export async function commandAvailable(command) {
  return new Promise(resolve => {
    const child = spawn(command, ['--help'], {
      shell: false,
      stdio: 'ignore',
      windowsHide: true,
    });
    child.once('error', () => resolve(false));
    child.once('exit', code => resolve(code === 0));
  });
}
