# Deployed check

Run at 2026-10-05T17:15:05.534Z against the live deployment, with a real
Chromium on a throwaway profile. Only what a network panel shows is
recorded: methods, urls, statuses and CORS headers. No response body,
no image bytes and no extracted text.

## API

- Base URL: `https://main-project-888645637790.asia-south1.run.app`
- `GET /health` -> 200 `{"status":"ok"}`
- `GET /api/version` -> 404 (the revision serving traffic predates this route)

## Deployed `api-config.js`

| url | status | baked-in `apiBaseUrl` |
| --- | --- | --- |
| https://project-drishti.pages.dev/api-config.js | 200 | `https://main-project-888645637790.asia-south1.run.app` |
| https://project-drishti.tech/api-config.js | 200 | _(empty)_ |
| http://project-drishti.tech/api-config.js | 200 | _(empty)_ |

## Origins the API actually allows

Read from `OPTIONS /api/screenings` answered by the revision that is
actually serving traffic, so this is the deployed allowlist rather than
the one written down anywhere.

| probe `Origin` | status | `access-control-allow-origin` |
| --- | --- | --- |
| `https://project-drishti.pages.dev` | 200 | https://project-drishti.pages.dev |
| `https://project-drishti.tech` | 400 | (absent) |
| `http://project-drishti.tech` | 200 | http://project-drishti.tech |
| `https://project-drishti-dev.github.io` | 200 | https://project-drishti-dev.github.io |
| `https://Cosmiczen7.github.io` | 200 | https://Cosmiczen7.github.io |
| `https://cosmiczen7.github.io` | 400 | (absent) |
| `http://localhost:5500` | 400 | (absent) |
| `https://not-allowed.example` | 400 | (absent) |

Allowed: 4 of 8 probed origins.

## Image upload, per deployed origin

| site | navigated | `location.origin` | preview | POST | responses (allow-origin) | blocked |
| --- | --- | --- | --- | --- | --- | --- |
| cloudflare-pages | https://project-drishti.pages.dev/home | `https://project-drishti.pages.dev` | true | 1 | 422 https://main-project-888645637790.asia-south1.run.app/api/analyze [allow-origin: https://project-drishti.pages.dev] | -- |
| tech | https://project-drishti.tech/home | `https://project-drishti.tech` | true | 0 | -- | -- |
| tech-http | http://project-drishti.tech/home | `https://project-drishti.tech` | true | 0 | -- | -- |

Sites that reached the API with an upload: 1 of 3.

A 4xx from the API is the CORS layer having done its job: the browser
delivered the request and the application answered it. Only a blocked
entry, or a response with no allow-origin header, is a CORS failure.

## Why a deployed origin fails

Read off the run above, so neither cause is assumed.

- https://project-drishti.tech never reaches the API: its api-config.js bakes in no base url, so the page issues no request at all. That is a build-time setting (DRISHTI_API_BASE_URL), not CORS, and only a redeploy changes it.
- https://project-drishti.tech would be refused even after that fix: the revision serving traffic allows https://project-drishti.pages.dev, http://project-drishti.tech, https://project-drishti-dev.github.io, https://Cosmiczen7.github.io, and https://project-drishti.tech is not among them. Add https://project-drishti.tech to CORS_ORIGINS and deploy a new revision; the variable alone changes nothing until one serves traffic.

## Findings

- [finding] api_base_url_empty (https://project-drishti.tech/api-config.js): api-config.js bakes in no API origin, so the page cannot call the API at all
- [finding] api_base_url_empty (http://project-drishti.tech/api-config.js): api-config.js bakes in no API origin, so the page cannot call the API at all
- [finding] page_makes_no_api_request (tech): https://project-drishti.tech loaded and rendered the page but issued 0 API request(s): api-config.js gave it no API origin
- [finding] page_makes_no_api_request (tech-http): https://project-drishti.tech loaded and rendered the page but issued 0 API request(s): api-config.js gave it no API origin
