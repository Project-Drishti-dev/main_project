# Private-browsing check

Opened home.html in a private (off-the-record) Chromium context and read
back what the browser actually did. Produced by `npm run private-check` in
`frontend/`.

| check | answer |
| --- | --- |
| private browser context | yes |
| localStorage on the page | available |
| upload requests after choosing a file | 0 |
| upload requests after clicking submit | 1 |
| localStorage in the opaque-origin frame | refused with SecurityError |
| preferences loaded without localStorage | yes |
| theme written without localStorage | dark |
| uncaught console errors | 0 |

## Verdict

Nothing to report: choosing a file sent nothing, clicking submit sent one
request, and preferences.js loaded and wrote with localStorage unavailable.
