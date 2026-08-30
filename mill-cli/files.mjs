import { access, stat } from 'node:fs/promises';
import path from 'node:path';

export const AUDIO_EXTENSIONS = new Set(['.ogg', '.opus', '.wav', '.mp3', '.m4a', '.aac', '.flac']);
export const LOCAL_EXTENSIONS = new Set([
  '.md', '.markdown', '.html', '.htm', '.tex', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp',
]);

export async function inspectFile(filename) {
  const absolutePath = path.resolve(filename);
  await access(absolutePath);
  const details = await stat(absolutePath);
  if (!details.isFile()) {
    throw new Error(`Not a file: ${absolutePath}`);
  }
  const extension = path.extname(absolutePath).toLowerCase();
  let execution = 'unsupported';
  if (AUDIO_EXTENSIONS.has(extension)) execution = 'authenticated-api';
  if (LOCAL_EXTENSIONS.has(extension)) execution = 'local-python';
  return {
    path: absolutePath,
    name: path.basename(absolutePath),
    extension,
    sizeBytes: details.size,
    execution,
  };
}

export function defaultAudioOutput(input, targetFormat) {
  const parsed = path.parse(path.resolve(input));
  return path.join(parsed.dir, `${parsed.name}.${targetFormat}`);
}
