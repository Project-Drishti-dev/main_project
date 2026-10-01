# DRISHTI Project -- Handover

**Updated:** October 1, 2026 -- after task 11.4. Part 11 has one write and
three reads: `POST /api/screenings` creates, `GET /api/screenings` answers one
filtered page, and `GET /api/screenings/{id}` answers the whole stored
screening.  Every refusal on all three is held to one envelope body.
`check-all.ps1` exits 0: 4104 backend tests (was 4084), 45 frontend, build.

**The pytest temp-root `PermissionError` is still uncured and fired again**
during this task -- 100% dots, no `F`, then a teardown traceback replacing the
summary line, and exit 1.  Not a test failure.
`[System.IO.Directory]::Delete('C:\Users\Ash-SSD\AppData\Local\Temp\pytest-of-Ash-SSD\pytest-current')`
(escalation, no recursive flag) cleared it and the rerun passed all three
stages.  `--basetemp=.\.pytest-tmp` inside the workspace also gives a real
summary and a zero exit, and is what the iteration runs used.

**Workspace:** `D:\sih\main_project` -- **Frontend:** `D:\sih\main_project\frontend`

## Resume from here

### Last Completed Task

**11.4** -- One error envelope, held by a test. Recorded as `D74`.

- **`tests/api/test_error_envelope_api.py` drives all thirteen refusals** the
  three new endpoints can answer -- eight on the create, four on the list,
  two on the read -- through the real app and asserts one body on every one:
  `{"error"}` at the top level, exactly `{"code", "message"}` inside it, both
  fields non-empty, and the code spelled `UPPER_SNAKE`.  The 404 the task names
  is compared against `/api/analyze`'s own body rather than a literal, so
  "the existing envelope" means the one that is actually there.
- **`app/main.py` gains a third handler, for `Exception`.**  The two `GET`
  routes have no catch-all, so a fault on a read was answered by Starlette's
  `text/plain` `Internal Server Error` -- a body no client can parse.  It now
  answers 500 `INTERNAL_ERROR`, the traceback to the log and nothing in the
  body.  The route-level catches still win: `SCREENING_FAILED` and
  `SCREENING_UNREADABLE` are unchanged.  Removing the handler was checked to
  turn that one case red with `content-type: text/plain`.
- **Two contract walks**, over `app.openapi()`: every failure the three routes
  declare resolves to `ErrorResponse`, and no second error schema exists in
  the document at all -- which is why `HTTPValidationError` is absent, since
  each route declares its own 422.
- 20 new cases.  A router miss (unknown path, wrong method) is still FastAPI's
  `{"detail": ...}`: it is not an endpoint refusal, and overriding the
  framework's own handler is not something Part 11 asked for.

### Current State & Key Decisions

**The HTTP surface is a package.**  `app/api/` holds one router per resource
and the session dependency they share; `app/main.py` keeps the app, the error
envelope, `/health` and `/api/analyze`, and mounts the routers.  `audit_id`
is the `analysis_completed` event's id, and the cascade runs synchronously in
`run_in_threadpool` before the answer (`D71`).  Both `GET` routes are plain
`def`, so FastAPI reaches them in a threadpool; the only `async def` route is
the one that awaits an upload.

**A statement belongs to the repository.**  Every read of `screenings` is a
method there -- `get`, `list`, `list_by_band`, `list_by_date_range`,
`list_by_document_type`, `list_matching` -- and each carries the one
`deleted_at` rule, the one `created_at`-then-`id` order and, for a page, the
count of the rows that matched.  A route that composed a query itself would
be a second spelling of all three (`D72`, `D73`).

**A stored result is read, never re-scored.**  Every number in
`GET /api/screenings/{id}`, and every column in a page row, is the row's own;
the only derived numbers anywhere are the contributions, a pure function of
the stored flags and the row's own ruleset (`D72`, `D73`).

**The upload's rules are spelled once, in `app/analysis.py`,** and both
endpoints reach them.  A second copy of the caps or the mode vocabulary would
answer a bad upload two ways; 11.9 re-tests it.

**One refusal body, on every endpoint.**  `{"error": {"code", "message"}}` is
built in `app/main.py` and nowhere else, by three handlers: `APIError`,
`RequestValidationError`, and `Exception` for a fault no route caught -- the
two `GET` routes have no catch-all of their own, so the app answers on their
behalf with a 500 `INTERNAL_ERROR` and nothing in the body.  A route that
catches its own fault still names it.  13 refusals and the two 500s are held
to the shape by `tests/api/test_error_envelope_api.py`, and a contract walk
fails if a new route declares any model but `ErrorResponse` (`D74`).

**A trail reads in the order a reader meets it:** `screening_created`, one
`tier_completed` per tier that ran, `analysis_completed` (which names the
tiers in `tiers_run`), then any `override_recorded` events after it.
`emit` is its only writer and `app/audit/trail.py` the only reader.

**A band names no outcome anywhere in the service, and the officer's three
choices are spelled in exactly one module.**  Both are held by walks over the
source rather than by prose, so a second spelling or a band-keyed table fails
a test rather than a review.  Every event's `actor` is the configured station
label (10.7), never a person, a session or a credential.

**The hashed record is the stored row's four columns plus its salt**, so
anything added to a payload from 10.3 on lands inside the record for free, in
the writer and in the verifier together.  A score in a payload must be text or
a scaled integer, and no payload carries a `float` at all: `D48` refuses one
and `emit` refuses the row.

**The `Screening` result columns are written by whoever ran the cascade**,
and `ScreeningRepository` writes no result at all -- the flow merges the row
it created and fills them in.

**Part 9 is complete and Gate 9 is met.** Nine modules in `app/ledger/`.
**Part 8 storage.** `Base`, `Screening`, `AuditEvent` (ten columns) and
`LedgerEntry` in `models.py`; an event's `screening_id` is a plain `Uuid` with
no foreign key, deliberately. **Part 7 is complete and Gate 7 is met.**
`D21`-`D35` hold that an unweighted id and an unmeasured value are **refused
rather than scored as zero**.

### Known Issues / Blockers

- **A router miss is not in the envelope.**  An unknown path answers FastAPI's
  `{"detail": "Not Found"}` and a wrong method answers `{"detail": ...}` with
  a 405, because those are the framework's own handler rather than ours.  No
  endpoint raises them on purpose, and nothing in Part 11 asks for it, so
  11.4 left them alone; overriding `StarletteHTTPException` is a decision, not
  a task (`D74`).
- **A `created_at` read back from SQLite carries no offset** (`D36`), so the
  instant the list prints cannot be fed straight back into `created_after` --
  a 422 by design, since a naive bound is two instants on two backends.  11.2's
  answer has the same shape; one shared UTC-labelling helper for both
  endpoints is 24.1's or 11.12's call, not a second spelling here.
- **The rows nothing has scored cannot be band-filtered.**  Their `band` is
  `None`, and `None` on this read is "no band filter"; an `unscored` chip
  would be the vocabulary 7.10's walk exists to catch, and what 24.7's pending
  filter is called is 24.3's decision.
- **The list has no sort parameter** and no `mode` column to sort on: 11.1
  does not store `mode`, so 24.2's seven-column table has one column nothing
  answers.  24.1 owns which column goes.
- **A ruleset bump makes old rows unreadable.**  The weights that produced a
  stored score are not kept, so once `v2.yaml` ships a row stamped `0.1.0` is
  refused rather than answered with numbers from another file.  Storing the
  weightset *name*, or a weight per finding, is a schema decision nobody has
  taken, and 8.4's suite holds the row to sixteen columns.
- **`GET /api/screenings/{id}` carries no verification status.**  9.17 answers
  `unknown` for any event no batch has claimed and nothing anchors one outside
  tests, so a field there could only ever say `unknown`.  18.7 is where that
  answer belongs (`D72`).
- **`record_override` still has no caller.**  18.1's endpoint, 18.2's
  validation error for a `reject` on a `low` band without `override: true`,
  and 18.3's `decision_recorded` event are what put it in the trail; the rule
  is already the one 18.2 needs.
- **The request is synchronous and has no job behind it.**  ROADMAP B8.1's
  "analysis continues" is not implemented: there is no job table, worker or
  queue, so the answer waits for the cascade rather than arriving before it.
- **No reference date is injected over HTTP**, so the route passes `None` and
  a DOB century stays unasked (5.8's honest "no day was injected").  A
  production source for the day is still owed.
- **The trail has exactly one read seam.**  `app/audit/trail.py` answers one
  question; 18.7 (`/api/audit/{audit_id}/verify`) and 24.8 (the audit view)
  grow it, and no `AuditEventRepository` exists.
- **The plan holds one tier**, so a real cascade is one tier deep and the
  stop is only exercised by a stub.  Parts 12 and 15 add a name and a runner
  to `_TIER_RUNNERS` and nothing else.
- **`model_versions` is `None` in practice**, and `mode`/`quality` stay
  `None` on a screening the API creates: Tier 1 and Tier 2 do not exist, and
  14.3 is what runs the quality gate as stage 0.
- **`cryptography` is still a dev dependency only**, so
  `app.ledger.signing` will not import in a production image until 26.1
  promotes it, and `app.ledger.anchoring` imports it transitively.  Nothing
  checks an entry's signature.
- **`tasks.md` marks 6.3 `- [x]` and there is no date-flag code** -- do not
  read Part 6 as five-sixths done. **4.7 is `- [ ] [BLOCKED]`** with
  production code written and zero tests of its own.
- **Unchanged from earlier parts**: nothing turns cells into characters, so
  `run_tier0` measures and the caller hands over a parsed document; no list
  can be asked about an identity end to end; three horizon gaps have no
  source behind them; 14.3 has no home.

### Immediate Next Step

**11.5** -- Add request-id middleware that stamps every request and returns
the id in a response header, with a test.
Verify: the new test passes.

Carry in:

- 11.6's structured JSON logging wants the id 11.5 stamps, and 26.8's
  correlation id wants the same value on the screening row -- so take it from
  an inbound header if one is offered rather than always minting a new one.
- The envelope is built in three handlers in `app/main.py` and nowhere else.
  A request id belongs on every answer, refusals included, so 11.5 is a
  middleware rather than a fourth handler.
- `DELETE /api/screenings/{id}` is B8.5 and 24.5's confirm-then-delete; the
  repository's `soft_delete` is the only writer, and 8.15's rule is that a
  deleted row is answered by no read.
