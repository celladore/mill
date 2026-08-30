export function parseArgs(argv) {
  const positionals = [];
  const options = {};
  const booleanOptions = new Set(['force', 'json', 'help', 'version', 'api', 'verbose']);

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--') {
      positionals.push(...argv.slice(index + 1));
      break;
    }
    if (!value.startsWith('--')) {
      positionals.push(value);
      continue;
    }
    const equals = value.indexOf('=');
    const key = value.slice(2, equals === -1 ? undefined : equals);
    if (booleanOptions.has(key)) {
      options[key] = equals === -1 ? true : value.slice(equals + 1) !== 'false';
      continue;
    }
    const optionValue = equals === -1 ? argv[++index] : value.slice(equals + 1);
    if (optionValue === undefined || optionValue.startsWith('--')) {
      throw new Error(`--${key} requires a value`);
    }
    options[key] = optionValue;
  }
  return { positionals, options };
}
