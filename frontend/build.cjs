const fs = require("node:fs");
const path = require("node:path");

const frontendDirectory = __dirname;
const outputDirectory = path.resolve(
  process.env.DRISHTI_BUILD_OUTPUT_DIR ||
    path.join(frontendDirectory, "dist"),
);

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

  const staticFiles = [
    "home.html",
    "home.css",
    "home.js",
  ];
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
  for (const fileName of ["home.html"]) {
    let html = fs.readFileSync(
      path.join(outputDirectory, fileName),
      "utf8",
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

try {
  buildSite();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
