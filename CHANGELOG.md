# Changelog

All notable changes to `juniper-cascor-client` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.1] - 2026-09-05

### Deprecated

- **`auto_pong=False` is deprecated and will be removed in 0.9.0** (defect-register
  `APD-ECO-007`, which owns the removal-date half of `APD-CCLIENT-012`). Constructing any of
  `CascorTrainingStream`, `CascorControlStream` or `FakeCascorTrainingStream` with the legacy
  posture now emits a `DeprecationWarning` naming the removal version.

  **Why dated rather than kept.** It shipped as a *silent* opt-out: no warning either way and no
  removal stated. The source primer names the consequence — "the risk is that the flag never goes
  away: nothing tells you who still sets it" — and contrasts it with the `juniper-data-client`
  alias deprecation, which is "warned, dated, loud" and whose "dated window turns a deprecation
  from a permanent tax into a plan". A fleet census answered the open question: **zero** production
  users. Every occurrence across juniper-canopy / cascor / cascor-worker / data / recurrence / ml is
  absent; all eleven in this repo are its own tests.

  **The escape hatch is not being taken away silently.** `auto_pong=False` remains legitimate for a
  relay that forwards pings, and the warning says so: if you need it, say so before 0.9.0 and the
  posture can be kept deliberately. Removal version lives in
  `constants.AUTO_PONG_REMOVAL_VERSION`.

  **The fake warns too**, at its own `stacklevel` (3, versus production's 4, because it sets
  `_auto_pong` directly rather than through `_init_liveness`). A consumer migrating against the fake
  must see the same deprecation production emits — the #91 fake-parity lesson. Both levels are pinned
  by tests asserting the warning is attributed to the *caller's* file; a mutation on either fails
  exactly its own arm.

### Fixed

- **Validation errors keep their per-field structure now that cascor wraps 422 in its envelope**
  (defect-register `APD-CCLIENT-008`). `_handle_response` reads the structured list from
  `error.detail` when the envelope carries one, so `exc.detail` still receives
  `[{"type", "loc", "msg", ...}]` rather than a flattened prose summary.

  **This is the client half of a coordinated change**; the server half is juniper-cascor#610.
  cascor's API-09 migration declared itself complete while never registering a
  `RequestValidationError` handler, so Pydantic field-validation 422s kept returning a bare
  `{"detail": [...]}` while every other error returned the envelope. That drift is what this
  client's two-envelope sniff existed to absorb -- the row was filed against the client, but the
  defect was on the server. cascor now wraps 422, moving the list to `error.detail`.

  Without this change a client talking to a fixed cascor would take the envelope branch, read
  `error.message`, and silently lose which field failed -- the exact regression `juniper-data`
  recorded on `APD-DATA-013`. Mutation-tested: reverting to `error.message` fails 3 arms.

  The legacy top-level `detail` branch is **retained and now labelled a compatibility shim**, not a
  live shape: a current cascor never takes it, and it exists so this client keeps working against a
  pre-completion deployment. Two regression guards pin that preferring `detail` unconditionally would
  be wrong -- `HTTPException` routes carry `error.detail: None`, and a string `error.detail` is prose
  rather than structure; in both cases `error.message` must still win.

### Changed

- **Retry backoff is jittered — `backoff_jitter` is passed to urllib3's `Retry`** (defect-register
  `APD-ECO-002`). Without it, every client instance that tripped the same transient outage retried on
  an *identical* schedule, so a service that was already failing took a synchronised herd on each
  backoff step. urllib3 applies jitter as an **absolute additive term**
  (`backoff_value += random.random() * backoff_jitter`), not a proportional one, so the new
  `DEFAULT_BACKOFF_JITTER` is matched to `DEFAULT_BACKOFF_FACTOR` (0.5) — a full window of spread on
  the first retry, the step that carries the most callers. **No dependency floor moves**:
  `backoff_jitter` arrived in urllib3 2.0.0 and this package already pins `urllib3>=2.0.0`. Retry
  counts, allowed methods and the status forcelist are untouched, so retry *behaviour* is unchanged —
  only its timing is decorrelated. `tests/test_retry_policy.py` pins the constant's presence, its
  positivity (a `0.0` would silently restore the herd while leaving the call site looking correct),
  and — the decisive arm — that 200 sampled backoffs actually differ.

- **`create_network` is fully typed — the server's 14 `NetworkCreateRequest` fields as keyword-only
  `Optional` parameters, with `**extra` demoted to a loud forward-compat channel** (defect-register
  `APD-CCLIENT-011`). The old `**kwargs: Any` surface typed none of its 11 documented parameters,
  claimed three were "(required)" when the server defaults every field, still advertised
  `epochs_max` after it left the server's create surface — and its blind pass-through fed the
  server's silent-ignore behavior, where a typo'd hyperparameter vanishes without a trace (that is
  exactly how retired `epochs_max` senders keep "working"). Now: only parameters the caller sets are
  sent (server defaults stay authoritative); `init_output_weights` / `optimizer_type` /
  `activation_function_name` are deliberately `str` rather than duplicated Literals so a newer
  server's registry additions stay callable from an older client (the server 422s bad values);
  unknown keys still forward via `**extra` — canopy's dict-splat adapter keeps working unchanged —
  but now log a WARNING naming the keys. `FakeCascorClient.create_network` mirrors the signature
  exactly (pinned by a parity test); its stricter-than-server validation posture (requiring
  `input_size`/`output_size`/`learning_rate` that the real server defaults, and defaulting the
  retired `epochs_max` into its config) is an **observed divergence deliberately left unchanged**
  and recorded with the register close.

- **`auto_pong` is keyword-only on all three WS stream constructors** — `CascorTrainingStream`,
  `CascorControlStream`, and `FakeCascorTrainingStream` (defect-register `APD-CCLIENT-012`). A
  trailing positional-or-keyword boolean made `CascorTrainingStream("ws://h", None, None, False)`
  legal and unreadable, and any future parameter inserted before it would silently rebind the
  boolean. **Breaking only for positional calls reaching that slot**: an ecosystem census found no
  construction passing more than one positional argument and every `auto_pong` use already by
  keyword. The fake mirrors the boundary so consumer tests fail exactly as production would; a
  signature-pin test holds all three. The legacy `auto_pong=False` posture's missing removal date
  — the row's other half — is the deprecation-machinery question tracked by open `APD-ECO-007`.

### Added

- **`backoff_factor` is constructor-configurable** (defect-register `APD-CCLIENT-013`). The retry
  backoff was hardcoded to `DEFAULT_BACKOFF_FACTOR` at session build; both sibling clients expose
  it as a constructor parameter. Inserted in the sibling position (before `api_key`) — an
  ecosystem census found no call passing more than one positional argument, so nothing rebinds.

### Fixed

- **The HTTP adapter now sets `pool_connections` alongside `pool_maxsize`** (defect-register
  `APD-CCLIENT-009`). Both siblings set the pair explicitly (10/10); omitting one here left it on
  urllib3's default — silent sibling drift rather than a decision. New `DEFAULT_POOL_CONNECTIONS`
  constant; both knobs pinned by test.
- **mypy targets 3.12, matching `requires-python >=3.12`** (defect-register `APD-CCLIENT-007`).
  The strict gate was type-checking a Python this package refuses to install on. A new drift test
  pins `[tool.mypy] python_version` to the `requires-python` floor so the two cannot drift apart
  again.

- **A raising message listener no longer tears down the training stream** (defect-register
  `APD-CCLIENT-006`). `_dispatch` ran each registered callback bare while its neighbour
  `_dispatch_disconnect` — same file, same author — wrapped each in try/except; and because
  `_dispatch` runs inside `stream()` *before* the yield, one faulty `on_metrics`/`on_state`/…
  listener killed the whole iterator (and `listen()`), skipped every later listener for that
  message, and masked the fault as a stream failure. The guard is now ported: each callback is
  isolated, the fault is logged at ERROR with the message type (`logger.exception`, matching the
  disconnect path), subsequent listeners still run, and the message still reaches the stream's
  consumer. Same-file inconsistency class — nothing structural catches these; recorded in the
  register's §2.3 table.

- **The base URL is now normalised and validated — a hostless `base_url` fails at construction with the new `JuniperCascorConfigurationError`** (defect-register `APD-CCLIENT-005`). This was the only Juniper client with *neither* scheme defaulting *nor* host validation: `base_url.rstrip("/")` was the entire treatment, so a schemeless host, a `/v1`-suffixed base (which then produced a broken double-`/v1` `api_url`), or an empty/hostless value all passed silently and failed opaquely on the first request. `_normalize_url` — ported from the sibling clients, juniper-recurrence-client being the reference — now strips whitespace, defaults the `http://` scheme, rejects an empty host with the typed error, drops a trailing slash and strips a trailing `/v1`. Two hardenings beyond the sibling port, both from a confirmed review finding on this PR: scheme matching is **case-insensitive** (RFC 3986 — a case-sensitive check would re-prefix `HTTPS://host` into `http://HTTPS://host`, a silent TLS downgrade sending the API key over HTTP to hostname `https`), and the guard reads `parsed.hostname` rather than `netloc` (netloc accepts a userinfo-only `http://user:secret@` as truthy; hostname is `None` for it). The siblings carry the same two flaws and are being fixed to match. The new `JuniperCascorConfigurationError` completes the sibling exception alignment (both other clients already carry one) and subclasses `JuniperCascorClientError`, so a consumer catching the base still catches it. The WS stream classes (`CascorTrainingStream` / `CascorControlStream`) keep their separate `rstrip`-only treatment — the `ws://` scheme family needs its own defaulting rules and is deliberately out of this change's scope.
- **`JuniperCascorServiceUnavailableError` is reachable again — retry exhaustion now surfaces the typed error with its real status** (defect-register `APD-CCLIENT-002`). urllib3 defaults `raise_on_status` to `True`, so once the retries for a `status_forcelist` code ran out it raised `MaxRetryError`; requests surfaced that as `RetryError`, a plain `RequestException`, which `_request`'s generic handler flattened into `JuniperCascorClientError` **before** `_handle_response` could classify it. The 503 arm there — and therefore the `JuniperCascorServiceUnavailableError` type itself, which is publicly exported — was dead code in **every client built with retries**, i.e. every production client. Setting `raise_on_status=False` leaves the retrying itself completely unchanged and alters only the give-up path: the final response is returned rather than raised, so a 503 that outlives its retries now raises `JuniperCascorServiceUnavailableError` with `status_code=503`, and 429 / 502 / 504 carry their real status instead of `None`. Transport failures (refused connection, DNS, timeout) produce no response and are unaffected. **Non-breaking**: the typed error subclasses `JuniperCascorClientError`, so any consumer catching the base still catches it. Note for anyone auditing coverage: every pre-existing 503 test mounts `HTTPAdapter(max_retries=0)` first, which is why the dead branch went unnoticed — the coverage proved the branch worked under a configuration production never uses. The new arms use a retrying client.
- **Exceptions now carry `status_code`, `detail` and `response`** (defect-register `APD-CCLIENT-004`, which absorbed the retired `APD-CCLIENT-003`). `_handle_response` computed the status and then dropped it on four of its five branches, so a 400 and a 422 both raised `JuniperCascorValidationError(error_msg)` and were **byte-identical** — the only way to tell them apart was substring-matching the message. Those were one defect, not two: the branches were indistinguishable *because* the type carried no status. The base `JuniperCascorClientError.__init__` now accepts keyword-only `status_code` / `detail` / `response`, and every branch passes them. **Backward compatible**: the new parameters are keyword-only, so the 29 single-positional-message raises in `FakeCascorClient` and every consumer call site are unchanged, and locally raised errors (connection, timeout, retry-exhausted) simply report `status_code=None`.
- **A FastAPI 422 `detail` list is no longer surfaced as a Python repr.** `body.get("detail", ...)` returns a *list* of error objects for a 422, and that list was passed straight to the exception, so `str(exc)` was an unparseable repr. The structure is now attached to `exc.detail` **unmodified** while the message renders it as `body.input_size: Field required` via a new `_render_error_detail` helper. This is the same defect juniper-data-client tracks as `APD-DCLIENT-003`; it had never been recorded against this client.
- **`FakeCascorClient` mirrors the real status codes.** It claims full API parity, so a double raising the right type with `status_code=None` would let a consumer's test pass against behaviour production does not have. 404 for not-found, 409 for conflict, and 422 for the two validation sites (the real service validates those inputs with pydantic `Field(ge=1)` and `Query(ge=, le=)`, which FastAPI answers 422 rather than 400). Its one local-state error ("Client is closed") deliberately carries no status.
- **Exception context survives `pickle` and `copy`.** `BaseException.__reduce__` returns `(cls, args, self.__dict__)` whenever the instance dict is non-empty, so the keyword-only context is restored automatically — but only while `args` holds exactly the constructor's positional message, which is the invariant `test_context_survives_pickle_and_copy` pins (the failure mode flake8-bugbear's `B042` warns about). An interim `__reduce__` override that reproduced this default byte-for-byte was removed with the `APD-CCLIENT-010` cleanup below; its stated rationale — that the default rebuilds from `args` alone — was wrong, and the same correction has landed in juniper-service-core and juniper-data-client.

This is a port of the convention established in [juniper-data-client#158](https://github.com/pcalnon/juniper-data-client/pull/158). The three Juniper clients are separately released packages with no shared code, so nothing mechanical keeps them aligned; the alignment is a convention carried by each package's tests and AGENTS.md.

### Changed

- **Removed the redundant `pass` statements from the exception subclasses** (defect-register `APD-CCLIENT-010`). The register filed eight; `APD-CCLIENT-004`'s fix had already given the base class a real body, so **seven** remained. A docstring is a complete class body; the `pass` lines were dead weight. No behavioural change; the whole suite passes untouched.

## [0.7.0] - 2026-07-11

### Added

- **CL1 — WebSocket heartbeat handling (root fix for the 40s control-WS kill).** The cascor server (C3 contract; heartbeat shipped in cascor#133) sends an application-level `{"type":"ping","ts":<float>}` on both `/ws/training` and `/ws/control` every `ws_heartbeat_interval_sec` (default 30s) and closes the connection when the client sends nothing within `ws_heartbeat_pong_timeout_sec` (default 10s) of a ping. This client implemented no ping handling at all: on `/ws/control` nothing even read the socket until the first `set_params` (the recv loop started lazily), so an idle control connection was killed 40s after connect — the 2026-07-10 incident, where canopy's control WS died at 18:17:03 and every hot-parameter push for the next 12+ hours burned its WS window against the half-open corpse before falling back to REST. Both stream classes now answer pings automatically with `{"type":"pong"}` (`auto_pong: bool = True` constructor kwarg on `CascorTrainingStream` and `CascorControlStream`; `auto_pong=False` restores the legacy yield-the-ping behaviour for consumers that reply themselves), and `CascorControlStream.connect()` starts the background recv loop eagerly so pings are answered from the moment the connection exists (`command()` consequently always routes through the `command_id` correlation path after `connect()`; the direct-recv path remains as a fallback and now skips/answers pings so a ping can never be returned as a command response). New constants `WS_MSG_TYPE_PING` / `WS_MSG_TYPE_PONG`.
- **Liveness surface for consumers (the seam canopy's supervisor hardening consumes).** Both stream classes (and `FakeCascorTrainingStream`) expose: `is_connected` (property — underlying `websockets` protocol state is OPEN; detects processed closes, which the historical `_ws is not None` idiom could not), `is_alive(window_sec=DEFAULT_LIVENESS_WINDOW_SEC)` (connected AND at least one inbound frame within the window — detects half-open sockets that `is_connected` alone cannot; default window 90s = three missed 30s server heartbeats), `last_frame_at` (wall-clock epoch seconds of the last inbound frame), and `pongs_sent` (count of automatic pong replies). A successful `connect()` counts as the first liveness evidence.

### Changed

- **`ping` is a recognized transport frame — no more per-30s `unrecognized_ws_frame` spam.** Heartbeat pings are consumed by the transport layer before envelope validation, so they no longer emit `juniper_cascor_client_unrecognized_ws_frame` warnings (~2,400 of them in the 2026-07-10 session, mirrored again by canopy's relay) nor increment the unrecognized-frame counter.
- **Unrecognized-frame warnings now carry the frame type in the message text.** `record_unrecognized_frame` logs `juniper_cascor_client_unrecognized_ws_frame type=<type> endpoint=<endpoint>` instead of the bare constant string whose diagnostic payload lived only in the `extra` dict (dropped by standard `%(message)s` formatters — the incident's thousands of zero-diagnostic-value warnings). The stable prefix is preserved for log-grep continuity; the Prometheus counter and `extra` keys are unchanged.
- **`FakeCascorTrainingStream` parity (the #91 lesson):** accepts `auto_pong`, consumes injected `{"type":"ping"}` frames (counted in `pongs_sent`, never yielded) under the default posture, yields them under `auto_pong=False`, and implements the full liveness surface (`is_connected` / `is_alive` / `last_frame_at` / `pongs_sent`).
- `__init__.__version__` corrected to match `[project].version` (had been left at `0.4.0` while the package shipped 0.5.x/0.6.x).

### Compatibility

- New client against old server (heartbeat present since cascor#133): pongs are answered as the server always expected — strictly better. Old client against new server (cascor C3): unchanged failure mode for idle control connections (closed after the pong window; C3 makes the close observable with a valid close code + reason instead of a silent half-open), and canopy's relay keeps `/ws/training` alive via its own pong workaround, which the new client makes redundant (the relay simply never sees pings anymore). No wire-format or public-API removals; pure-additive surfaces.

## [0.6.0] - 2026-07-11

### Added

- **`FakeCascorClient._request` — in-memory parity for the real client's private escape hatch.** juniper-canopy's `CascorServiceAdapter` drives the cascor dataset-staging and experimental-functions endpoints through `JuniperCascorClient._request` (the "public-but-private" escape hatch documented in cascor #242 — the client still has no first-class methods for those routes), and canopy #438 put that path on canopy's trivial-case Start-Training flow (`_ensure_first_start_dataset` → `get_pending_dataset()` / `stage_dataset()`). The fake previously did not implement `_request` at all, so any canopy test driving `ServiceBackend.start_training()` against `FakeCascorClient` crashed with `AttributeError: 'FakeCascorClient' object has no attribute '_request'` the moment the real `juniper-cascor-client` package was installed (canopy's CI conftest stub masks the gap — its `juniper_cascor_client.testing` importorskip means the affected tests only run against the real package, i.e. on developer machines). The new method mirrors the real signature (`method, path, json=None, params=None`; signature parity pinned by a new conformance test) and answers the five routes canopy drives, with response `data` shapes copied from the cascor server handlers (`src/api/routes/training.py` + `admin.py`): `POST /training/dataset` (stage; empty body clears, `{"status": "staged"|"cleared", "config": ...}`), `DELETE /training/dataset` (`{"status": "cleared", "discarded": <prior-or-null>}`), `GET /training/dataset/pending` (`{"pending": <cfg-or-null>}`), and `GET`/`POST /admin/experimental_functions` (`{"enabled": bool}` / `{"experimental_functions_enabled": bool}`). Unknown routes raise `JuniperCascorNotFoundError` exactly like a real 404; closed-client and `error_prone`-scenario injection behave like every other fake method. `FakeCascorClient.start_training` now also **consumes** any staged config on a successful start, mirroring cascor #396's consume-on-start so the canopy pending banner clears after a start. New regression class `tests/test_fake_client.py::TestPrivateRequestEscapeHatch` (9 tests) pins the signature parity, all five route round-trips, the 404 behaviour, closed-client refusal, and the consume-on-start. Pure-additive: no existing public API or wire shape is touched.

## [0.5.0] - 2026-05-29

### Added

- **E.2 PR-2-A (juniper-ml STACK_REGRESSION_CORRECTIONS_2026-05-27 §E.2)**: `CascorTrainingStream` and `CascorControlStream` now accept an `origin: Optional[str] = None` keyword argument that is forwarded to `websockets.connect(..., origin=…)` when set. Pure-additive change: callers that do not pass `origin=` (and do not set the new `JUNIPER_CASCOR_WS_ORIGIN` env var) preserve the pre-0.5.0 behaviour of sending no Origin header — backwards-compatible for every existing CLI / test / direct-Python consumer. The new `WS_ORIGIN_ENV_VAR: str = "JUNIPER_CASCOR_WS_ORIGIN"` constant in `juniper_cascor_client/constants.py` documents the env-var alias. Required for server-to-server callers against cascor's `/ws/control` because juniper-cascor#129 makes the endpoint fail-closed against missing Origin: prior to this release, juniper-canopy's `ControlStreamSupervisor` could not connect from inside docker compose (canopy hostname's WS upgrade carries no Origin → cascor 403 → 30-second reconnect loop). The juniper-canopy companion PR threads the configured Origin (default `http://juniper-canopy:8050`) through `CascorServiceAdapter` to `CascorControlStream(origin=…)`. New regression at `tests/test_ws_client.py` (4 tests across both stream classes) pins both branches: `connect(..., origin=…)` is forwarded only when the Origin attribute is set, and the kwarg is omitted otherwise so the M2M-no-Origin default that worker / training paths rely on is preserved.

- **API-06 / XREPO-17** (v7 roadmap §7985 / §14322): new `CascorTrainingStream.on_candidate_progress(callback)` callback registration method (and matching `FakeCascorTrainingStream.on_candidate_progress(callback)` in the `juniper_cascor_client.testing` subpackage) closes a previously-silent gap where the cascor server's `candidate_progress` WS frames (broadcast during the candidate-training phase via `juniper-cascor/src/api/websocket/messages.py:165` `create_candidate_progress_message`, wrapping the shared `CandidateProgressEnvelope` already in `juniper-cascor-protocol`) could pass through the client's dispatch loop without surfacing to a consumer-registered handler. Pure-additive change: new public method + new module-level `WS_MSG_TYPE_CANDIDATE_PROGRESS: str = "candidate_progress"` constant in `juniper_cascor_client/constants.py`. No existing public API or wire-format is touched; consumers that did not previously care about candidate-training progress are unaffected. The fake helper uses the bare string literal `"candidate_progress"` to match the existing `on_metrics` / `on_event` etc. convention in `fake_ws_client.py` (the real `ws_client.py` uses the new constant for symmetry with the other registration methods). New regression at `tests/test_fake_ws_client.py::TestFakeCascorTrainingStream::test_on_candidate_progress_callback` exercises the registration + dispatch path end-to-end with a representative payload `{"candidate_id": 0, "epoch": 5, "correlation": 0.42}`. Tracks API-06 in the v7 outstanding-development roadmap §21 (cross-references XREPO-17 in §11).

## [0.4.0] - 2026-05-23

### Changed (potentially breaking)

- **METRICS-MON R2.2.4 / seed-05**: `juniper-cascor-client` now consumes the shared `juniper-cascor-protocol>=0.1.0` package as a runtime dependency and validates every inbound `/ws/training` and `/ws/control` frame against its canonical Pydantic envelope models. Validation is purely **observational** — the wire-format dict is yielded / passed to callbacks unchanged so the public `stream()`, `on_metrics`, `on_state`, `on_topology`, `on_cascade_add`, `on_event`, `command()`, and `set_params()` APIs are byte-compatible with the pre-migration behaviour. **Python floor bumped to `>=3.12`** (was `>=3.11`) to match the cascor server and the protocol package; `Programming Language :: Python :: 3.11` classifier removed. **New observability surface**: when an inbound frame fails validation (unknown `type`, missing required field, wrong field types) the client emits a structured WARNING log line `juniper_cascor_client_unrecognized_ws_frame` with `type` and `endpoint` extra keys, and (when `juniper-cascor-client[observability]` is installed) increments a new Prometheus counter `juniper_cascor_client_unrecognized_ws_frames_total{type, endpoint}`. The `type` label is bounded by the same R1.1 cardinality discipline the protocol package uses (first 16 distinct unknowns tracked verbatim per process; subsequent unknowns collapse to `"_unmatched"`) so an attacker emitting many distinct frame types cannot inflate label cardinality. New optional extra `[observability]` adds `prometheus-client>=0.20.0`. New chaos-coverage test suite at `tests/test_inbound_validation.py` (10+ tests) pinning: known envelopes pass through unchanged, unknown types are observed but not rejected, malformed payloads do not crash `stream()`, the cardinality bound holds, and the counter degrades gracefully when `prometheus-client` is not installed. See [`notes/code-review/METRICS_MONITORING_R2.2_WS_FRAME_SCHEMA_DESIGN_2026-04-29.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/code-review/METRICS_MONITORING_R2.2_WS_FRAME_SCHEMA_DESIGN_2026-04-29.md) in juniper-ml.

### Added

- **API-09 PR 2 of 3 (juniper-cascor-client side)**: explicit regression coverage at `tests/test_api_09_dual_shape_error_parser.py` (23 tests) pinning `_handle_response` against all three error-response shapes cascor can emit during the API-09 deprecation window: (1) **legacy** `{"detail": "..."}` (pre-PR-1 cascor, FastAPI default `HTTPException` shape), (2) **envelope-only** `{"status":"error","error":{"code","message","detail"},"meta":{...}}` (post-PR-3 cascor; also pre-PR-1 `ValueError`/`Exception` handler output), and (3) **dual-shape** envelope + top-level `"detail"` alias (cascor PR 1 ↔ PR 3 deprecation-window output). Investigation while preparing this PR surfaced that the dual-shape parser was **already shipped** in `client.py:_handle_response` on 2026-02-21 (commit b0a636a3), months before the API-09 migration design doc was written — the existing `if isinstance(body.get("error"), dict): ... else: body.get("detail", ...)` logic correctly prefers `error.message` over the top-level `detail` alias when both are present, so juniper-cascor-client requires **zero production code changes** for the API-09 migration. The new tests pin all three shape paths (including a divergent-mock case that asserts `error.message` wins over a deliberately-different `detail` alias, and defensive fallback paths for non-JSON `text/html` bodies and JSON bodies missing both keys) so a future refactor of `_handle_response` cannot silently drop one of the branches. The juniper-ml `[clients]` extra pin (`juniper-cascor-client>=0.3.0`) already admits the current `0.4.0` release so no pin bump is required. Tracks API-09 in the v7 outstanding-development roadmap §21; design doc at `juniper-cascor/notes/API_09_ERROR_ENVELOPE_MIGRATION_DESIGN_2026-05-21.md`; cascor PR 1 = #293, cascor PR 3 (alias drop) ships after this.

- **`util/test_agents_md_version_drift.py`** -- portable port of juniper-ml's lint test pinning `AGENTS.md`'s `**Version**:` header to `pyproject.toml`'s `[project].version`. Catches the failure class where a `pyproject.toml` bump leaves the agent-facing contract stale. Bundled with a one-line `AGENTS.md` bump 0.3.0 → 0.4.0 to clear the pre-existing drift this lint surfaces. Wired into the CI tests job next to the existing `test_workflow_script_paths.py` lint.

- Track 5B — CI-04: Weekly security-scan workflow (`.github/workflows/security-scan.yml`) running Bandit (SAST, SARIF output) and `pip-audit --strict --desc on` against the package on a Monday-06:00-UTC cron plus `workflow_dispatch`. Mirrors the established pattern in `juniper-cascor-worker`. Reports upload as a 30-day-retention artifact.
- Track 5B — CI-05: Lockfile update workflow (`.github/workflows/lockfile-update.yml`) that regenerates `requirements.lock` via `uv pip compile pyproject.toml --extra dev --upgrade` whenever Dependabot pushes to `dependabot/pip/**`, and commits the result back. Uses `CROSS_REPO_DISPATCH_TOKEN` so the push re-triggers CI. Mirrors the pattern in `juniper-canopy`, `juniper-data`, and `juniper-cascor`. Workflow is dormant until the first Dependabot push — `juniper-cascor-client` does not currently ship a `requirements.lock`, and the first run will create one.
- Serena code agent integration configuration (`.serena/project.yml`)
- New `juniper_cascor_client/constants.py` module centralizing wire-protocol identifiers (`API_KEY_*`, `API_VERSION_*`), the full set of REST `ENDPOINT_*` paths, WebSocket `WS_*_PATH` constants, `DEFAULT_*` constructor defaults, `MSG_TYPE_*` discriminators bit-identical to the cascor server's `MessageType` enum, and scenario/fake-client defaults.
- `tests/test_retry_policy.py`: new regression suite asserting that the retryable-status list covers 429/502/503/504 in both directions (canonical transients retried, non-transient 4xx/5xx not) and that the `Retry` adapter mounted on the session reflects these constants end-to-end.

### Changed

- `client.py`, `ws_client.py`, `testing/fake_client.py`, and `testing/scenarios.py` now import from `juniper_cascor_client.constants` instead of embedding inline literals (~200 replacements total across REST + WebSocket + testing utilities).
- `MSG_TYPE_*` values are guaranteed to remain bit-identical to the `juniper-cascor` server's `MessageType(StrEnum)` and to the matching constants in `juniper-cascor-worker` — verified by Wave 5 cross-repo alignment checks.
- `AGENTS.md` gained a new "Constants" section documenting the categories, server alignment, and contribution rules.
- **XREPO-02 / CC-02 (Phase 4B)**: `RETRYABLE_STATUS_CODES` now includes 429 (Too Many Requests) and 503 (Service Unavailable) in addition to the existing 502/504. 503 is the canonical transient error emitted by the cascor service during restart / deploy; prior behavior surfaced deploy windows as hard failures at the caller. 429 is retried so clients back off cleanly when the server applies rate limits.

### Notes

- No public API changes; constructor signatures, method behavior, and exception types are unchanged.
- All 223 existing tests pass without modification; pre-commit (22 hooks) is clean.

## [0.3.0] - 2026-03-30

### Added

- `list_workers()`, `get_worker()`, `get_worker_stats()` client methods for remote worker monitoring
- `list_snapshots()`, `get_snapshot()`, `save_snapshot()`, `load_snapshot()` client methods for snapshot management
- `get_dataset_data()` client method for dataset array retrieval (`GET /v1/dataset/data`)
- `generate_dataset_inputs()` and `generate_dataset_targets()` functions in scenarios for synthetic dataset creation
- FakeCascorClient support for worker, snapshot, and dataset data methods with scenario-driven behavior
- Comprehensive AGENTS.md with architecture, directory layout, CI/CD, linting, and test documentation

### Fixed

- Aligned FakeCascorClient response format with real cascor `ResponseEnvelope` (`_success_envelope()` wrapping, nested `state_machine/monitor/training_state` structure, bare list for metrics history, flat param dict)

### Changed

- Bumped github/codeql-action from 4.33.0 to 4.34.1 (Dependabot)
- Bumped actions/cache from 5.0.3 to 5.0.4 (Dependabot)
- Bumped github/codeql-action from 4.34.1 to 4.35.1 (Dependabot)

## [0.2.0] - 2026-03-21

### Added

- `update_params()` client method for runtime training parameter updates (`PATCH /v1/training/params`)
- `_patch()` helper method and `PATCH` in `ALLOWED_METHODS` set on `JuniperCascorClient`
- FakeCascorClient `update_params()` with scenario-aware state updates
- Tests for `update_params()` on both real client (responses mock) and fake client
- FakeCascorClient and FakeCascorTrainingStream testing submodule (`juniper_cascor_client.testing`)
- `JUNIPER_CASCOR_API_KEY` environment variable fallback for API key
- Cross-repo CI dispatch to juniper-canopy on push to main
- Dependabot configuration for automated dependency updates (weekly)
- CODEOWNERS file for PR review routing
- SOPS config (`.sops.yaml`) and `.env.example` for secrets management
- CHANGELOG.md following Keep a Changelog format
- Documentation suite: DOCUMENTATION_OVERVIEW.md, QUICK_START.md, REFERENCE.md
- Developer cheatsheet (`docs/DEVELOPER_CHEATSHEET.md`)
- AGENTS.md with thread handoff and worktree procedures
- Pre-commit hooks configuration with markdownlint, shellcheck, flake8, bandit, yamllint
- Ecosystem compatibility matrix in README

### Fixed

- Aligned FakeCascorClient decision boundary format with real API (`grid_x`/`grid_y` as 2D meshgrid arrays, integer argmax class indices instead of 1D arrays with continuous sigmoid values)
- Incorrect file references in AGENTS.md key files table

### Changed

- SHA-pinned all GitHub Actions to immutable commit hashes
- Expanded `.gitignore` to cover all `.env` variants and `.env.secrets`
- Set line length to 512 for all linters (black, isort, flake8) per Juniper ecosystem standard
- Removed py314 from black target versions
- Propagated V2 worktree cleanup procedure (CWD-trap bug fix)
- Bumped actions/checkout from 4 to 6 (Dependabot)
- Bumped actions/setup-python from 5 to 6 (Dependabot)
- Bumped actions/upload-artifact from 4 to 6 (Dependabot)
- Bumped actions/cache from 4.2.3 to 5.0.3 (Dependabot)
- Bumped github/codeql-action from 3.28.0 to 4.33.0 (Dependabot)

## [0.1.0] - 2026-02-22

### Added

- Initial release of `juniper-cascor-client`
- `CascorClient` class with REST API coverage for juniper-cascor
- `CascorTrainingStream` WebSocket client for real-time training monitoring
- `CascorClientError` exception hierarchy
- Type annotations with `py.typed` marker
- Unit test suite with 80%+ coverage
- CI/CD pipeline with GitHub Actions
- PyPI and TestPyPI trusted publishing
- README with API documentation and examples
- Ecosystem compatibility matrix
- AGENTS.md with thread handoff and worktree procedures

[Unreleased]: https://github.com/pcalnon/juniper-cascor-client/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/pcalnon/juniper-cascor-client/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/pcalnon/juniper-cascor-client/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/pcalnon/juniper-cascor-client/releases/tag/v0.1.0
