# DRISHTI — Settled Decisions

**Created:** September 30, 2026
**Purpose:** Record the three decisions that are already settled so a future
session does not re-litigate them. Each one was a real fork, it was decided
deliberately, and reopening it costs time without a visible benefit.

**Status of this file:** these decisions are **closed**. Do not re-open one
because the lorebook or an earlier design note says something different. If a
decision genuinely must change, that is a new, explicit decision with a new
entry at the bottom of this file — not a silent edit to an existing one.

Related documents: `ROADMAP.md` (strategy), `tasks.md` (executable checklist),
`handover.md` (session state), `lorebook/` (domain context, not architecture).

---

## D1 — The frontend is vanilla HTML/CSS/JS; no React

**Status:** settled · **Settled by:** project maintainer

The six shipped pages (`home`, `screenings`, `settings`, `guide`, `about`,
`profile`) are plain HTML with `home.css` / `pages.css` and plain JS modules
(`home.js`, `pages.js`, `preferences.js`). There is no build-time framework
step beyond `frontend/build.cjs`, which copies files and generates
`dist/api-config.js`.

**Why**

- The lorebook mentions React + Tailwind. The repo is deliberately not that,
  and the two have diverged for the whole prototype.
- UX4G is the government design mandate for this project, and
  `ux4g-web-components@2.1.0` is explicitly framework-neutral: it supplies CSS
  components and a runtime usable from plain HTML. A framework migration buys
  nothing a judge can see.
- Six pages and 45 passing tests already exist. A rewrite costs roughly two
  days of the demo runway and adds no capability.

**What this forbids**

- No `package.json` UI framework dependency, no JSX/Vite/Next/webpack app
  shell, no component build step, no Tailwind.
- The Cloudflare Pages build stays `node frontend/build.cjs`.

**Revisit only if** the roadmap grows an interactive surface that genuinely
cannot be expressed as page-level JS — and then as a new decision, not by
quietly adding a framework.

---

## D2 — No authentication for now

**Status:** settled · **Settled by:** project maintainer

The public demo and the API are unauthenticated. There is no login,
registration, logout, password-reset, or password field anywhere in the
frontend, and the Cloud Run API has no auth and no rate limiter.

**Why**

- The prototype shipped a mock credential flow. Cloudflare's security team
  served a phishing interstitial over it, and the mock flow was removed. Mock
  credential collection is a real harm here — it misrepresents the project to
  visitors and to the host — so it is not an acceptable shortcut.
- There is no auth backend to talk to. A form that collects a password and
  discards it is worse than no form.
- A quality-checker demo needs to be openable by a judge in one click, with no
  account to create first.

**What this forbids**

- No password input, no "Change password" affordance that is not
  `aria-disabled="true"` and explicitly labelled as having no account behind
  it, and no demo copy implying the product has accounts.
- Never add a credential field that does not talk to a real authentication
  backend. The user has not authorised one.

**When this changes** — real auth is planned, backend-first. Build argon2id
hashing and JWT issuance on the server (`app/auth/*`) and only *then* add
sign-in UI, on a separate operator route, never on the public demo page. The
profile page stays an explicitly labelled sample until an API actually serves
an officer identity.

**Related but separate:** the open API needs rate limiting and a
`PUBLIC_DEMO` mode before the model-loading tiers land. That is a security
task, not an auth task, and it does not reopen D2.

---

## D3 — The UX4G default light theme ships as the default

**Status:** settled · **Settled by:** project maintainer

The application renders with UX4G's own default light theme. `preferences.js`
defaults to `{ theme: "light", textSize: "default" }` and sets
`data-theme="light"` on the root element, loaded synchronously in `<head>` on
every page so there is no flash of the wrong theme.

**Why**

- The user has already chosen the default theme. It is not to be re-asked
  unless a branded theme is explicitly requested.
- UX4G's own token set is the mandate. Inventing custom theme-token overrides
  creates a second source of truth that can drift from the design system.
- Dark and system themes remain available at runtime because they are
  UX4G's own tokens, not a custom theme. A visitor's choice persists under the
  single key `drishti.preferences.v1` and is only a preference — it does not
  change what ships.

**What this forbids**

- No custom UX4G token overrides, no rebrand palette, no hand-rolled colour
  scale, and no forked stylesheet.
- The accessibility toggle stays a text-size preference, not a theme.

**Revisit only if** the user explicitly asks for a branded theme. When a new
page is added, the `ux4g-design` preflight still applies, and the theme
question is already answered by this decision.

---

## How to use this file

- Read it before proposing architecture, UI, or security changes.
- Do not treat any decision here as up for debate in a routine task.
- To change one, say so explicitly, and append a new dated entry describing
  what replaced it and why. Never edit an entry in place.
- New settled decisions go at the bottom in the same format, so this file
  stays a record rather than a summary that silently drifts.
