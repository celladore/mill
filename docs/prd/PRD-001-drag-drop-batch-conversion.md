# PRD-001: Unified drag-and-drop intake and batch conversion jobs

| Field | Value |
|---|---|
| Status | Approved for implementation on 2026-08-30 |
| Product | Mill |
| Baton task | `ad307110` |
| Target | Post-alpha product increment |
| Scope | Authenticated web workbench and supporting API contracts |

## Decision summary

Mill should turn the existing route-specific, single-file source picker into an explicit drag-and-drop intake surface for every currently supported route. Conversion routes should accept one or more compatible files. A multi-file submission becomes one authenticated batch job with per-file progress, partial-success reporting, and output retrieval.

The selected route determines the operation. For example, dropping an OGG file on **Audio** means audio conversion, while dropping it on **Transcript** means transcription. The first batch release is route-homogeneous: one route, one set of output settings, many compatible inputs. A mixed drop may be inspected, but incompatible files must be rejected before submission instead of being silently rerouted.

Multi-file transcription is not included automatically. It requires a separate decision because the current transcription path is non-retaining by default, while a pollable batch job needs a bounded result-retrieval contract.

## Problem

The authenticated workbench currently stores one selected file per route and advertises “one file per run.” Its file input is visually styled as a source drop area, but the unified `TransformationApp` does not implement explicit drag events or multi-file selection.

The API also has two older batch endpoints:

- `POST /api/batch/convert-latex`, up to 50 files;
- `POST /api/batch/convert-audio`, up to 20 files.

Those endpoints process files synchronously in the request, do not require the same authenticated ownership contract as the current transformation routes, and do not provide durable job polling, progress, cancellation, or a cross-media model. Extending the UI directly onto those endpoints would preserve inconsistent validation and reliability behavior.

Users need to drop supported files directly onto the operation they intend, submit several conversions together, leave the page or refresh safely, see which items succeeded or failed, and retrieve each successful output without losing ownership isolation.

## Goals

1. Make drag-and-drop a real, accessible input mechanism on every supported transformation route.
2. Keep click-to-browse and keyboard input equivalent to drag-and-drop.
3. Allow multiple compatible files on conversion routes without adding new formats.
4. Represent multi-file work as an authenticated, user-isolated batch job.
5. Report progress and failures per file, including partial success.
6. Preserve existing single-file endpoints and compatibility contracts during migration.
7. Preserve existing artifact-retention and transcription-retention rules.
8. Provide enough observability to distinguish upload, queue, conversion, storage, and download failures.

## Non-goals

- Adding new source or target formats.
- Automatically choosing an operation when the same source supports more than one route.
- Mixing output settings within one batch.
- Multi-file transcription without a separately approved retention design.
- Indefinite file, output, or job retention.
- Introducing a second authentication system.
- Renaming `xtox`, `xtotext`, GHCR images, Azure resources, OIDC audiences, or persisted compatibility fields.
- Bare npm package transfer work.
- Folder recursion, archive extraction, cloud-drive import, scheduling, or recurring jobs.
- Modifying unrelated Celladore products.

## Current supported route contract

The PRD does not expand this matrix. Implementation must derive the deployed capability contract from one authoritative server representation and render the same constraints in the client.

| Route | Accepted sources | Existing targets or result |
|---|---|---|
| Document | `.tex` | PDF |
| Image | `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff`, `.gif` | WebP, JPEG, PNG, GIF, TIFF, BMP, SVG |
| Text | `.md`, `.markdown`, `.html`, `.htm`, `.txt`, `.docx` | Markdown, HTML, plain text, DOCX as currently supported |
| Audio | `.ogg`, `.opus`, `.mp3`, `.wav`, `.m4a`, `.aac`, `.flac` | MP3, WAV, OGG, M4A, AAC, FLAC |
| Transcript | `.ogg`, `.opus`, `.mp3`, `.wav`, `.m4a`, `.aac`, `.flac` | Text transcript; non-retaining by default |
| Video | `.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`, `.m4v` | MP4, WebM, MOV as currently supported |

If deployed capabilities differ from this table, the server contract wins and the documentation must be corrected in the same change.

## User experience

### Single-file flow

1. The signed-in user chooses a transformation route.
2. They drag one compatible file onto the source area or activate the file picker.
3. Mill validates the extension, size, and route compatibility locally for fast feedback.
4. The user chooses route settings and starts the transformation.
5. Mill uses the existing single-file behavior and displays/downloads the result.

### Batch conversion flow

1. The signed-in user chooses a conversion route.
2. They drop or select multiple files.
3. Mill lists every file before upload with name, size, detected source type, and validation state.
4. Incompatible, oversized, duplicate, or excess files remain visible with actionable errors and are excluded from submission until resolved.
5. One shared set of route settings applies to every accepted item.
6. The user submits one batch.
7. Mill returns a batch identifier and renders aggregate plus per-item progress.
8. Completed outputs become independently downloadable. Failed items retain explicit errors.
9. A refresh restores the batch from the server for the same authenticated user.

### Ambiguous sources

Mill must not infer **Audio conversion** versus **Transcription** from an audio filename. The route selected by the user is authoritative. Moving between those routes must not carry a queued file across silently; the UI must ask the user to confirm or reselect it.

## Functional requirements

### FR-1: Explicit drop behavior

- The source surface handles `dragenter`, `dragover`, `dragleave`, and `drop`.
- The browser's default navigation/open-file behavior is prevented for accepted drop targets.
- A visible and programmatically determinable state indicates that a drop is active.
- Dropping directories or non-file data is rejected clearly.
- Click-to-browse remains available.

### FR-2: Multiple selection

- Conversion-route file inputs support `multiple`.
- A single selected file continues to use the established single-file experience unless the implementation deliberately normalizes both paths behind the new job contract.
- Two or more accepted files create a batch submission.
- The UI preserves selection order for display but does not use filenames as identifiers.

### FR-3: Route-scoped validation

- Only files compatible with the selected route are eligible.
- Client validation is advisory; the API repeats every security and limit check.
- Errors name the file and the violated rule.
- Duplicate filenames must not overwrite each other. Stable server item identifiers and collision-safe output names are required.
- An unsupported file never causes supported siblings to disappear from the preflight list.

### FR-4: Authoritative capabilities and limits

The API must expose or otherwise generate one authoritative capability contract containing:

- route identifiers;
- accepted source extensions and content types;
- supported targets;
- per-file size limits;
- maximum items per batch;
- maximum aggregate upload size;
- whether batch execution is enabled for the route;
- retention behavior relevant to the route.

The UI, API documentation, and tests must consume or validate against this contract so their allowlists cannot drift independently.

### FR-5: Batch creation

- Batch creation requires a valid Mystira access token.
- The request identifies one route and one settings object.
- The server validates all items before acknowledging the batch.
- Accepted creation returns HTTP `202` with a stable batch ID and item IDs.
- Idempotency keys are scoped to the authenticated user and enforced atomically on `(user_id, key_hash)`. The normalized route, settings, item order, sanitized filenames, sizes, and SHA-256 content digests form the request fingerprint. An identical retry replays the original batch and item IDs; reusing the key for a different fingerprint returns `409`.
- A rejected batch must not leave unowned uploads or orphaned job records.

### FR-6: Job and item states

Batch states:

- `accepted`
- `running`
- `succeeded`
- `partial_success`
- `failed`

Item states:

- `accepted`
- `running`
- `succeeded`
- `failed`

Every state transition records timestamps. Terminal item states do not regress. Aggregate counts are derived from items rather than maintained as an independent source of truth.

Cancellation is not required for the first release. The implementation must not advertise cancellation until workers can stop or fence in-flight work safely.

### FR-7: Durable execution

- Production work must not rely only on a web-process memory structure or an untracked `BackgroundTasks` callback.
- Job and item state survives API restarts.
- Item execution is claimed atomically with a unique fencing token and a 15-minute deadline. An expired claim may be recovered once; terminal writes require the current token so an abandoned request cannot overwrite the recovered attempt.
- Retries are bounded and distinguish transient infrastructure failures from deterministic file failures.
- A retry does not overwrite a previously successful output.

The implementation design may reuse existing Azure and MongoDB infrastructure, but any new queue, worker, storage, or Terraform resource requires a reviewed operational plan before production apply.

### FR-8: Progress and restoration

- The batch response exposes aggregate counts and per-item states.
- The UI polls with bounded backoff and stops on terminal state, logout, navigation away, or explicit dismissal.
- Refreshing the page restores non-expired batches owned by the signed-in user.
- The UI distinguishes upload progress from server processing progress when both are available.
- Simulated percentage progress must not be presented as measured server progress.

### FR-9: Results and partial failure

- Each successful item exposes the same result metadata and output retrieval semantics as its single-file route.
- Each failed item exposes a stable, user-safe error code plus actionable text.
- Item execution returns the current item and batch representation with HTTP 200 after a handled conversion failure; clients determine the outcome from `item.state` and `error_code` so partial success remains representable in one batch.
- A batch can finish as `partial_success`.
- Successful siblings remain downloadable when another item fails.
- “Download all” is deferred unless it can be implemented without changing retention or materializing an unbounded archive.
- Retrying failed items creates a new batch linked to the prior batch; the original audit record remains unchanged.

### FR-10: Authentication and authorization

- Every create, list, status, item, and download operation requires authentication.
- Batch and item queries are filtered by the authenticated user before counts, metadata, or existence are disclosed.
- A user cannot infer another user's batch through IDs, status codes, previews, or timing-sensitive list results.
- Logout clears client-side queued files, polling, previews, and result URLs.
- Missing identity configuration fails closed.

### FR-11: Retention

- Existing route-specific artifact expiration remains authoritative.
- Job metadata must have an explicit bounded retention period.
- Expired output is represented distinctly from failed conversion.
- Cleanup is idempotent and removes uploaded sources, converted outputs, and job metadata according to their policies.
- Non-retaining transcription remains unchanged in this release.

### FR-12: Accessibility

- The source area is reachable and operable by keyboard.
- The native file picker remains the keyboard and assistive-technology fallback.
- Validation and state changes are announced through an appropriate live region without repeated noise.
- Progress is represented semantically, not by color alone.
- Per-file remove and error controls have file-specific accessible names.
- Focus moves predictably after submission and after removing an invalid file.

## Proposed API shape

Exact naming may change during technical design, but one consistent route family is required.

```text
GET    /api/capabilities
POST   /api/batches
GET    /api/batches
GET    /api/batches/{batch_id}
GET    /api/batches/{batch_id}/items/{item_id}
GET    /api/batches/{batch_id}/items/{item_id}/download
POST   /api/batches/{batch_id}/retry-failed
```

The initial `POST /api/batches` may use multipart upload if bounded aggregate limits make one request safe. If direct-to-storage staging is required, it must preserve the same ownership, idempotency, validation, and orphan-cleanup contract.

The existing `/api/batch/convert-latex` and `/api/batch/convert-audio` endpoints must be classified during design as one of:

1. compatibility wrappers over the new job service;
2. deprecated endpoints with a documented migration window; or
3. removed before public reliance, if authoritative usage evidence confirms no consumers.

They must not remain as an undocumented second batch model.

## Data model requirements

### Batch

- `id`
- `user_id`
- `route`
- normalized settings
- state
- item counts derived from items
- idempotency key hash
- created, started, completed, and expires timestamps
- optional retry-of batch ID

### Batch item

- `id`
- `batch_id`
- original display filename
- collision-safe source and output keys
- source and target formats
- state
- safe error code and message
- existing conversion/result ID when successful
- created, started, completed, and artifact-expiry timestamps
- bounded attempt count

No durable schema should use `mill` where an existing neutral or compatibility-safe field name is sufficient.

## Limits

Limits must be explicit configuration, exposed through capabilities, enforced server-side, and covered by tests. The implementation PR must propose measured initial values for:

- items per batch by route;
- bytes per file by route;
- aggregate bytes per batch;
- concurrent running items per user;
- concurrent batches per user;
- polling interval and backoff ceiling;
- retry count;
- job metadata retention.

The existing 50-file LaTeX and 20-file audio limits are research inputs, not automatically approved cross-media defaults.

## Observability

Record structured events without source content, transcript text, access tokens, or sensitive filenames:

- batch accepted/rejected;
- item started/succeeded/failed;
- batch terminal state;
- queue/claim latency;
- processing duration by route;
- sanitized error code;
- cleanup success/failure;
- output retrieval success/failure.

Metrics must allow operators to distinguish API availability, queue health, worker health, conversion failures, and expired artifacts.

## Compatibility and migration

- Existing single-file API routes remain supported.
- Existing history records remain readable.
- `xtox` imports and the `xtotext` Python distribution remain unchanged.
- `@celladore/mill` and the installed `mill` executable remain unchanged.
- The PRD does not add a CLI batch command. A later CLI design may consume the same job API.
- CoilTrace's existing `mill.render` contract must not be changed by the batch API.

## Rollout plan

1. Approve this PRD and resolve the open decisions below.
2. Land the server capability contract and shared validation tests.
3. Land durable batch persistence and execution behind a disabled production flag.
4. Add API contract, ownership, idempotency, partial-failure, and cleanup tests.
5. Add the unified drop/preflight UI and accessibility tests.
6. Exercise exact packed/frontend/backend builds on the implementation head.
7. Deploy through the existing production approval gate.
8. Verify health separately from a legitimate signed-in batch acceptance run.
9. Record representative outputs, partial-failure behavior, and cleanup evidence in Baton.

## Acceptance criteria

1. A signed-in user can drag or browse one supported file on every current route.
2. A signed-in user can select or drop multiple compatible files on each conversion route.
3. The selected route unambiguously determines the operation.
4. Invalid files remain visible with actionable errors and cannot enter server processing.
5. Batch creation returns stable batch and item IDs.
6. Batch and item state survive an API restart.
7. One failed item produces `partial_success` without hiding successful outputs.
8. Duplicate filenames never collide or overwrite.
9. Refresh restores the user's non-expired batch.
10. Cross-user batch, item, and output access fails without disclosing existence.
11. Logout stops polling and clears client-side file and blob state.
12. Existing single-file conversion and non-retaining transcription acceptance do not regress.
13. The implementation adds no new supported formats or unrelated product features.
14. Production acceptance retrieves at least two successful outputs from one batch and demonstrates one safe partial failure.

## Required tests

- Unit tests for drop parsing, route validation, duplicate names, limits, and client state cleanup.
- Component tests for mouse drag/drop, keyboard browse, live-region announcements, progress, refresh restoration, and partial failure.
- API tests for authentication, ownership filtering, idempotency, invalid files, aggregate limits, state transitions, retry fencing, and output expiry.
- Worker tests for atomic claims, bounded retry, restart recovery, and cleanup.
- Compatibility tests for existing single-file and legacy batch endpoints.
- Production acceptance with a legitimate Mystira session and representative supported inputs.

## Open decisions before implementation

1. **Execution mechanism — resolved for the first increment:** use MongoDB-persisted batch and item records with atomic per-item claims. The authenticated browser coordinates bounded, synchronous item execution requests through the API. This survives API restarts without an in-memory queue or `BackgroundTasks`; accepted files that were not uploaded must be reselected after a refresh. A server-side queue/worker remains a later operational change requiring its own reviewed deployment plan.
2. **Measured limits — resolved for the first increment:** 10 items per conversion batch, existing route-specific per-file limits, 200 MiB declared aggregate size, one active item request per browser batch, at most two fenced claims per item, a 15-minute claim lease, and seven-day batch metadata retention. These values are configuration-backed and exposed by `/api/capabilities`.
3. **Legacy batch endpoints:** wrap, deprecate, or remove based on consumer evidence.
4. **Multi-file transcription:** decide separately whether a bounded encrypted temporary-result contract can preserve the intended non-retaining behavior. It is excluded until approved.
5. **Download all:** include only if bounded archive creation and cleanup can be demonstrated; otherwise retain per-item downloads.

## Evidence required for closeout

- Approved PRD and linked Baton task.
- Exact implementation commit and reviewed PR.
- Full backend/frontend and compatibility test evidence.
- Deployment workflow and exact image digest.
- Healthy deployed revision and readiness evidence.
- Legitimate signed-in drag/drop and batch acceptance.
- Retrieved representative outputs and observed partial failure.
- Retention/cleanup evidence after the configured expiry.
