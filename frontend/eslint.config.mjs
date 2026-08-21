import eslint from '@eslint/js';
import eslintReact from '@eslint-react/eslint-plugin';
import globals from 'globals';

export default [
  eslint.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.es2021,
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: eslintReact.configs.recommended.plugins,
    settings: eslintReact.configs.recommended.settings,
    rules: {
      ...eslintReact.configs.recommended.rules,
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
  {
    ignores: [
      'build/**',
      'node_modules/**',
      '*.config.js',
      '**/xtotext Tailwind Configuration.js', // Design token reference file
    ],
  },
];
