const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const FORMAT_PATH = path.join(__dirname, "format.js");
const source = fs.readFileSync(FORMAT_PATH, "utf8");

const REFERENCE = "2026-10-04T09:00:00Z";
const SECOND_MS = 1000;

function loadFormat() {
  const windowStub = {};
  vm.runInNewContext(source, { window: windowStub });
  return windowStub.DRISHTI_FORMAT;
}

function refuses(call, fragment) {
  assert.throws(call, (error) => {
    assert.equal(error.name, "FormatError");
    if (fragment !== undefined) {
      assert.ok(
        error.message.includes(fragment),
        "message was " + JSON.stringify(error.message),
      );
    }
    return true;
  });
}

function at(secondsBeforeReference) {
  return new Date(
    Date.parse(REFERENCE) - secondsBeforeReference * SECOND_MS,
  ).toISOString();
}

function rel(value, now) {
  return loadFormat().formatRelativeTime(value, now);
}

test("each of the three bands has one display label", () => {
  const format = loadFormat();
  assert.equal(format.bandLabel("low"), "Low Risk");
  assert.equal(format.bandLabel("review"), "Review");
  assert.equal(format.bandLabel("high"), "High Risk");
});

test("the label table is exactly the three bands the engine bands in", () => {
  const format = loadFormat();
  assert.deepEqual(Object.keys(format.BAND_LABELS).sort(), [
    "high",
    "low",
    "review",
  ]);
  for (const band of Object.keys(format.BAND_LABELS)) {
    assert.equal(format.bandLabel(band), format.BAND_LABELS[band]);
  }
});

test("a band the engine cannot produce is refused, not guessed", () => {
  const format = loadFormat();
  refuses(() => format.bandLabel("critical"), "critical");
  refuses(() => format.bandLabel("LOW"), "LOW");
  refuses(() => format.bandLabel(" low"), "Not a risk band");
  refuses(() => format.bandLabel(""), "Not a risk band");
  refuses(() => format.bandLabel(null), "null");
  refuses(() => format.bandLabel(undefined));
  refuses(() => format.bandLabel(1));
  refuses(() => format.bandLabel(["low"]));
});

test("a whole score prints without a decimal", () => {
  const format = loadFormat();
  assert.equal(format.formatScore(0), "0");
  assert.equal(format.formatScore(34), "34");
  assert.equal(format.formatScore(92), "92");
  assert.equal(format.formatScore(100), "100");
});

test("a score prints one decimal place and no more", () => {
  const format = loadFormat();
  assert.equal(format.formatScore(73.5), "73.5");
  assert.equal(format.formatScore(34.5), "34.5");
  assert.equal(format.formatScore(73.46), "73.5");
  assert.equal(format.formatScore(0.04), "0");
  assert.equal(format.formatScore(99.99), "100");
});

test("both thresholds a band is read against are printable scores", () => {
  const format = loadFormat();
  assert.equal(format.formatScore(34), "34");
  assert.equal(format.formatScore(69), "69");
  assert.equal(format.formatScore(69.5), "69.5");
});

test("a score off the scale or not a number is refused", () => {
  const format = loadFormat();
  refuses(() => format.formatScore("92"), "finite number");
  refuses(() => format.formatScore(null), "finite number");
  refuses(() => format.formatScore(undefined), "finite number");
  refuses(() => format.formatScore(NaN), "finite number");
  refuses(() => format.formatScore(Infinity), "finite number");
  refuses(() => format.formatScore(-0.1), "between 0 and 100");
  refuses(() => format.formatScore(100.1), "between 0 and 100");
});

test("a stamp inside the last minute reads as just now", () => {
  assert.equal(rel(at(0), REFERENCE), "just now");
  assert.equal(rel(at(59), REFERENCE), "just now");
});

test("minutes read as a count once the minute is up", () => {
  assert.equal(rel(at(60), REFERENCE), "1 minute ago");
  assert.equal(rel(at(119), REFERENCE), "1 minute ago");
  assert.equal(rel(at(120), REFERENCE), "2 minutes ago");
  assert.equal(rel(at(59 * 60), REFERENCE), "59 minutes ago");
});

test("hours read as a count once the hour is up", () => {
  assert.equal(rel(at(3600), REFERENCE), "1 hour ago");
  assert.equal(rel(at(2 * 3600 - 1), REFERENCE), "1 hour ago");
  assert.equal(rel(at(2 * 3600), REFERENCE), "2 hours ago");
  assert.equal(rel(at(23 * 3600), REFERENCE), "23 hours ago");
});

test("days read as a count once the day is up", () => {
  assert.equal(rel(at(24 * 3600), REFERENCE), "1 day ago");
  assert.equal(rel(at(2 * 86400 - 1), REFERENCE), "1 day ago");
  assert.equal(rel(at(2 * 86400), REFERENCE), "2 days ago");
});

test("the ladder stops at days, because a month is not a fixed width", () => {
  assert.equal(rel(at(30 * 86400), REFERENCE), "30 days ago");
  assert.equal(rel(at(400 * 86400), REFERENCE), "400 days ago");
});

test("an offset, a naive stamp and epoch milliseconds read the same instant", () => {
  const reference = "2026-10-04T09:00:00Z";
  const expected = "30 minutes ago";
  assert.equal(rel("2026-10-04T14:00:00+05:30", reference), expected);
  assert.equal(rel("2026-10-04T08:30:00", reference), expected);
  assert.equal(rel("2026-10-04T08:30:00Z", reference), expected);
  assert.equal(rel(Date.parse("2026-10-04T08:30:00Z"), reference), expected);
});

test("sub-second precision is read, not rounded away", () => {
  const reference = "2026-10-04T09:00:00Z";
  assert.equal(rel("2026-10-04T08:59:30.123456Z", reference), "just now");
  assert.equal(rel("2026-10-04T08:30:00.123456Z", reference), "29 minutes ago");
});

test("an hour across a clock change still reads as an hour", () => {
  assert.equal(
    rel("2026-03-08T06:30:00Z", "2026-03-08T07:30:00Z"),
    "1 hour ago",
  );
  assert.equal(
    rel("2026-11-01T05:30:00Z", "2026-11-01T06:30:00Z"),
    "1 hour ago",
  );
});

test("a stamp ahead of the reference reads as just now", () => {
  assert.equal(rel("2026-10-04T09:05:00Z", REFERENCE), "just now");
  assert.equal(rel("2026-12-25T00:00:00Z", REFERENCE), "just now");
});

test("a timestamp that cannot be read is refused", () => {
  refuses(() => rel("not-a-date", REFERENCE), "Not a timestamp");
  refuses(() => rel("2026-13-45T00:00:00Z", REFERENCE), "Not a timestamp");
  refuses(() => rel("   ", REFERENCE), "must not be empty");
  refuses(() => rel(null, REFERENCE), "ISO 8601 string");
  refuses(() => rel(undefined, REFERENCE), "ISO 8601 string");
  refuses(() => rel({}, REFERENCE), "ISO 8601 string");
  refuses(() => rel(NaN, REFERENCE), "finite number");
});

test("the reference date is an argument, so nothing here reads a clock", () => {
  const format = loadFormat();
  refuses(
    () => format.formatRelativeTime(REFERENCE),
    "reference date is required",
  );
  refuses(() => rel(REFERENCE, null), "reference date is required");
  refuses(() => rel(REFERENCE, undefined), "reference date is required");
  refuses(() => rel(REFERENCE, "not-a-date"), "Not a timestamp");
});

test("the module reaches no clock and no locale of its own", () => {
  assert.equal(
    /Date\.now|new Date|performance\.now|toLocale/.test(source),
    false,
  );
});

const TZ_TABLE = [
  ["2026-10-04T14:00:00+05:30", "2026-10-04T09:00:00Z"],
  ["2026-10-04T08:30:00", "2026-10-04T09:00:00Z"],
  ["2026-03-08T06:30:00Z", "2026-03-08T07:30:00Z"],
  ["2026-10-04T08:59:30.123456Z", "2026-10-04T09:00:00Z"],
  ["2026-10-04T08:59:00Z", "2026-10-04T09:00:00Z"],
  ["2026-10-04T00:00:00-08:30", "2026-10-04T09:00:00Z"],
];
const TZ_TABLE_EXPECTED = [
  "30 minutes ago",
  "30 minutes ago",
  "1 hour ago",
  "just now",
  "1 minute ago",
  "30 minutes ago",
];
const ZONES = [
  "UTC",
  "Asia/Kolkata",
  "America/New_York",
  "Pacific/Kiritimati",
  "Australia/Lord_Howe",
];

const DRIVER_SOURCE = [
  'const fs = require("node:fs");',
  'const vm = require("node:vm");',
  "const source = fs.readFileSync(" + JSON.stringify(FORMAT_PATH) + ', "utf8");',
  "const windowStub = {};",
  "vm.runInNewContext(source, { window: windowStub });",
  "const format = windowStub.DRISHTI_FORMAT;",
  "const table = " + JSON.stringify(TZ_TABLE) + ";",
  "const out = table.map(function (pair) {",
  "  return format.formatRelativeTime(pair[0], pair[1]);",
  "});",
  'process.stdout.write(JSON.stringify({ offset: new Date("2026-10-04T09:00:00Z").getTimezoneOffset(), out: out }));',
].join("\n");

function runTableInZone(zone) {
  return JSON.parse(
    execFileSync(process.execPath, ["-e", DRIVER_SOURCE], {
      encoding: "utf8",
      env: { ...process.env, TZ: zone },
    }),
  );
}

test("the same stamps read the same way in this process", () => {
  const format = loadFormat();
  assert.deepEqual(
    TZ_TABLE.map((pair) => format.formatRelativeTime(pair[0], pair[1])),
    TZ_TABLE_EXPECTED,
  );
});

test("the answer does not move with the reader's timezone", () => {
  const offsets = new Set();
  for (const zone of ZONES) {
    const answer = runTableInZone(zone);
    offsets.add(answer.offset);
    assert.deepEqual(answer.out, TZ_TABLE_EXPECTED, zone + " answered");
  }
  assert.ok(
    offsets.size >= 4,
    "the zones covered " + offsets.size + " distinct offsets, so the claim is untested",
  );
});
