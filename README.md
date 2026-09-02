# Mill

Mill is Celladore's alpha conversion workspace for documents, images, audio, and
video. Deterministic local tools handle supported document and image formats;
the deployed API provides authenticated media conversion and transcription.

- Web: <https://mill.celladoresystems.com>
- API documentation: <https://api.mill.celladoresystems.com/docs>
- Repository: <https://github.com/celladore/mill>

HTTP availability, dependency readiness, deployment, and an authenticated user
conversion are separate evidence. */api/health* is process liveness;
*/api/ready* checks the configured database dependency. */api/status* is a
persisted status-check collection and is not a health endpoint.

## Mill CLI alpha

The temporary npm identity is *@celladore/mill*. The bare *mill* package belongs
to somebody else, so *npx mill* is not supported and must not be documented as a
Mill command.

*@celladore/mill@0.1.0* is published on the public npm registry, so the commands
below resolve as documented.

    npx @celladore/mill init
    npx @celladore/mill inspect "voice notes/input.ogg"
    npx @celladore/mill convert "voice notes/input.ogg" --format mp3

    npm install --global @celladore/mill
    mill doctor

Audio conversion requires an operator-provided *MYSTIRA_ACCESS_TOKEN*. Web login
does not currently hand a token to the CLI through a supported user flow. The
CLI therefore fails closed when this external token boundary is absent; it does
not fabricate a native OAuth client, scrape the browser session, or store a
credential.

Commands:

- *mill init* writes a non-secret *.millrc.json* in the current directory.
- *mill login* reports whether the external token boundary is satisfied and
  points to the web login. It is not native CLI OIDC acceptance.
- *mill inspect INPUT* reports the selected local/API boundary before work.
- *mill convert INPUT* delegates documents/images to *xtotext* and supported
  audio to the authenticated Mill API, then retrieves the output.
- *mill doctor* checks Node, configuration, identity input, and the compatible
  local Python executable. *--api* checks */docs* availability and explicitly
  does not claim readiness.

The package requires Node 20 or newer. Paths are passed as argument arrays, not
shell strings, so spaces are preserved and no interactive terminal is required.

## Python compatibility

The Python distribution remains *xtotext*, its import remains *xtox*, and its
legacy executable remains *xtotext*. Those are compatibility APIs, not current
product branding, and this alpha does not perform a breaking namespace migration.

    python -m pip install -e ".[dev,azure,api]"
    xtotext --help

Example:

    from xtox.core import DocumentConverter

    converter = DocumentConverter(output_dir="./output")
    result = converter.markdown_to_pdf("document.md", refinement_level=2)

The local Python engine currently supports Markdown, HTML, LaTeX, and common
image conversions. Audio is deliberately delegated to the authenticated API;
the Node package does not duplicate FFmpeg or backend conversion logic.

## Development

    python -m pytest
    pnpm --dir frontend install --frozen-lockfile
    pnpm --dir frontend test
    pnpm --dir frontend build
    npm test
    npm pack --dry-run

Production publication, deployment, DNS, secrets, and OIDC registration changes
are separately authorized operations. See
[the Mill identity inventory](docs/mill-identity-inventory.md) before renaming
any remaining *xtox* or *xtotext* identifier.
