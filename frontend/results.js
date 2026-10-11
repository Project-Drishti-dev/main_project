(() => {
  "use strict";

  // Every number this site shows, each drawn beside the dataset it was read
  // over. The rows come from `results-metrics.js`, which the Part 27 harnesses
  // wrote; nothing here computes a metric, rounds one or invents a value.

  const METRICS_GLOBAL = "DRISHTI_RESULTS_METRICS";

  // What a row shows where nothing was counted. The harnesses print the same
  // mark, so a rate a detector never achieved is not read as one.
  const NO_NUMBER = "--";

  // The abstract's own targets: shown in the same table, and the one row a
  // number may appear on without a dataset behind it (Gate 27).
  const DESIGNED = "designed";

  const TAG_CLASS = "ux4g-tag";
  const TAG_SIZE_CLASS = "ux4g-tag-s";
  const MUTED_CLASS = "ux4g-text-neutral-secondary";

  // What a design target names in the dataset column, said rather than left
  // blank so an empty cell is never read as a missing dataset by accident.
  const WHAT_A_TARGET_NAMES = "The abstract's design target";

  // What a row with nothing installed names, which is an answer and not a gap.
  const NO_DATASET_TEXT = "No dataset installed";

  // The four sources a row can carry, read out of the harnesses that write
  // them: measured (27.5-27.7), stub and designed (27.11, 27.9), and the
  // not-measured answer every harness reports when an input is missing.
  const SOURCES = {
    measured: { label: "Measured", variant: "ux4g-tag-filled-success" },
    stub: { label: "Stub", variant: "ux4g-tag-filled-warning" },
    designed: { label: "Design target", variant: "ux4g-tag-filled-neutral" },
    "not measured": { label: "Not measured", variant: "ux4g-tag-filled-info" },
  };

  class ResultsError extends Error {
    constructor(message) {
      super(message);
      this.name = "ResultsError";
    }
  }

  // Whether a row shows a number rather than the mark for "nothing counted".
  function showsANumber(value) {
    return String(value) !== NO_NUMBER && String(value).trim() !== "";
  }

  /* Gate 27, as a refusal rather than a comment: a number is drawn only beside
     the dataset it was read over, and a design target is the one row that may
     name none. A dataset id nothing declares is refused too, since a row
     pointing at an unnamed corpus is the failure this page exists to prevent. */
  function checkMetric(metric, datasets) {
    if (metric.source === DESIGNED) {
      if (metric.dataset) {
        throw new ResultsError(
          metric.id + " is a design target and must not name a dataset.",
        );
      }
      return metric;
    }
    if (showsANumber(metric.value) && !metric.dataset) {
      throw new ResultsError(
        metric.id + " shows " + metric.value + " and names no dataset, so the " +
          "number would be shown with nothing behind it.",
      );
    }
    if (metric.dataset && !datasets.has(metric.dataset)) {
      throw new ResultsError(
        metric.id + " names dataset " + metric.dataset + ", which is not one " +
          "this file declares.",
      );
    }
    return metric;
  }

  // What the dataset column reads for one row.
  function datasetText(metric, datasets) {
    if (metric.source === DESIGNED) {
      return WHAT_A_TARGET_NAMES;
    }
    if (!metric.dataset) {
      return NO_DATASET_TEXT;
    }
    return datasets.get(metric.dataset).name;
  }

  function labelledCell(document, value, className) {
    const cell = document.createElement("td");
    cell.textContent = value;
    if (className) {
      cell.classList.add(className);
    }
    return cell;
  }

  // The source tag, so a row is never read by its number alone.
  function sourceCell(document, source) {
    const known = SOURCES[source];
    if (!known) {
      throw new ResultsError("No source label for " + String(source) + ".");
    }
    const cell = document.createElement("td");
    const tag = document.createElement("span");
    tag.classList.add(TAG_CLASS, known.variant, TAG_SIZE_CLASS);
    tag.textContent = known.label;
    cell.appendChild(tag);
    return cell;
  }

  // One metric: its name and how it was read, the number, where the number
  // came from, and what read it.
  function metricRow(document, metric, datasets) {
    checkMetric(metric, datasets);
    const row = document.createElement("tr");

    const name = labelledCell(document, metric.label);
    if (metric.note) {
      const note = document.createElement("p");
      note.classList.add(MUTED_CLASS);
      note.textContent = metric.note;
      name.appendChild(note);
    }
    row.appendChild(name);
    row.appendChild(labelledCell(document, metric.value));
    row.appendChild(sourceCell(document, metric.source));
    row.appendChild(labelledCell(document, datasetText(metric, datasets)));
    row.appendChild(labelledCell(document, metric.detector));
    return row;
  }

  function readMetrics() {
    const source = window[METRICS_GLOBAL];
    if (!source) {
      throw new ResultsError(
        "This page loads " + METRICS_GLOBAL + " and it is not here, so there " +
          "is nothing measured to show.",
      );
    }
    return source;
  }

  /* Every row is checked before any row is drawn, so a file that breaks Gate
     27 leaves the table empty rather than half filled. */
  function draw(view, source) {
    const datasets = new Map(
      source.datasets.map(function (dataset) {
        return [dataset.id, dataset];
      }),
    );
    const metrics = source.metrics;
    for (const metric of metrics) {
      checkMetric(metric, datasets);
    }
    view.body.textContent = "";
    for (const metric of metrics) {
      view.body.appendChild(metricRow(document, metric, datasets));
    }
    if (view.empty) {
      view.empty.hidden = metrics.length > 0;
    }
    return metrics.length;
  }

  function bindResultsView(settings) {
    const view = {
      body: settings ? settings.body : null,
      empty: settings ? settings.empty : null,
    };
    if (!view.body) {
      throw new ResultsError("The results view needs the table body to fill.");
    }
    return {
      draw: function (source) {
        return draw(view, source || readMetrics());
      },
    };
  }

  function start() {
    const body = document.getElementById("results-body");
    if (!body) {
      return null;
    }
    const view = bindResultsView({
      body: body,
      empty: document.getElementById("results-empty"),
    });
    return view.draw(readMetrics());
  }

  window.DRISHTI_RESULTS = Object.freeze({
    ResultsError: ResultsError,
    SOURCES: SOURCES,
    NO_NUMBER: NO_NUMBER,
    DESIGNED: DESIGNED,
    WHAT_A_TARGET_NAMES: WHAT_A_TARGET_NAMES,
    NO_DATASET_TEXT: NO_DATASET_TEXT,
    showsANumber: showsANumber,
    checkMetric: checkMetric,
    datasetText: datasetText,
    metricRow: metricRow,
    draw: draw,
    bindResultsView: bindResultsView,
    start: start,
  });

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
  }
})();