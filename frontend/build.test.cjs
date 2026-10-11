const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { buildFileNames, renderPage, ShellRenderError } = require("./build.cjs");

const frontendDirectory = path.resolve(__dirname);
const { pageFileNames, staticFiles } = buildFileNames();
const shippedAssetPaths = [
  ["./node_modules/ux4g-web-components/styles/ux4g.css", "./assets/ux4g.css"],
  [
    "./node_modules/ux4g-web-components/dist/runtime/design-system.js",
    "./assets/design-system.js",
  ],
];

const legacyAuthArtifacts = [
  "register.html",
  "login.css",
  "login.js",
  "reset-flow.js",
  "register.css",
  "register.js",
];

function readSource(fileName) {
  return fs.readFileSync(path.join(frontendDirectory, fileName), "utf8");
}

/* The shell's own bytes as the build ships them.  A run is a maximal stretch of
   shell.html carrying no placeholder; a nav section counts as one placeholder
   here, so the bytes either side of it are runs of their own and hold whether
   the section was kept whole or dropped whole. */
function shellRuns() {
  let shell = readSource("shell.html").replace(/\r\n/g, "\n");
  for (const [sourcePath, builtPath] of shippedAssetPaths) {
    assert.ok(
      shell.includes(sourcePath),
      `shell.html should still carry ${sourcePath}`,
    );
    shell = shell.replaceAll(sourcePath, builtPath);
  }
  shell = shell.replace(
    /\{\{#nav\.[a-z]+\}\}[\s\S]*?\{\{\/nav\.[a-z]+\}\}/g,
    "{{nav}}",
  );
  return shell.split(/\{\{[^{}]*\}\}/).filter((run) => run.trim() !== "");
}

function withBuildOutput(environment, assertBuild) {
  const outputDirectory = fs.mkdtempSync(
    path.join(frontendDirectory, ".build-test-"),
  );

  try {
    const result = spawnSync(
      process.execPath,
      [path.join(frontendDirectory, "build.cjs")],
      {
        cwd: frontendDirectory,
        encoding: "utf8",
        env: {
          ...process.env,
          CF_PAGES: "",
          DRISHTI_API_BASE_URL: "",
          DRISHTI_BUILD_OUTPUT_DIR: outputDirectory,
          ...environment,
        },
      },
    );
    assertBuild({ outputDirectory, result });
  } finally {
    const resolvedOutputDirectory = path.resolve(outputDirectory);
    assert.ok(
      resolvedOutputDirectory.startsWith(`${frontendDirectory}${path.sep}`),
      "test build output must remain inside the frontend workspace",
    );
    fs.rmSync(resolvedOutputDirectory, { recursive: true, force: true });
  }
}

test("static build publishes the screening demo without account flows", () => {
  withBuildOutput(
    {
      CF_PAGES: "1",
      DRISHTI_API_BASE_URL: "https://quality-api.example.run.app",
    },
    ({ outputDirectory, result }) => {
      assert.equal(result.status, 0, result.stderr);

      for (const fileName of [
        "index.html",
        "home.html",
        "api.js",
        "home.css",
        "home.js",
        "pages.css",
        "pages.js",
        "status.js",
        "topbar-status.js",
        "preferences.js",
        "screenings.html",
        "settings.html",
        "guide.html",
        "about.html",
        "profile.html",
        "api-config.js",
      ]) {
        assert.ok(
          fs.existsSync(path.join(outputDirectory, fileName)),
          `build should include ${fileName}`,
        );
      }

      for (const fileName of legacyAuthArtifacts) {
        assert.equal(
          fs.existsSync(path.join(outputDirectory, fileName)),
          false,
          `build must not publish ${fileName}`,
        );
      }

      const homeHtml = fs.readFileSync(
        path.join(outputDirectory, "home.html"),
        "utf8",
      );
      assert.equal(
        fs.readFileSync(path.join(outputDirectory, "index.html"), "utf8"),
        homeHtml,
        "the public root should open the screening demo directly",
      );

      for (const fileName of ["index.html", ...pageFileNames]) {
        const html = fs.readFileSync(
          path.join(outputDirectory, fileName),
          "utf8",
        );
        assert.match(html, /href="\.\/assets\/ux4g\.css"/);
        assert.match(html, /src="\.\/assets\/design-system\.js"/);
        assert.doesNotMatch(html, /node_modules/);
        assert.doesNotMatch(
          html,
          /type="password"|Forgot password\?|Personnel ID|Verification code|Register/,
        );
      }

      for (const fileName of pageFileNames) {
        const html = fs.readFileSync(
          path.join(outputDirectory, fileName),
          "utf8",
        );
        assert.match(
          html,
          /href="\.\/pages\.css"/,
          `${fileName} should load the shared page stylesheet`,
        );
        assert.match(
          html,
          /src="\.\/preferences\.js"/,
          `${fileName} should load the shared preferences script`,
        );
        assert.match(
          html,
          fileName === "home.html" ? /src="\.\/home\.js"/ : /src="\.\/pages\.js"/,
          `${fileName} should load its page script`,
        );
      }

      assert.ok(
        fs.existsSync(path.join(outputDirectory, "assets", "ux4g.css")),
      );
      assert.ok(
        fs.existsSync(path.join(outputDirectory, "assets", "design-system.js")),
      );
      const apiConfig = fs.readFileSync(
        path.join(outputDirectory, "api-config.js"),
        "utf8",
      );
      assert.match(apiConfig, /https:\/\/quality-api\.example\.run\.app/);
      assert.match(apiConfig, /http:\/\/localhost:8080/);
    },
  );
});

/* The station is configuration, not a sign-in: there is nothing to log into,
   so the label is read from the environment the build already runs in and
   written beside the API origin it was already reading. */

test("the configured station label is written into api-config.js trimmed", () => {
  withBuildOutput(
    { DRISHTI_STATION_LABEL: "  BLR-GATE-3  " },
    ({ outputDirectory, result }) => {
      assert.equal(result.status, 0, result.stderr);
      const apiConfig = fs.readFileSync(
        path.join(outputDirectory, "api-config.js"),
        "utf8",
      );
      assert.match(apiConfig, /stationLabel: "BLR-GATE-3"/);
      assert.doesNotMatch(apiConfig, /stationLabel: " /);
    },
  );
});

test("an unset or blank station label is the placeholder the trail already stamps", () => {
  for (const configured of ["", "   "]) {
    withBuildOutput(
      { DRISHTI_STATION_LABEL: configured },
      ({ outputDirectory, result }) => {
        assert.equal(result.status, 0, result.stderr);
        const apiConfig = fs.readFileSync(
          path.join(outputDirectory, "api-config.js"),
          "utf8",
        );
        assert.match(apiConfig, /stationLabel: "station-unset"/);
      },
    );
  }
});
test("static build reports when the hosted API origin is not configured", () => {
  withBuildOutput(
    { CF_PAGES: "1", DRISHTI_API_BASE_URL: "" },
    ({ outputDirectory, result }) => {
      assert.equal(result.status, 0, result.stderr);
      assert.match(
        result.stderr,
        /DRISHTI_API_BASE_URL is not set/,
      );
      assert.match(
        fs.readFileSync(path.join(outputDirectory, "api-config.js"), "utf8"),
        /apiBaseUrl: isLocalDevelopment\s+\? "http:\/\/localhost:8080"\s+: ""/,
      );
    },
  );
});

/* Every page in dist/ carries the shell, and carries it as the same bytes. */

test("every page in dist/ ships the shell markup byte for byte", () => {
  const runs = shellRuns();
  assert.ok(runs.length >= 12, "the shell should hold runs of its own markup");

  withBuildOutput({}, ({ outputDirectory, result }) => {
    assert.equal(result.status, 0, result.stderr);

    const builtPages = fs
      .readdirSync(outputDirectory)
      .filter((name) => name.endsWith(".html"))
      .sort();
    assert.deepEqual(builtPages, [...pageFileNames, "index.html"].sort());

    for (const builtPage of builtPages) {
      const html = fs.readFileSync(
        path.join(outputDirectory, builtPage),
        "utf8",
      );
      for (const run of runs) {
        assert.ok(
          html.includes(run),
          `${builtPage} is missing shell markup: ` +
            JSON.stringify(run.trim().slice(0, 80)),
        );
      }
    }
  });
});

/* The nav item a page marks current, counted inside #sidebar-navigation.  The
   sidebar profile shortcut sits outside that nav and may carry aria-current
   too, so the count is taken from the nav block and not from the page. */
function assertOneActiveNavItem(html, pageName) {
  const nav = html.match(
    /<nav\b[^>]*id="sidebar-navigation"[\s\S]*?<\/nav>/,
  );
  assert.ok(nav, `${pageName} should ship the workspace navigation`);

  const activeNavKey = nav[0].match(/data-active-nav="([^"]*)"/);
  assert.ok(activeNavKey, `${pageName} should name its active nav key`);
  assert.notEqual(
    activeNavKey[1],
    "",
    `${pageName} should name a nav key rather than an empty one`,
  );

  const currentNavKeys = [];
  for (const anchor of nav[0].matchAll(/<a\b[^>]*>/g)) {
    const navKey = anchor[0].match(/data-nav="([^"]*)"/);
    assert.ok(
      navKey,
      `${pageName} should mark every nav link with a data-nav key`,
    );
    if (anchor[0].includes('aria-current="page"')) {
      currentNavKeys.push(navKey[1]);
    }
  }
  assert.deepEqual(
    currentNavKeys,
    [activeNavKey[1]],
    `${pageName} should mark exactly one nav item active, and it should be ` +
      `${activeNavKey[1]}`,
  );
}

test("every page in dist/ marks exactly one nav item active", () => {
  withBuildOutput({}, ({ outputDirectory, result }) => {
    assert.equal(result.status, 0, result.stderr);

    const builtPages = fs
      .readdirSync(outputDirectory)
      .filter((name) => name.endsWith(".html"))
      .sort();
    assert.deepEqual(builtPages, [...pageFileNames, "index.html"].sort());

    for (const builtPage of builtPages) {
      assertOneActiveNavItem(
        fs.readFileSync(path.join(outputDirectory, builtPage), "utf8"),
        builtPage,
      );
    }
  });
});

/* The check is held to the two ways the marker can go: none, or two. */
test("a page marking no nav item, or two, fails the active nav check", () => {
  const home = renderPage(readSource("home.html"), "home.html");
  const marksNothing = home.replaceAll(' aria-current="page"', "");
  const marksTwice = home.replace(
    'data-nav="guide"',
    'data-nav="guide" aria-current="page"',
  );
  assert.notEqual(marksNothing, home, "the case must drop the marker");
  assert.notEqual(marksTwice, home, "the case must add a second marker");

  for (const page of [marksNothing, marksTwice]) {
    assert.throws(
      () => assertOneActiveNavItem(page, "home.html"),
      (error) => {
        assert.ok(error instanceof assert.AssertionError, "the check must fail");
        assert.match(
          error.message,
          /home\.html should mark exactly one nav item active/,
        );
        return true;
      },
    );
  }
});
/* The build refuses a fragment it cannot fill, and names what is wrong. */

test("a page missing a shell token fails the build and names the page and the token", () => {
  const withoutActiveNav = readSource("home.html").replace(
    "{{activeNavKey}}home\n",
    "",
  );
  assert.notEqual(withoutActiveNav, readSource("home.html"), "the case must drop a token");

  assert.throws(
    () => renderPage(withoutActiveNav, "home.html"),
    (error) => {
      assert.ok(error instanceof ShellRenderError, "the refusal must be named");
      assert.equal(error.name, "ShellRenderError");
      assert.match(error.message, /^home\.html is missing the shell tokens/);
      assert.match(error.message, /\bactiveNavKey\b/);
      assert.doesNotMatch(error.message, /pageTitle/, "only what is missing is named");
      return true;
    },
  );
});

test("a token block nobody closed fails the build", () => {
  const unclosed = readSource("home.html").replace("{{/content}}", "");

  assert.throws(
    () => renderPage(unclosed, "home.html"),
    (error) => {
      assert.equal(error.name, "ShellRenderError");
      assert.match(error.message, /home\.html opens \{\{content\}\} and never closes it/);
      return true;
    },
  );
});

test("a placeholder the shell does not fill is refused by name", () => {
  const undeclared = readSource("home.html").replace(
    "{{content}}",
    "{{pageAccent}}\nsaffron\n{{/pageAccent}}\n{{content}}",
  );

  assert.throws(
    () => renderPage(undeclared, "home.html"),
    (error) => {
      assert.equal(error.name, "ShellRenderError");
      assert.match(error.message, /home\.html carries a placeholder the shell does not fill/);
      assert.match(error.message, /pageAccent/);
      return true;
    },
  );
});

test("page text outside every token is refused rather than dropped", () => {
  const stray = `${readSource("home.html")}<p>written outside the shell</p>\n`;

  assert.throws(
    () => renderPage(stray, "home.html"),
    (error) => {
      assert.equal(error.name, "ShellRenderError");
      assert.match(error.message, /home\.html carries text the shell has no slot for/);
      assert.match(error.message, /outside the shell/);
      return true;
    },
  );
});

test("an active nav key the shell does not carry is refused", () => {
  const wrongKey = readSource("home.html").replace(
    "{{activeNavKey}}home",
    "{{activeNavKey}}Home",
  );

  assert.throws(
    () => renderPage(wrongKey, "home.html"),
    (error) => {
      assert.equal(error.name, "ShellRenderError");
      assert.match(error.message, /home\.html names an active nav key the shell does not carry/);
      assert.match(error.message, /"Home"/);
      return true;
    },
  );
});

/* The sidebar as one block, so a link is read from the sidebar and not from the
   page around it.  The brand link and the profile shortcut sit outside
   #sidebar-navigation, so the whole aside is taken rather than the nav alone. */
function sidebarMarkup(html, pageName) {
  const sidebar = html.match(/<aside\b[^>]*id="app-sidebar"[\s\S]*?<\/aside>/);
  assert.ok(sidebar, `${pageName} should ship the workspace sidebar`);
  return sidebar[0];
}

/* Every sidebar link resolves to a file the build wrote.  The check is given the
   directory the build wrote and resolves into it, so a link to a page the build
   stopped writing fails it, as does a link out of that directory. */
function assertSidebarLinksResolve(html, pageName, outputDirectory) {
  const builtRoot = path.resolve(outputDirectory);
  const hrefs = [
    ...sidebarMarkup(html, pageName).matchAll(/<a\b[^>]*\bhref="([^"]*)"/g),
  ].map((match) => match[1]);
  assert.ok(hrefs.length > 0, `${pageName} should ship sidebar links to check`);

  for (const href of hrefs) {
    const resolved = path.resolve(builtRoot, href);
    assert.ok(
      resolved.startsWith(`${builtRoot}${path.sep}`) &&
        fs.existsSync(resolved) &&
        fs.statSync(resolved).isFile(),
      `${pageName} sidebar link ${href} resolves to no file in the build`,
    );
  }
}

test("every sidebar link in dist/ resolves to a file the build wrote", () => {
  withBuildOutput({}, ({ outputDirectory, result }) => {
    assert.equal(result.status, 0, result.stderr);

    const builtPages = fs
      .readdirSync(outputDirectory)
      .filter((name) => name.endsWith(".html"))
      .sort();
    assert.deepEqual(builtPages, [...pageFileNames, "index.html"].sort());

    for (const builtPage of builtPages) {
      assertSidebarLinksResolve(
        fs.readFileSync(path.join(outputDirectory, builtPage), "utf8"),
        builtPage,
        outputDirectory,
      );
    }
  });
});

/* A dead link is what this check exists for, so it is shown rather than assumed:
   one href is the only change, and the file it names is absent from the build. */
test("a sidebar link to a file the build does not write fails the link check", () => {
  withBuildOutput({}, ({ outputDirectory, result }) => {
    assert.equal(result.status, 0, result.stderr);

    const home = fs.readFileSync(
      path.join(outputDirectory, "home.html"),
      "utf8",
    );
    const deadLink = home.replace(
      'href="./guide.html"',
      'href="./dashboard.html"',
    );
    assert.equal(
      sidebarMarkup(deadLink, "home.html"),
      sidebarMarkup(home, "home.html").replace(
        'href="./guide.html"',
        'href="./dashboard.html"',
      ),
      "the case must break a link inside the sidebar",
    );
    assert.equal(
      fs.existsSync(path.join(outputDirectory, "dashboard.html")),
      false,
      "the case must point at a file the build does not write",
    );

    assertSidebarLinksResolve(home, "home.html", outputDirectory);
    assert.throws(
      () => assertSidebarLinksResolve(deadLink, "home.html", outputDirectory),
      (error) => {
        assert.ok(error instanceof assert.AssertionError, "the check must fail");
        assert.match(
          error.message,
          /home\.html sidebar link \.\/dashboard\.html resolves to no file in the build/,
        );
        return true;
      },
    );
  });
});
/* The two lists in build.cjs against the directory they read.  21.5 to 21.7
   read what the build wrote; this reads the source, so a page written without
   its place in the lists fails here rather than after the build is trusted. */

/* The two names the build writes rather than copies, and so asks for by name:
   index.html is the rendered home page and api-config.js comes from the
   environment.  Neither is read out of frontend/. */
const buildWrittenFileNames = new Set(["api-config.js", "index.html"]);

/* The assets a page or the shell loads, as names without the "./".  A path
   carrying a directory is not one of ours: the two UX4G paths the shell still
   names are rewritten into assets/ and copied by the build itself. */
function localAssetNames(sources) {
  const names = new Set();
  for (const source of sources) {
    for (const [, href] of source.matchAll(/(?:src|href)="\.\/([^"#]+)"/g)) {
      if (/^[A-Za-z0-9._-]+\.(?:js|css)$/.test(href)) {
        names.add(href);
      }
    }
  }
  return names;
}

function pageSources() {
  return [
    readSource("shell.html"),
    ...pageFileNames.map((fileName) => readSource(fileName)),
  ];
}

/* Every .html in frontend/ is a fragment the build renders, and every page it
   renders is a fragment there.  The two sides are compared as sets because a
   second copy of the list is the drift this exists to stop.  shell.html is the
   one .html left out: it is the template the build fills for every page rather
   than a page it renders, so it carries placeholders where a fragment supplies
   them, and D168 already holds it apart from the pages. */
function assertListedPagesMatchTheDirectory(listedNames) {
  const fragments = fs
    .readdirSync(frontendDirectory)
    .filter(
      (name) =>
        name.endsWith(".html") &&
        name !== "shell.html" &&
        !buildWrittenFileNames.has(name),
    )
    .sort();
  assert.deepEqual(
    fragments,
    [...listedNames].sort(),
    "every page fragment in frontend/ is rendered by the build, and every " +
      "page the build renders is a fragment in frontend/",
  );
}

/* What the pages load is what the build copies, in both directions: a script
   left out of staticFiles ships as a 404 on a page the shell rendered, and a
   copied file no page loads is weight in dist/ nothing else would notice.
   api-config.js is the one name a page loads that the build does not copy. */
function assertListedAssetsMatchThePages(referencedNames, listedNames) {
  assert.deepEqual(
    [...referencedNames]
      .filter((name) => !buildWrittenFileNames.has(name))
      .sort(),
    [...listedNames].sort(),
    "every asset a page loads is copied into the build, and the build copies " +
      "nothing a page does not load",
  );
}

function assertFails(check, messagePattern, what) {
  assert.throws(check, (error) => {
    assert.ok(
      error instanceof assert.AssertionError,
      `${what} must fail the check`,
    );
    assert.match(error.message, messagePattern, `${what} must be named`);
    return true;
  });
}

test("every page fragment in frontend/ is a page the build renders", () => {
  assertListedPagesMatchTheDirectory(pageFileNames);
});

test("the build copies what the pages load, and nothing else", () => {
  const referenced = localAssetNames(pageSources());
  for (const name of referenced) {
    assert.ok(
      fs.existsSync(path.join(frontendDirectory, name)),
      `a page loads ${name}, which is not in frontend/`,
    );
  }
  assertListedAssetsMatchThePages(referenced, staticFiles);
});

/* Both checks are held to the four ways the lists fall behind: a page the
   build stops rendering, a page it is asked to render that does not exist, a
   script a page loads that the build does not copy, and a file copied that no
   page loads.  Each claim is shown passing first, so neither check can pass by
   refusing everything. */
test("a page or an asset the lists do not carry fails the check", () => {
  const referenced = localAssetNames(pageSources());

  assertListedPagesMatchTheDirectory(pageFileNames);
  assertListedAssetsMatchThePages(referenced, staticFiles);

  assertFails(
    () =>
      assertListedPagesMatchTheDirectory(
        pageFileNames.filter((name) => name !== "guide.html"),
      ),
    /guide\.html/,
    "a page the build stopped rendering",
  );
  assertFails(
    () => assertListedPagesMatchTheDirectory([...pageFileNames, "report.html"]),
    /report\.html/,
    "a page the build was asked to render and does not hold",
  );

  const withScreeningScript = new Set([...referenced, "screening.js"]);
  assertFails(
    () => assertListedAssetsMatchThePages(withScreeningScript, staticFiles),
    /screening\.js/,
    "a page script the build does not copy",
  );
  assertListedAssetsMatchThePages(withScreeningScript, [
    ...staticFiles,
    "screening.js",
  ]);

  assertFails(
    () =>
      assertListedAssetsMatchThePages(referenced, [...staticFiles, "overlay.js"]),
    /overlay\.js/,
    "a file the build copies and no page loads",
  );
});