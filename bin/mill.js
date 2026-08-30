#!/usr/bin/env node

import { main } from '../mill-cli/main.mjs';

main(process.argv.slice(2)).catch(error => {
  console.error(`mill: ${error.message}`);
  process.exitCode = error.exitCode || 1;
});
