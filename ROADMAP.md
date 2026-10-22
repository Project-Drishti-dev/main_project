# DRISHTI — Build Roadmap

**Created:** September 30, 2026
**Scope:** Turn the current image-quality prototype into the system described in
`lorebook/abstract.txt`.
**Method:** Every task is a slice one agent (or one person) can finish and
verify in isolation. Tasks are ordered so that each one only depends on
earlier ones.

**Execution:** the atomized, per-task checklist is `tasks.md`. This file is the
strategy behind it.

**Repository safety:** never commit, push, or otherwise write to git history
or the remote unless the user explicitly asks in that turn. No `git add`,
`commit`, `push`, `merge`, `reset`, `checkout --`, `clean`, or `stash`, and no
deploys. Read-only git (`status`, `diff`, `log`, `show`) is fine. If the tree
is already dirty, leave it dirty. See `tasks.md` for the full list.

---

## 1. Verified starting point

Checked on September 30, 2026, not taken on trust from `handover.md`.

**Working tree is CLEAN**, on branch `ag/experimental-updates`, HEAD
`2b779e5 Feat(Frontend): Added more UI pages, Warn(Overall): Uses new automated ai models`.
The handover's "uncommitted tree" note is stale — the September 30 page work was
committed.

**What exists**

- `frontend/` — 6 static UX4G pages (`home`/`index`, `screenings`, `settings`,
  `guide`, `about`, `profile`), vanilla HTML/CSS/JS, `ux4g-web-components@2.1.0`
  loaded from local `node_modules`. Builds to `dist/` via `build.cjs`.
  **45/45 node tests pass** (verified this session).
- `backend/` — FastAPI on Cloud Run. `GET /health`, `POST /api/analyze`
  returning the 9 image-quality modules. 13 pytest tests. No database, no auth,
  no rate limiter, no image persistence.

**Two documentation defects to fix first**

- Root `README.md` says the backend "is not deployed or connected to the
  frontend yet". It has been deployed and wired since September 25.
- `handover.md` "Git state" section describes an uncommitted tree. It is committed.

**What the lorebook describes that does not exist yet**

Tier 0 (MRZ/ICAO 9303, date rules, watchlist), Tier 1 (OCR-to-MRZ, barcode,
template, face + PAD), Tier 2 (tamper, ELA/noise/copy-move, stamps, morph,
deepfake, anomaly), cross-document checks, the history layer, the weighted risk
engine with Low/Review/High bands, evidence flags with document locations, the
LLM summary plus its code verifier, Merkle-batched audit anchoring, officer
decisions and overrides, screening persistence, and the officer dashboard.

**The gap in one line:** the prototype answers *"is this photo good enough?"*;
the lorebook requires *"what is wrong, where on the document, how risky, and
what did the officer decide — provably."*

---

## 2. Decisions to lock before writing code

Each of these is a fork. The recommendation is what the rest of this roadmap
assumes. Changing one means editing the tasks that depend on it.

| # | Question | Recommendation | Why |
|---|---|---|---|
| D1 | Lorebook says React + Tailwind; repo is vanilla UX4G | **Stay vanilla UX4G** | UX4G is the government mandate, 6 pages + 45 tests already exist, handover explicitly rules out a framework migration. A rewrite costs ~2 days and buys nothing a judge can see. |
| D2 | Lorebook has officer authentication; the mock login was removed after a Cloudflare phishing interstitial | **Build real auth on the backend first. Add any sign-in UI only after it exists, and only on a separate operator route.** | Mock credential forms are what triggered the interstitial. Real auth with argon2id + JWT is a different category of thing. Never re-add a credential form that does not talk to a real auth backend. |
| D3 | Lorebook says PostgreSQL | **SQLite first, behind a repository interface, Postgres-compatible URL from day one** | Zero-setup demo, and switching is a `DATABASE_URL` change plus one Alembic migration. Judges run your code; make it run with no Docker. |
| D4 | Lorebook says Hyperledger Fabric | **Local append-only ledger (SQLite) behind a `Ledger` interface; Merkle batching and proofs are the demoable part** | Fabric is a 3-container deployment problem that will eat a demo day. The *idea* being judged is "hashes only, Merkle-batched, independently verifiable". Prove that; stub Fabric behind the same interface. |
| D5 | Tier 2 needs GPU models you cannot train in a hackathon | **Interface + honest heuristic stand-ins, clearly labelled** | `abstract.txt` says "No accuracy figures are claimed." Keep that honesty. A stand-in that moves the score and is labelled a stand-in beats a fake model name. |
| D6 | `home.css` doubles as the app shell stylesheet; sidebar markup is duplicated across 6 pages | **Extract the shell in `build.cjs` before adding 3 more pages** | 6 duplicated shells is debt; 9 is a bug generator. Cheap to fix now, painful later. |
| D7 | Public demo is unauthenticated and Cloud Run has no rate limiter | **Add rate limiting and an explicit `PUBLIC_DEMO` mode now, before the endpoints get expensive** | Once Tier 1/2 model loading lands, an open endpoint is a denial-of-wallet. |

---

## 3. Sequencing rules (do not violate)

1. **No evidence flag without a region.** If a flag cannot be located on the
   document, it is not a DRISHTI flag. MRZ region detection (B1.10) therefore
   lands before most Tier 1 work.
2. **No risk band before the flag schema exists** (B2.1). Everything aggregates
   into `EvidenceFlag`.
3. **No summary before flags.** The verifier (B7.3) checks a summary against
   flag data; there is no flag data to check against until B2.1.
4. **No decision UI before the decision endpoint** (B8.4), and no decision
   endpoint before the audit event (B3.8), and no audit event before the hash +
   Merkle layer (B3.4, B3.5).
5. **No sign-in UI before backend auth** (D2). This is a hard gate, not a
   preference.
6. **UX4G preflight before any new page** (F22): read `Design.md`, list
   components with exact variant and size, then code. The pinned 2.1.0 README
   is unreliable — grep the shipped `ux4g.css` and `design-system.js` for any
   class before using it.

---

## 4. Tasks

Legend — **B** backend, **F** frontend, **O** ops/infra, **V** validation,
**X** cross-cutting. Effort: `S` ≈ 1–2 h, `M` ≈ half a day, `L` ≈ 1–2 days.

### Phase 0 — Ground the repo (X0)

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| X0.1 | Correct the stale "not deployed / not connected" claim in root `README.md`; correct the "uncommitted tree" claim in `handover.md` | `README.md`, `handover.md` | No doc claims the backend is unwired | S |
| X0.2 | Add `backend/ROADMAP_STATE.md`: one line per task ID, status, and the commit that closed it | new file | Every later session can resume without re-reading this file | S |
| X0.3 | Pin the API contract: expand `app/schemas.py` into a versioned contract module and add a test that snapshots the OpenAPI schema | `app/schemas.py`, `tests/test_contract.py` | `test_contract.py` fails on any unplanned response-shape change | M |
| X0.4 | Write `docs/ARCHITECTURE.md`: the tier cascade, the escalation rule, module boundaries, and what runs at the checkpoint vs centrally | new file | A new contributor can name where a given check belongs | S |

### Phase 1 — Tier 0: deterministic gate (B1)

This is the highest value-per-hour block in the entire roadmap. It is pure
arithmetic and string parsing, needs no model, no GPU, and a judge can verify
it in ten seconds. Do not skip ahead of it.

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| B1.1 | Character-value table + `7-3-1` weighted checksum function, exactly as ICAO Doc 9303 Part 3 | `app/pipeline/tier0/mrz.py`, `tests/test_mrz_checkdigit.py` | Known MRZ strings produce the documented check digits; `<` maps to 0 | S |
| B1.2 | TD3 parser (passport, 2×44). Field offsets as named constants, not magic numbers | `app/pipeline/tier0/mrz.py`, `tests/test_mrz_td3.py` | A real specimen MRZ parses to correct doc number, nationality, DOB, sex, expiry | M |
| B1.3 | TD1 parser (ID card, 3×30) including the composite check digit over lines 1–2 | `app/pipeline/tier0/mrz.py`, `tests/test_mrz_td1.py` | Composite digit verified; a mutated composite is caught | M |
| B1.4 | TD2 parser (visa, 2×36) | `app/pipeline/tier0/mrz.py`, `tests/test_mrz_td2.py` | Passes on a specimen visa MRZ | S |
| B1.5 | Composite check digit for TD3 (positions 1–10, 14–20, 22–43 of line 2) | `app/pipeline/tier0/mrz.py` | A forged final digit is detected | S |
| B1.6 | Name parsing with ICAO transliteration: `<<` surname separator, `<` given-name separator, space filler, diacritic stripping | `app/pipeline/tier0/mrz.py`, `tests/test_mrz_names.py` | `ERIKSSON<<ANNA MARIA` → `surname: ERIKSSON`, `given: ANNA MARIA` | M |
| B1.7 | Date rules engine: expired, not-yet-valid, issue-after-expiry, implausible DOB, cross-checked against a configurable reference date | `app/pipeline/tier0/dates.py`, `tests/test_dates.py` | Each rule emits a distinct rule code; reference date is injectable (no `datetime.now()` in tests) | M |
| B1.8 | Watchlist connector interface + `MockWatchlist` backed by a JSON seed file (stolen numbers, blacklisted, expired-override list) | `app/pipeline/tier0/watchlist.py`, `app/seed/watchlist.json`, `tests/test_watchlist.py` | A number in the seed fires `WATCHLIST_HIT`; swapping in an `InterpolWatchlist` needs no caller change | M |
| B1.9 | MRZ band detector in OpenCV: binarize, morphological gradient, horizontal projection profile, group into 2 or 3 monospace lines, return a polygon per line | `app/pipeline/tier0/mrz_region.py`, `tests/test_mrz_region.py` | Returns a polygon per line on a synthetic MRZ image; returns empty (not an exception) when no MRZ is present | L |
| B1.10 | Map parsed fields to sub-regions of the MRZ line (which x-range is the DOB, which is the doc number) so a flag can point at a field, not a line | `app/pipeline/tier0/mrz_region.py`, `tests/test_mrz_field_regions.py` | Each extracted field carries a bbox; test asserts the DOB bbox covers the DOB characters | M |
| B1.11 | Tier 0 runner: run MRZ + dates + watchlist, emit `EvidenceFlag` objects, exit hard on checksum or blacklist failure without running later tiers | `app/pipeline/tier0/runner.py`, `tests/test_tier0.py` | Worked example A from the abstract (DOB check digit expected 4, found 7) reproduces exactly | M |
| B1.12 | Expose Tier 0 over HTTP: `POST /api/screen?tier=tier0` returning flags, hard-fail reason, and per-field regions; leave `/api/analyze` untouched | `app/api/routes_screen.py`, `app/main.py`, `tests/test_tier0_api.py` | Existing 13 API tests still pass unchanged | M |

### Phase 2 — Evidence flags and the risk engine (B2)

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| B2.1 | `EvidenceFlag` schema: `id`, `tier`, `label`, `weight_band`, `value` ∈ [0,1], `confidence`, `region` (polygon or bbox, nullable), `expected`, `found`, `reason`, `source_module` | `app/risk/flags.py`, `tests/test_flags.py` | Rejects a flag whose `value` is out of range; regions are validated as polygons | M |
| B2.2 | Versioned weightset file (`app/risk/weightsets/v1.yaml`) + loader exposing `ruleset_version` | `app/risk/weights.py`, `tests/test_weights.py` | Every flag id in the codebase resolves to a weight or the loader raises in tests | M |
| B2.3 | Weighted-sum engine `R = Σ(wᵢ·Fᵢ) + hard_rules`, normalised to 0–100, with hard rules overriding to a floor | `app/risk/engine.py`, `tests/test_engine.py` | Worked example B from the abstract (R1 = 0.41 vs 0.55 threshold) produces the expected band | M |
| B2.4 | Band mapping Low / Review / High with configurable thresholds; the Review band must exist and must not auto-reject | `app/risk/bands.py`, `tests/test_bands.py` | Boundary values land in the documented band; Review maps to `review`, never `reject` | S |
| B2.5 | Thread `score`, `band`, `flags`, `ruleset_version`, `model_versions` into the `/api/screen` response | `app/schemas.py`, `app/api/routes_screen.py`, `tests/test_screen_response.py` | Response contract test updated and passing | M |
| B2.6 | History layer: bounded, decaying prior from *verified* outcomes only, half-life configurable, hard cap on how far it can move R | `app/risk/history.py`, `tests/test_history.py` | Cap and decay tested; a single old verified pass cannot move the band; unverified outcomes contribute nothing | M |
| B2.7 | Explain the score: return a per-flag contribution breakdown so the UI can show "why", not just "how much" | `app/risk/engine.py`, `tests/test_contributions.py` | Contributions sum to the final score (property test) | M |
| B2.8 | Calibration script: sweep thresholds against a labelled CSV and emit a precision/recall table + the chosen threshold | `scripts/calibrate.py`, `scripts/data/labels.csv` | Script runs end to end on synthetic labels and prints a table | M |

### Phase 3 — Persistence, hashing, Merkle audit (B3)

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| B3.1 | DB engine + session factory, SQLite by default, `DATABASE_URL` override, Alembic wired from task one | `app/storage/db.py`, `alembic.ini`, `alembic/` | `alembic upgrade head` on an empty SQLite file succeeds; Postgres URL accepted by config | M |
| B3.2 | ORM models: `Screening`, `ScreeningFlag` (JSON column), `AuditEvent`, `LedgerEntry`, `Officer` | `app/storage/models.py` | Migrations generate and round-trip | M |
| B3.3 | `ScreeningRepository` with create / get / list (filter by band, date range, doc type) / delete; pagination | `app/storage/repository.py`, `tests/test_repository.py` | List with filters + pagination tested against a temp DB | M |
| B3.4 | Canonical JSON serialisation + salted SHA-256 record hash (RFC 8785-style key ordering, no floats, no `None` ambiguity) | `app/audit/hashing.py`, `tests/test_hashing.py` | Same record always hashes the same; changing one field changes the hash; salt is per-record and stored, not global | M |
| B3.5 | Merkle tree (RFC 6962 domain-separated leaves/nodes), root, inclusion proof generation, and proof verification | `app/audit/merkle.py`, `tests/test_merkle.py` | Proof verifies for every leaf; a mutated leaf fails verification; single-leaf and odd-count trees handled | M |
| B3.6 | `Ledger` interface + `SqliteLedger` (append-only: DB triggers reject UPDATE and DELETE) | `app/audit/ledger.py`, `tests/test_ledger.py` | `UPDATE ledger_entries` raises; append and read work | M |
| B3.7 | Batch anchoring job: group unanchored events into Merkle batches, write one root per batch, record the batch id on each event | `app/audit/anchoring.py`, `tests/test_anchoring.py` | 100 events → N batches; every event resolvable to a batch and proof | M |
| B3.8 | Emit `AuditEvent` on every status transition and on every officer action including overrides; record `ruleset_version` and model versions on the event | `app/audit/events.py`, `tests/test_events.py` | An override produces its own event, distinct from the automated result | M |
| B3.9 | `GET /api/audit/{audit_id}/verify` — recompute the hash from stored data, walk the Merkle proof, compare to the anchored root, return `verified` / `altered` / `unknown` | `app/api/routes_audit.py`, `tests/test_audit_api.py` | Tampering with a stored record in the test DB flips the endpoint to `altered` | M |
| B3.10 | Encrypted off-chain blob store for evidence images: AES-GCM via `cryptography`, per-blob DEK wrapped by a master key from env, content-addressed filenames | `app/storage/blobs.py`, `tests/test_blobs.py` | Ciphertext on disk does not contain the plaintext header; wrong key fails closed | L |
| B3.11 | Retention config: `RETENTION_DAYS` per record class, a purge function, and a test that a purge actually deletes and logs what it deleted | `app/storage/retention.py`, `tests/test_retention.py` | Purge is idempotent and never touches ledger entries | M |
| B3.12 | Ed25519 signature over each batch root, key from env, public key exposed by `GET /api/audit/pubkey` | `app/audit/signing.py`, `tests/test_signing.py` | Signature verifies with the published public key; fails on a tampered root | M |

### Phase 4 — Tier 1: light analysis (B4)

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| B4.1 | `OcrEngine` interface with `TesseractEngine` and `EasyOcrEngine`; both return text + per-word confidence | `app/pipeline/tier1/ocr.py`, `tests/test_ocr.py` | Interface test runs against a synthetic image; the unavailable engine degrades, it does not crash | L |
| B4.2 | Confidence-gated re-read: below threshold, crop the field region, re-OCR at higher DPI, then try the fallback engine; only then is a flag raised | `app/pipeline/tier1/ocr.py`, `tests/test_ocr_reread.py` | A deliberately misread field is re-read correctly before any flag fires (this is the anti-false-alarm rule from the abstract) | M |
| B4.3 | Visible-text field extraction per document type (regex + anchor-word location, not blind layout slicing) | `app/pipeline/tier1/fields.py`, `tests/test_fields.py` | Extracts name / doc number / DOB / expiry from a synthetic MRZ-bearing image | L |
| B4.4 | OCR-to-MRZ field comparison, transliteration-tolerant, emitting a flag per mismatched field with the field's region | `app/pipeline/tier1/ocr_compare.py`, `tests/test_ocr_compare.py` | Deliberately altered printed DOB yields exactly one `OCR_MRZ_MISMATCH` flag with the right region | M |
| B4.5 | 2D barcode / QR decoder (`zxing-cpp`) behind an interface, then compare decoded payload against printed fields | `app/pipeline/tier1/barcode.py`, `tests/test_barcode.py` | Decodes a generated QR; a QR/print disagreement yields a flag | M |
| B4.6 | Template registry: a template is a reference image + field rectangles, stored as JSON; per document type | `app/pipeline/tier1/templates/registry.py`, `templates/*.json` | Adding a new document type is adding one JSON file, no code | M |
| B4.7 | Alignment: corner detection → homography → warp to template space | `app/pipeline/tier1/align.py`, `tests/test_align.py` | A rotated, skewed photo warps to approximately the template | L |
| B4.8 | Layout / font / position deviation scoring in aligned space, with per-field tolerances | `app/pipeline/tier1/layout.py`, `tests/test_layout.py` | A field moved outside tolerance yields a `LAYOUT_DEVIATION` flag with a region | L |
| B4.9 | Face detection + alignment + embedding behind an `Embedder` interface; ship `InsightFaceEmbedder` and a deterministic `NullEmbedder` for environments without the model | `app/pipeline/tier1/face.py`, `tests/test_face.py` | Interface contract test passes with the null embedder; real embedder skipped if unavailable | M |
| B4.10 | Live capture endpoint + `LiveCapture` session store (short-lived, in-memory, consented); client-side capture is F9 | `app/api/routes_capture.py`, `tests/test_capture.py` | A capture session expires and is single-use | M |
| B4.11 | Face match scoring → `FACE_MISMATCH` / `FACE_LOW_SIMILARITY` flag carrying similarity and threshold, following the abstract's worked example B numbers | `app/pipeline/tier1/face.py`, `tests/test_face_match.py` | similarity 0.41 vs threshold 0.55 reproduces the abstract's example | S |
| B4.12 | Tier 1 runner producing partial score `R1`, plus the escalation rule (ambiguous band, high-risk profile, random audit draw, full-depth mode) | `app/pipeline/tier1/runner.py`, `app/pipeline/orchestrator.py`, `tests/test_orchestrator.py` | Four distinct escalation triggers each route to Tier 2; a clean low-risk case does not | L |

### Phase 5 — Tier 2: deep analysis (B5)

Every task here ships an interface plus an honest, labelled stand-in. None of
it may be described as a validated detector.

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| B5.1 | `DeepModule` interface + registry, so a missing module degrades to "not run" rather than failing the screening | `app/pipeline/tier2/base.py`, `tests/test_tier2_base.py` | Registering zero modules still returns a valid screening | S |
| B5.2 | Error-level analysis: re-encode at several JPEG qualities, measure per-block discrepancy, output a normalised heatmap | `app/pipeline/tier2/ela.py`, `tests/test_ela.py` | Heatmap localises a re-compressed region on a synthetic edit | M |
| B5.3 | Noise-residual analysis: high-pass residual, local variance map, sensor-noise consistency | `app/pipeline/tier2/noise_residual.py`, `tests/test_noise.py` | Edited region shows anomalous residual variance | M |
| B5.4 | Copy-move detection via self-similarity matching on SIFT/ORB blocks | `app/pipeline/tier2/copy_move.py`, `tests/test_copy_move.py` | A duplicated region inside the document is localised | L |
| B5.5 | Heatmap fusion: combine B5.2–B5.4 into one tamper score + one overlay mask, with the contributing modules named | `app/pipeline/tier2/fusion.py`, `tests/test_fusion.py` | Fusion output names which modules contributed; a clean document yields a near-zero score | M |
| B5.6 | Stamp detection + template matching against registered stamp templates, with a "no template registered" honest state | `app/pipeline/tier2/stamp.py`, `tests/test_stamp.py` | Matching stamp is found; missing template reports `not_configured`, not `clean` | M |
| B5.7 | Morph classifier interface + a clearly labelled heuristic stand-in (frequency + boundary irregularity cues at the photo region) | `app/pipeline/tier2/morph.py`, `tests/test_morph.py` | Response includes `is_stub: true` and a `model_version` of `heuristic-v0` | M |
| B5.8 | Deepfake classifier interface + a clearly labelled heuristic stand-in | `app/pipeline/tier2/deepfake.py`, `tests/test_deepfake.py` | Same stub labelling contract as B5.7 | M |
| B5.9 | Unsupervised anomaly detector (IsolationForest over a per-document feature vector) for forgery styles not in training | `app/pipeline/tier2/anomaly.py`, `tests/test_anomaly.py` | Scores an out-of-distribution synthetic document above in-distribution ones; trained on a committed feature fixture | M |
| B5.10 | Randomised deep audit sampler: `DEEP_AUDIT_RATE`, draw by `HMAC(server_secret, screening_id)` so it is unpredictable to the officer but reproducible for audit | `app/pipeline/audit_draw.py`, `tests/test_audit_draw.py` | Same id always draws the same outcome; distribution matches the configured rate over 10k ids | M |

### Phase 6 — Cross-document verification (B6)

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| B6.1 | `TravelerCase` grouping model: one case, N documents, each with a role (passport / visa / ID) | `app/storage/models.py`, `app/storage/repository.py` | Two documents attach to one case and appear together | M |
| B6.2 | Name comparison with transliteration tolerance (diacritics, `Ph`/`F`, compound surnames, ordering) returning a similarity plus the differing tokens | `app/pipeline/crossdoc/names.py`, `tests/test_names.py` | `Mueller` vs `Müller` matches; `Muller` vs `Mueller` matches; `Rahman` vs `Rahmani` does not fully match | M |
| B6.3 | Passport-number ↔ visa cross-match, and validity-window consistency (visa must cover the travel date) | `app/pipeline/crossdoc/documents.py`, `tests/test_crossdoc.py` | A visa referencing an unknown passport raises a flag | M |
| B6.4 | Same-face consistency across documents in a case | `app/pipeline/crossdoc/face_consistency.py`, `tests/test_face_consistency.py` | Uses the B4.9 interface; degrades cleanly without embeddings | M |
| B6.5 | Cross-document runner emitting flags into the same `EvidenceFlag` stream with `tier: crossdoc` | `app/pipeline/crossdoc/runner.py` | Flags from B6.2–B6.4 aggregate into the same risk score | M |

### Phase 7 — Explainability (B7)

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| B7.1 | `Summarizer` interface + self-hosted LLM client (Ollama / llama.cpp HTTP) with a hard timeout, no external fallback, and no data leaving the host | `app/explain/summarizer.py`, `tests/test_summarizer.py` | Client is never called when `LOCAL_LLM_ENABLED=false`; a timeout returns `None`, not an exception | M |
| B7.2 | Rule-based template summariser producing 2–3 sentences with one line per flag; used whenever the LLM is unavailable or rejected | `app/explain/template_summary.py`, `tests/test_template_summary.py` | Template output itself passes the B7.3 verifier | M |
| B7.3 | Code-based verifier: extract every number, date, field name, and capitalised token from the summary and require each to exist in the flag data | `app/explain/verifier.py`, `tests/test_verifier.py` | A summary inventing `0.98` or `MRZ_DOB` not present in flags is rejected; the verifier needs no model | M |
| B7.4 | Reject-and-fallback wiring: verifier failure → discard LLM text → use B7.2 → record `summary_source` and `verification: failed` in the response | `app/explain/pipeline.py`, `tests/test_explain_pipeline.py` | Deliberately poisoned LLM output never reaches the client; the reason is auditable | M |
| B7.5 | Versioned prompt template file, loaded at runtime, with the prompt version returned in the response | `app/explain/prompts/v1.txt`, `app/explain/prompts.py` | Changing the prompt file changes `prompt_version` in the response | S |
| B7.6 | Per-flag one-line reason strings in plain language, separate from the LLM narrative, so the officer always has a model-free explanation | `app/risk/flag_reasons.py`, `tests/test_flag_reasons.py` | Every flag id in the weightset has a reason template | M |

### Phase 8 — Backend API surface (B8)

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| B8.1 | `POST /api/screenings` — multipart create, returns `screening_id` + `audit_id` immediately, analysis continues | `app/api/routes_screenings.py` | Client can poll or subscribe without blocking | M |
| B8.2 | `GET /api/screenings` — list with band / date / doc-type filters and pagination | same | Matches the B3.3 repository contract | S |
| B8.3 | `GET /api/screenings/{id}` — full result: score, band, flags with regions, summary, verification status, versions | same | Contract test covers every field | M |
| B8.4 | `POST /api/screenings/{id}/decision` — `allow` / `further_inspection` / `reject` + remark + `override` flag + optional score override | same | Emits B3.8 audit event; `reject` is impossible without an explicit override when band is Low | M |
| B8.5 | `DELETE /api/screenings/{id}` — soft delete respecting retention, ledger entry untouched | same | Deleted screening disappears from list; audit proof still verifies | S |
| B8.6 | Server-Sent Events stream for cascade progress (tier + module status) so the UI can show Tier 0 → 1 → 2 progressing | `app/api/routes_stream.py` | A 10-event stream completes and disconnects cleanly; works with Cloud Run's request timeout in mind | L |
| B8.7 | Printable report route (`GET /api/screenings/{id}/report`) returning standalone HTML with flags, reasons, bands, and the audit id | `app/api/routes_report.py` | Opens in a browser with no frontend assets | M |
| B8.8 | Security hardening pass: rate limiting (per-IP and per-key), request size caps, structured logging with request ids, generic error messages, no image bytes logged | `app/middleware/*`, `tests/test_security.py` | Abusive client is throttled; logs contain no image data | M |
| B8.9 | Officer auth **backend only**: argon2id password hashing, JWT access tokens, roles `officer` / `supervisor` / `admin`, no UI | `app/auth/*`, `tests/test_auth.py` | No HTML page references a credential field; endpoints reject missing tokens | L |
| B8.10 | `GET /health` (liveness) and `GET /ready` (readiness: DB + ledger reachable); `/api/version` returns app, ruleset, model and prompt versions | `app/main.py`, `app/api/routes_meta.py` | Deploy probes can use them; version endpoint feeds the about page | S |
| B8.11 | `PUBLIC_DEMO` mode flag: unauthenticated but read-mostly, strict per-IP quota, rejects repeat submissions, returns a demo watermark in reports | `app/config.py`, `app/middleware/quotas.py`, `tests/test_public_demo.py` | Production deployments can require auth without code changes | M |

### Phase 9 — Frontend (F)

#### 9a — Shared plumbing

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| F1 | `api.js` — single fetch client: base URL from `window.DRISHTI_CONFIG`, timeouts, `AbortController`, normalised `{code,message}` errors, no `fetch` calls outside this file | `frontend/api.js`, `frontend/api.test.cjs` | `pages.js` and `home.js` contain zero direct `fetch` | M |
| F2 | `overlay.js` — canvas overlay that draws flag regions on the document image with hover/click/selection states and a colour per weight band | `frontend/overlay.js`, `frontend/overlay.test.cjs` | Given synthetic regions, hit-testing selects the right flag | M |
| F3 | `format.js` — band labels, score formatting, relative timestamps, flag weight labels; single source for display strings | `frontend/format.js`, `frontend/format.test.cjs` | Unit-tested formatting, no hard-coded strings in pages | S |
| F4 | `status.js` — connection state to the API (`checking` / `online` / `unreachable`) surfaced in the topbar instead of a silent "Could not connect" | `frontend/status.js`, `frontend/status.test.cjs` | Distinct message for CORS/network vs 5xx vs validation error | M |

#### 9b — Officer screening workspace

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| F5 | Extract the duplicated sidebar + topbar shell into `shell.html`, injected by `build.cjs` at build time; source pages keep a static fallback | `frontend/shell.html`, `build.cjs`, all `*.html` | Shell markup exists once; the existing shell-consistency test inverts to assert injection | M |
| F6 | `screening.html` — the officer workspace: document type selector (passport / visa / national ID / permit), upload, live capture, and a clear quality-gate step | new page + `screening.js` | Reachable from the home "Start screening" button; passes UX4G preflight first | L |
| F7 | Real camera capture with `getUserMedia`, explicit consent text, capture-frame-then-upload, and a graceful "requires HTTPS / permission denied" state | `frontend/screening.js` | Works on `localhost` and on HTTPS; fails with a readable message, not a blank frame | M |
| F8 | Cascade progress panel: Tier 0 / 1 / 2 rows that fill in as the SSE stream reports module completion, with per-module status and elapsed time | `frontend/screening.js`, `frontend/screening.css` | Matches the B8.6 event shape; degrades to polling if SSE is blocked | M |
| F9 | Retake prompt: when the quality gate fails, show which checks failed and offer "Retake" / "Analyse anyway" with the consequence stated | `frontend/screening.js` | Retake clears the file; "Analyse anyway" requires an explicit click | S |
| F10 | `result.html` — full result view replacing the results modal as the primary surface: band badge, score, versions, and the document image with overlay | new page + `result.js` + `result.css` | Loads from `?id=<screening_id>`; deep-linkable and refresh-safe | L |
| F11 | Flag list panel: label, weight band, confidence, expected vs found, plain-language reason, tier badge; grouped by tier | `frontend/result.js` | Every flag in the B2.1 schema renders; unknown flags render as a defensive fallback row | M |
| F12 | Flag ↔ region interaction: clicking a flag highlights its region on the image and scrolls it into view; clicking a region selects the flag | `frontend/overlay.js`, `frontend/result.js` | Round-trip selection works both directions | M |
| F13 | Officer summary panel: the verified summary text, plus `summary_source` and `verification` badges; on verification failure, show the fallback and the reason | `frontend/result.js` | A `verification: failed` response is visibly different from a verified one | M |
| F14 | Decision form: Allow entry / Send for further inspection / Reject entry, remark textarea, and an override control that appears only when the officer contradicts the band | `frontend/result.js` | Submitting posts to B8.4 and locks the form; a second submission is blocked client-side too | M |
| F15 | Post-decision state: status transition shown, audit id surfaced with a link to the verification view, model/ruleset versions displayed | `frontend/result.js` | Audit id is copyable and links to F19 | S |

#### 9c — History, audit, case views

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| F16 | Rewire `screenings.html` from sample rows to `GET /api/screenings`, keeping the existing table, search, filter chips, sort, pagination, and CSV export | `frontend/pages.js`, `frontend/screenings.html` | Empty state, loading state, and error state all handled; sample rows gone or clearly behind a "demo data" toggle | M |
| F17 | Row action becomes "View" → `result.html?id=…`; Delete calls B8.5 and refreshes the list | `frontend/pages.js` | Delete confirms, then the row disappears and the count updates | S |
| F18 | `audit.html` — audit trail viewer: event list for a screening with type, actor, timestamp, ruleset/model version, and batch id | new page + `audit.js` | Renders the B3.8 event stream | M |
| F19 | Merkle verification panel: enter or auto-load an audit id, show batch root, proof length, and `verified` / `altered` / `unknown` with a plain explanation of what was checked | `frontend/audit.js` | A tampered record visibly flips to `altered` | M |
| F20 | `cases.html` — cross-document case view: documents in a case, per-document band, and the cross-document flags | new page + `cases.js` | Two documents in a case render side by side with the mismatch highlighted | M |
| F21 | Profile page reads real officer identity from the API once B8.9 exists; until then it stays explicitly a sample profile | `frontend/pages.js`, `frontend/profile.html` | No password field appears under any circumstance; if auth is off, the page says so | S |

#### 9d — UX4G compliance, accessibility, and verification

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| F22 | UX4G preflight for each new page: read `Design.md`, list every component with exact variant and size, identify any UX4G gap before writing custom CSS | design notes per page | Written component plan exists per page before code (required by the `ux4g-design` skill; theme stays the default light theme already chosen) | S per page |
| F23 | Modal focus management: focus trap, `Escape`, focus restore, and `aria-modal` on both the source chooser and any remaining dialogs | `frontend/home.js`, `frontend/result.js` | Keyboard-only walkthrough passes | M |
| F24 | Responsive pass at 320 / 768 / 1024 / 1440 CSS px for all 9 pages, light and dark, including the overlay canvas and the flag list side by side vs stacked | CSS | No overflow, no clipped overlay, no unreadable dark-mode text | M |
| F25 | Contrast audit in light and dark, plus a check that text-size scaling (112.5% / 125%) does not break the table, overlay, or decision form | CSS + manual check | Recorded results; the ~32 internal `px` sizes in the package are documented as known debt | M |
| F26 | **Real-browser verification pass** — the single highest-value outstanding item from `handover.md`. Screenshots of all 9 pages in light and dark, console and network clean, every interaction exercised | manual + `browser-testing-with-devtools` | Screenshots committed. No visual claim in this repo is currently browser-verified. | L |
| F27 | Test suite growth to cover the new pages and scripts, following the existing `node --test` structural pattern plus real unit tests for pure functions | `frontend/*.test.cjs` | Suite passes; the shared-shell test now asserts injection rather than duplication | M |

### Phase 10 — Ops and deployment (O)

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| O1 | Multi-stage backend `Dockerfile`, non-root user, pinned base image, no `.venv` or caches in the image | `backend/Dockerfile`, `.dockerignore` | Image builds and runs `/health` | M |
| O2 | Cloud Run settings: concurrency 1, max instances, request timeout sized for the cascade, `CORS_ORIGINS` per environment, secrets from Secret Manager | deploy config | No public runaway spend; env vars documented in one place | S |
| O3 | Postgres on Cloud SQL + Alembic migration run in the deploy step; keep the SQLite path working for local demo | `alembic/`, deploy config | Same migrations pass on both engines | M |
| O4 | Redis queue + stateless worker skeleton for Tier 1/2 so a long cascade does not hold an HTTP request | `app/queue/`, `worker.py` | A screening can be queued and picked up; falls back to in-process when Redis is absent | L |
| O5 | Object storage adapter for evidence blobs (S3/MinIO) with server-side encryption, behind the B3.10 interface | `app/storage/blobs_s3.py` | Interface test passes against a local MinIO or a fakes3 double | M |
| O6 | Frontend deployment: Pages build variables per environment, CORS allowlist kept in one documented list matching actual serving origins | `build.cjs`, deploy docs | Every real origin is allowed exactly; no stale entries | S |
| O7 | Observability: per-tier latency metrics, cascade outcome counters, error rate, and a correlation id that appears in every log line and in the screening record | `app/observability/*` | You can answer "how long does Tier 2 take" from logs | M |
| O8 | CI: GitHub Actions running `npm test`, `npm run build`, and `pytest` on every push, with the build artefact contract asserted | `.github/workflows/ci.yml` | A red test blocks the branch | M |
| O9 | Public-endpoint protection: API key option for the demo, per-IP quota, and a synthetic-image-only notice surfaced in the UI and the API response | `app/middleware/*`, `frontend/home.html` | Someone cannot burn your GPU quota with a script | M |
| O10 | Seed script that generates the synthetic demo dataset: fake passports, visas, and IDs, each with known tampering, plus the matching watchlist and template files | `scripts/make_demo_data.py` | A judge can run the whole demo from a clean clone with one command | M |
| O11 | Demo script and a `DEMO.md`: the 3-minute judge walkthrough, which claims are measured vs designed, and the known limitations | `DEMO.md` | Every number you say out loud is either measured (V-phase) or labelled a design target | M |

### Phase 11 — Validation and evaluation (V)

`abstract.txt` currently states "No accuracy figures are claimed in this
document." This phase is how you earn the right to change that sentence.

| ID | Task | Touches | Done when | E |
|---|---|---|---|---|
| V1 | Synthetic document generator: passports, visas, IDs with controllable fields, MRZ, layout, and injected tampering (photo swap, text edit, date change, stamp edit) | `scripts/gen_synthetic.py`, `tests/data/` | Produces a labelled corpus with a manifest of ground truth per document | L |
| V2 | Ground-truth format: per-document JSON with tampered regions as polygons, so region-overlap metrics are computable | `tests/data/manifest.schema.json` | Schema validated by a test | S |
| V3 | Evaluation harness: field-level extraction accuracy, tamper catch rate, false-alert rate, and region overlap (IoU) | `scripts/evaluate.py` | Prints a table over the corpus; exits non-zero on regression | L |
| V4 | MRZ negative corpus: N documents with a single deliberately corrupted check digit each; all must be caught | `tests/data/mrz_negative/*` | 100% catch rate or the harness fails | M |
| V5 | Latency benchmark per tier, reporting median and p95 against the abstract's targets (<0.3 s / 0.5–1 s / 1–2 s) and stating clearly that these were targets | `scripts/benchmark.py` | Produces a table labelled measured vs target | M |
| V6 | Face-evaluation scaffolding: FAR/FRR reporting shape with per-demographic-group slots, wired to the B4.9 interface, explicitly empty until a real embedder is available | `scripts/eval_face.py` | Runs and honestly reports "no model configured" | M |
| V7 | Morp/ deepfake evaluation scaffolding following the NIST FATE MORPH framing (attacks missed vs genuine wrongly flagged), stub-labelled | `scripts/eval_morph.py` | Same honesty contract as B5.7 | M |
| V8 | Results page in the app (`about.html` extension or a `results.html`) showing measured metrics with the dataset each came from | `frontend/results.html` | Judges can see the numbers and the method on the site | M |

---

## 5. Critical path

If time is short, this is the order that maximises demonstrated capability per
hour. Everything else is optional.

1. **B1.1 → B1.6** — MRZ parsing and check digits. Pure logic, fully testable,
   instantly verifiable by a judge. This is the module the rest of the system
   is built on and the one most likely to impress.
2. **B1.9, B1.10** — MRZ region detection. This is what makes "the DOB field is
   highlighted" possible, and that single screenshot sells the whole product.
3. **B2.1 → B2.5** — flags, weights, engine, bands. Turns a pass/fail into a
   risk score with reasons.
4. **B1.11, B1.12, B8.1–B8.3** — expose it. End to end: upload → flags → band.
5. **B3.4, B3.5, B3.8, B8.4, B3.9** — hash, Merkle, decision, verify. The audit
   story is a named differentiator in the abstract; this is a day of work.
6. **F10, F11, F12, F14** — the result page with the overlay, the flag list, and
   the decision form. This is the screen a judge looks at.
7. **B7.2, B7.3** — the verifier. Cheap, pure code, and the "the model narrates
   and never decides" claim becomes real rather than aspirational.
8. **F26** — the browser pass. Nothing above is verified until someone opens it.

If you have 36 hours, that is roughly the whole first day and a half. Phases 4,
5, 6, 10 and 11 are what turn it from a strong demo into a submission.

---

## 6. Definition of done for the project

- [ ] An officer can upload or capture a document and receive a banded risk
      score with per-flag reasons and document locations.
- [ ] Hard failures (broken checksum, blacklist hit) exit in under a second with
      the offending field highlighted.
- [ ] The Review band exists, and nothing auto-rejects a borderline case.
- [ ] The officer records a decision, and that decision is in the audit trail
      alongside the automated result.
- [ ] Any single screening event can be independently verified against an
      anchored Merkle root, and a tampered record is detected.
- [ ] No identity data reaches the ledger — hashes only.
- [ ] Every visual claim in this repository has been checked in a real browser,
      in light and dark, at four widths.
- [ ] Measured accuracy numbers exist, each labelled with the dataset it came
      from, or the "no accuracy figures are claimed" line still stands.
- [ ] There is no password field anywhere in the frontend unless a real
      authentication backend is deployed behind it.

---

## 7. Known traps

- **The UX4G 2.1.0 README lies.** It documents accordion attributes the runtime
  does not implement and a `completed` stepper class that does not exist.
  Grep `node_modules/ux4g-web-components/dist/runtime/design-system.js` and
  `styles/ux4g.css` before using any class.
- **UX4G 2.1.0 ships a malformed CSS selector** that breaks the horizontal
  stepper. `pages.css` works around it. If a test asserting the malformed
  selector starts failing, the package was fixed — delete the workaround.
- **Never call `datetime.now()` inside Tier 0 logic.** Inject the reference
  date, or the date-rule tests become untestable.
- **Tier 2 stand-ins must carry `is_stub: true`.** An unlabelled heuristic in a
  border-security project is a claim you cannot support.
- **Do not put OCR text, images, or embeddings in the ledger or in logs.**
- **The public API has no auth.** Land B8.8 rate limiting before Tier 1/2 model
  loading, not after.
- **`home.css` is the app shell stylesheet despite its name.** Renaming it is a
  clean, cheap follow-up to F5.
- **Recheck `git status` before starting.** The tree is clean today, but that
  has not been true for the last three sessions.
