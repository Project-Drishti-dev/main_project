const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const frontendDirectory = __dirname;
const outputDirectory = path.resolve(
  process.env.DRISHTI_BUILD_OUTPUT_DIR ||
    path.join(frontendDirectory, "dist"),
);

const pageFileNames = [
  "home.html",
  "screenings.html",
  "settings.html",
  "guide.html",
  "about.html",
  "profile.html",
  "result.html",
  "audit.html",
  "cases.html",
  "results.html",
];

const staticFiles = [
  "api.js",
  "status.js",
  "home.css",
  "home.js",
  "pages.css",
  "pages.js",
  "format.js",
  "screenings-list.js",
  "audit.js",
  "cases.js",
  "results.js",
  "results-metrics.js",
  "topbar-status.js",
  "preferences.js",
];

//: The two paths every page loads the UX4G runtime under.  They are the only
//:  names copied out of node_modules/, and the artefact check reads them from
//:  here rather than carrying a second list of them.
const htmlReplacements = [
  [
    "./node_modules/ux4g-web-components/styles/ux4g.css",
    "./assets/ux4g.css",
  ],
  [
    "./node_modules/ux4g-web-components/dist/runtime/design-system.js",
    "./assets/design-system.js",
  ],
];
//: The station every event is recorded under until a label is configured.
//:  Spelled as app/audit/emit.py's PLACEHOLDER_ACTOR, so the page and the
//:  trail cannot disagree about what "no station set" looks like.
const PLACEHOLDER_STATION_LABEL = "station-unset";

//: The one environment variable that names the station.  A label, never a
//:  person, a credential or a session: there is no sign-in to read one from.
const STATION_LABEL_ENV_VAR = "DRISHTI_STATION_LABEL";

class ShellRenderError extends Error {
  constructor(message) {
    super(message);
    this.name = "ShellRenderError";
  }
}

function ensureOutputIsInsideFrontend() {
  const relativePath = path.relative(frontendDirectory, outputDirectory);
  if (
    !relativePath ||
    relativePath === "." ||
    relativePath === ".." ||
    relativePath.startsWith(`..${path.sep}`) ||
    path.isAbsolute(relativePath)
  ) {
    throw new Error("Build output must be a child directory of frontend/.");
  }
}

/* The names this build reads out of frontend/, handed out as copies so a
   caller cannot reorder them (D168).  The cases in build.test.cjs hold
   both lists against the directory beside them. */
function buildFileNames() {
  return {
    pageFileNames: [...pageFileNames],
    staticFiles: [...staticFiles],
  };
}

/* The directory this build writes, so a caller serves what the build wrote
   rather than repeating the rule that chose it. */
function buildOutputDirectory() {
  return outputDirectory;
}

/* Every file this build is answerable for in the output directory, named the
   way the pages name them: relative, with "/" between the parts.  The artefact
   check reads this list instead of carrying a second one. */
function expectedArtefactNames() {
  return [
    ...pageFileNames,
    "index.html",
    ...staticFiles,
    "api-config.js",
    ...htmlReplacements.map(([, builtPath]) => builtPath.replace("./", "")),
  ];
}

// shell-tokens.js is the only reader of shell.html's placeholders, and this
// build is its first: the table decides what a page has to supply.
function loadShellTokens() {
  const windowStub = {};
  vm.runInNewContext(
    fs.readFileSync(path.join(frontendDirectory, "shell-tokens.js"), "utf8"),
    { window: windowStub },
  );
  return windowStub.DRISHTI_SHELL_TOKENS;
}

/* Reads the values a page fragment carries.  A token followed by a newline is
   a block that ends at {{/token}}; anything else is the rest of the line.
   Throws ShellRenderError naming the page and every token it left out. */
function readPageValues(pageSource, pageFileName, shellTokens) {
  const source = pageSource.replace(/\r\n/g, "\n");
  const values = new Map();
  let index = 0;

  while (index < source.length) {
    const start = source.indexOf("{{", index);
    const gap =
      start === -1 ? source.slice(index) : source.slice(index, start);
    if (gap.trim() !== "") {
      throw new ShellRenderError(
        `${pageFileName} carries text the shell has no slot for: ` +
          JSON.stringify(gap.trim().slice(0, 60)),
      );
    }
    if (start === -1) {
      break;
    }

    const end = source.indexOf("}}", start + 2);
    if (end === -1) {
      throw new ShellRenderError(
        `${pageFileName} carries an unclosed placeholder.`,
      );
    }
    const name = source.slice(start + 2, end);
    if (shellTokens.isToken(name) === false) {
      throw new ShellRenderError(
        `${pageFileName} carries a placeholder the shell does not fill: ` +
          `{{${name}}}.`,
      );
    }

    const afterOpening = end + 2;
    let value;
    if (source[afterOpening] === "\n") {
      const closing = `{{/${name}}}`;
      const closingAt = source.indexOf(closing, afterOpening);
      if (closingAt === -1) {
        throw new ShellRenderError(
          `${pageFileName} opens {{${name}}} and never closes it.`,
        );
      }
      value = source.slice(afterOpening + 1, closingAt);
      index = closingAt + closing.length;
    } else {
      const lineEnd = source.indexOf("\n", afterOpening);
      index = lineEnd === -1 ? source.length : lineEnd;
      value = source.slice(afterOpening, index);
    }
    values.set(name, value.trim());
  }

  const missing = shellTokens
    .tokenNames()
    .filter((name) => !values.has(name));
  if (missing.length > 0) {
    throw new ShellRenderError(
      `${pageFileName} is missing the shell tokens it must supply: ` +
        `${missing.join(", ")}.`,
    );
  }
  return values;
}

/* Fills shell.html with one page's values: the nav section the page owns keeps
   its body, every other nav section is dropped whole. */
function renderPage(pageSource, pageFileName) {
  const shellTokens = loadShellTokens();
  const values = readPageValues(pageSource, pageFileName, shellTokens);
  let html = fs
    .readFileSync(path.join(frontendDirectory, "shell.html"), "utf8")
    .replace(/\r\n/g, "\n");

  const activeNavKey = values.get("activeNavKey");
  try {
    shellTokens.conditionalName(activeNavKey);
  } catch {
    throw new ShellRenderError(
      `${pageFileName} names an active nav key the shell does not carry: ` +
        `${JSON.stringify(activeNavKey)}.`,
    );
  }

  for (const navKey of shellTokens.navKeys()) {
    const name = shellTokens.conditionalName(navKey);
    const opening = `{{#${name}}}`;
    const closing = `{{/${name}}}`;
    if (!html.includes(opening) || !html.includes(closing)) {
      throw new ShellRenderError(
        `shell.html has no ${name} section to fill.`,
      );
    }
    const section = new RegExp(
      `${opening.replace(/\./g, "\\.")}[\\s\\S]*?` +
        `${closing.replace(/\./g, "\\.")}`,
      "g",
    );
    html =
      navKey === activeNavKey
        ? html.replaceAll(opening, "").replaceAll(closing, "")
        : html.replaceAll(section, "");
  }

  for (const name of shellTokens.tokenNames()) {
    html = html.replaceAll(`{{${name}}}`, values.get(name));
  }
  if (html.includes("{{")) {
    throw new ShellRenderError(
      "shell.html still carries a placeholder no value filled.",
    );
  }
  return html;
}

/* The station this build is deployed as, or the placeholder when nobody
   configured one.  Trimmed, and an empty or whitespace value is the same as
   unset rather than a blank station on the record. */
function getStationLabel() {
  const configured = process.env[STATION_LABEL_ENV_VAR]?.trim();
  return configured || PLACEHOLDER_STATION_LABEL;
}

function getApiBaseUrl() {
  const configuredUrl = process.env.DRISHTI_API_BASE_URL?.trim() || "";
  if (!configuredUrl) {
    if (process.env.CF_PAGES) {
      console.warn(
        "DRISHTI_API_BASE_URL is not set; hosted image analysis will stay disabled.",
      );
    }
    return "";
  }

  let parsedUrl;
  try {
    parsedUrl = new URL(configuredUrl);
  } catch {
    throw new Error("DRISHTI_API_BASE_URL must be a valid HTTPS origin.");
  }

  if (
    parsedUrl.protocol !== "https:" ||
    parsedUrl.username ||
    parsedUrl.password ||
    parsedUrl.pathname !== "/" ||
    parsedUrl.search ||
    parsedUrl.hash
  ) {
    throw new Error(
      "DRISHTI_API_BASE_URL must be an HTTPS origin without a path.",
    );
  }

  return parsedUrl.origin;
}

function buildSite() {
  ensureOutputIsInsideFrontend();
  fs.mkdirSync(outputDirectory, { recursive: true });

  for (const fileName of staticFiles) {
    fs.copyFileSync(
      path.join(frontendDirectory, fileName),
      path.join(outputDirectory, fileName),
    );
  }

  const assetsDirectory = path.join(outputDirectory, "assets");
  fs.mkdirSync(assetsDirectory, { recursive: true });
  const ux4gDirectory = path.join(
    frontendDirectory,
    "node_modules",
    "ux4g-web-components",
  );
  fs.copyFileSync(
    path.join(ux4gDirectory, "styles", "ux4g.css"),
    path.join(assetsDirectory, "ux4g.css"),
  );
  fs.copyFileSync(
    path.join(ux4gDirectory, "dist", "runtime", "design-system.js"),
    path.join(assetsDirectory, "design-system.js"),
  );

  for (const fileName of pageFileNames) {
    let html = renderPage(
      fs.readFileSync(path.join(frontendDirectory, fileName), "utf8"),
      fileName,
    );
    for (const [sourcePath, builtPath] of htmlReplacements) {
      if (!html.includes(sourcePath)) {
        throw new Error(
          `Expected UX4G asset reference was not found in ${fileName}.`,
        );
      }
      html = html.replaceAll(sourcePath, builtPath);
    }
    fs.writeFileSync(path.join(outputDirectory, fileName), html);
  }

  fs.copyFileSync(
    path.join(outputDirectory, "home.html"),
    path.join(outputDirectory, "index.html"),
  );

  const apiBaseUrl = getApiBaseUrl();
  const apiConfig = `(() => {
  const localHosts = new Set(["localhost", "127.0.0.1"]);
  const isLocalDevelopment = localHosts.has(window.location.hostname);

  window.DRISHTI_CONFIG = {
    apiBaseUrl: isLocalDevelopment
      ? "http://localhost:8080"
      : ${JSON.stringify(apiBaseUrl)},
    stationLabel: ${JSON.stringify(getStationLabel())},
  };
})();
`;
  fs.writeFileSync(
    path.join(outputDirectory, "api-config.js"),
    apiConfig,
    "utf8",
  );

  console.log(`Static site built in ${path.relative(frontendDirectory, outputDirectory)}.`);
}

module.exports = {
  PLACEHOLDER_STATION_LABEL,
  STATION_LABEL_ENV_VAR,
  ShellRenderError,
  buildFileNames,
  buildOutputDirectory,
  buildSite,
  expectedArtefactNames,
  renderPage,
};

if (require.main === module) {
  try {
    buildSite();
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
