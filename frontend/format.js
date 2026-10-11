(() => {
  "use strict";

  const BAND_LABELS = {
    low: "Low Risk",
    review: "Review",
    high: "High Risk",
  };

  const MIN_SCORE = 0;
  const MAX_SCORE = 100;
  const SCORE_DECIMALS = 1;

  const SECOND_MS = 1000;
  const MINUTE_MS = 60 * SECOND_MS;
  const HOUR_MS = 60 * MINUTE_MS;
  const DAY_MS = 24 * HOUR_MS;

  const JUST_NOW_LABEL = "just now";
  const AGE_LABELS = {
    minute: ["minute ago", "minutes ago"],
    hour: ["hour ago", "hours ago"],
    day: ["day ago", "days ago"],
  };

  // An ISO 8601 stamp with no offset is read as UTC: the backend stamps
  // created_at in UTC and serialises it without one, and Date.parse would
  // otherwise read it in the reader's own zone.
  const HAS_OFFSET = /(?:[Zz]|[+-]\d{2}:?\d{2})$/;

  class FormatError extends Error {
    constructor(message) {
      super(message);
      this.name = "FormatError";
    }
  }

  function bandLabel(band) {
    const label = typeof band === "string" ? BAND_LABELS[band] : undefined;
    if (label === undefined) {
      throw new FormatError("Not a risk band: " + String(band) + ".");
    }
    return label;
  }

  function formatScore(score) {
    if (typeof score !== "number" || !Number.isFinite(score)) {
      throw new FormatError("A score must be a finite number.");
    }
    if (score < MIN_SCORE || score > MAX_SCORE) {
      throw new FormatError(
        "A score must lie between " + MIN_SCORE + " and " + MAX_SCORE + ".",
      );
    }
    const text = score.toFixed(SCORE_DECIMALS);
    return text.endsWith(".0") ? text.slice(0, -2) : text;
  }

  function parseInstant(value) {
    if (typeof value === "number") {
      if (!Number.isFinite(value)) {
        throw new FormatError(
          "A timestamp must be a finite number of milliseconds.",
        );
      }
      return value;
    }
    if (typeof value !== "string") {
      throw new FormatError(
        "A timestamp must be an ISO 8601 string or epoch milliseconds.",
      );
    }
    const text = value.trim();
    if (text === "") {
      throw new FormatError("A timestamp must not be empty.");
    }
    const millis = Date.parse(HAS_OFFSET.test(text) ? text : text + "Z");
    if (!Number.isFinite(millis)) {
      throw new FormatError("Not a timestamp: " + text + ".");
    }
    return millis;
  }

  function ageLabel(count, unit) {
    const labels = AGE_LABELS[unit];
    return count + " " + (count === 1 ? labels[0] : labels[1]);
  }

  function formatRelativeTime(value, now) {
    if (now === undefined || now === null) {
      throw new FormatError(
        "A reference date is required; this module reads no clock.",
      );
    }
    const elapsed = parseInstant(now) - parseInstant(value);
    if (elapsed < MINUTE_MS) {
      return JUST_NOW_LABEL;
    }
    if (elapsed < HOUR_MS) {
      return ageLabel(Math.floor(elapsed / MINUTE_MS), "minute");
    }
    if (elapsed < DAY_MS) {
      return ageLabel(Math.floor(elapsed / HOUR_MS), "hour");
    }
    return ageLabel(Math.floor(elapsed / DAY_MS), "day");
  }

  window.DRISHTI_FORMAT = {
    bandLabel,
    formatScore,
    formatRelativeTime,
    parseInstant,
    FormatError,
    BAND_LABELS,
    MIN_SCORE,
    MAX_SCORE,
  };
})();
