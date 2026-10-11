const fs = require("node:fs");
const path = require("node:path");

const { buildOutputDirectory, expectedArtefactNames } = require("../build.cjs");

const frontendDirectory = path.resolve(__dirname, "..");

class ArtefactsMissingError extends Error {
  constructor(message, missingNames) {
    super(message);
    this.name = "ArtefactsMissingError";
    this.missingNames = missingNames;
  }
}

function relativeToFrontend(directory) {
  const relativePath = path.relative(frontendDirectory, directory);
  return relativePath && !relativePath.startsWith("..") ? relativePath : directory;
}

/* A name the directory does not hold as a file with bytes in it.  A zero-byte
   page is a page the copy failed to make, which is the same fault as none. */
function artefactIsMissing(directory, name) {
  const artefact = path.join(directory, name);
  if (!fs.existsSync(artefact)) {
    return true;
  }
  const stats = fs.statSync(artefact);
  return !stats.isFile() || stats.size === 0;
}

function missingArtefacts(directory, expectedNames = expectedArtefactNames()) {
  return expectedNames.filter((name) => artefactIsMissing(directory, name));
}

/* Fails naming every artefact that is missing or empty rather than the first:
   a build that dropped three files should not need three runs.  The expected
   names are the build's own (D219), so this cannot agree with a list of its
   own that fell behind. */
function checkArtefacts(directory = buildOutputDirectory()) {
  const expectedNames = expectedArtefactNames();
  if (!fs.existsSync(directory)) {
    throw new ArtefactsMissingError(
      `${relativeToFrontend(directory)}/ holds no build output; ` +
        "run `npm run build` first.",
      expectedNames,
    );
  }

  const missingNames = missingArtefacts(directory, expectedNames);
  if (missingNames.length > 0) {
    throw new ArtefactsMissingError(
      `${relativeToFrontend(directory)}/ is missing ${missingNames.length} of ` +
        `${expectedNames.length} build artefacts: ${missingNames.join(", ")}.`,
      missingNames,
    );
  }
  return directory;
}

module.exports = {
  ArtefactsMissingError,
  checkArtefacts,
  missingArtefacts,
};

if (require.main === module) {
  try {
    const checked = checkArtefacts();
    console.log(
      `All ${expectedArtefactNames().length} build artefacts are in ` +
        `${relativeToFrontend(checked)}/.`,
    );
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}