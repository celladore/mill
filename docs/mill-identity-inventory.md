# Mill identity inventory

Mill is the product name. This inventory prevents a branding pass from breaking
compatibility, infrastructure, identity, persisted records, or audit history.

| Surface | Classification | Alpha treatment |
| --- | --- | --- |
| README, API title/root response, current product copy | Stale user-facing branding | Present as Mill. |
| npm package and executable | New public surface | *@celladore/mill*; executable *mill*. Never claim the unrelated bare package or *npx mill*. |
| Python distribution *xtotext*, import *xtox*, executable *xtotext* | Compatibility API | Preserve. The Node CLI delegates supported local conversion to this executable. |
| *celladore-xtox* OIDC client and token audience | Load-bearing external identity | Preserve until a separately authorized registration migration exists. |
| *ghcr.io/celladore/xtox-api*, Terraform state key, module/resource names and Azure resource names | Load-bearing cloud identity | Preserve. Renaming source labels does not rename deployed/stateful objects. |
| API routes and serialized fields | External/persisted contract | Preserve. Additive */api/health* liveness and */api/ready* dependency-readiness routes are explicit. |
| MongoDB collection names and stored conversion records | Persisted data contract | Preserve; no migration in this release slice. |
| old migration guides, incident comments, task IDs and historical examples | Historical record | Keep identifiers when needed for provenance; do not present them as the current product name. |
| CoilTrace *mill.render* scope and delegated audience behavior | Compatibility API | Preserve and verify through existing contract tests; do not widen access. |
| legacy Azure Functions source and older deployment/migration guides | Historical/load-bearing boundary | Do not promote as the canonical FastAPI deployment and do not mass-rename without a separately scoped retirement or state migration. |
| *XTOX_MCP_MAX_IMAGE_BYTES* | Compatibility environment variable | Preserve while presenting the MCP server itself as Mill. |
| MCP protocol server name *xtox-images* and webhook User-Agent *XToX-Converter/1.0* | External compatibility contract | Preserve until consumer traces support a versioned migration; human-facing MCP registration examples may use the *mill-images* client alias. |

Public values used by the npm CLI live in [product.json](../product.json). That
single manifest makes the temporary scoped-package choice easy to reverse without
scattering package names, URLs, and compatibility identifiers through the code.
