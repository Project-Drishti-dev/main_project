const fs = require("node:fs");
const file = "frontend/screenings-list.js";
let raw = fs.readFileSync(file, "utf8");
const crlf = raw.includes("\r\n");
let src = crlf ? raw.replace(/\r\n/g, "\n") : raw;

function sub(anchor, replacement) {
  const parts = src.split(anchor);
  if (parts.length !== 2) {
    throw new Error("anchor not unique (" + (parts.length - 1) + "): " + anchor.slice(0, 60));
  }
  src = parts.join(replacement);
}

sub(
  '  const REQUIRED_ELEMENTS = ["body"];\n',
  '  const REQUIRED_ELEMENTS = ["body"];\n' +
    '\n' +
    '  // The controls the confirmation can hold focus on. Read off the dialog as\n' +
    '  // a key is pressed rather than listed here, so a control added to the\n' +
    '  // markup is inside the trap without a second edit.\n' +
    '  const FOCUSABLE_SELECTOR =\n' +
    "    'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex=\"-1\"])';\n",
);

sub(
  '    let pendingDelete = null;\n    let shown = STATE_LOADING;\n',
  '    let pendingDelete = null;\n    let pendingTrigger = null;\n    let shown = STATE_LOADING;\n',
);

sub(
  '    function requestDelete(id) {\n',
  '    // Tab from the last control returns to the first and Shift+Tab from the\n' +
    '    // first returns to the last, so focus cannot walk out of the open dialog\n' +
    '    // and leave the officer tabbing through the table behind it.\n' +
    '    function trapTabKey(dialog, event) {\n' +
    '      const focusable = Array.from(\n' +
    '        dialog.querySelectorAll(FOCUSABLE_SELECTOR),\n' +
    '      ).filter(\n' +
    '        (element) =>\n' +
    '          !element.closest("[hidden]") &&\n' +
    '          element.getAttribute("aria-hidden") !== "true",\n' +
    '      );\n' +
    '\n' +
    '      if (focusable.length === 0) {\n' +
    '        event.preventDefault();\n' +
    '        dialog.focus();\n' +
    '        return;\n' +
    '      }\n' +
    '\n' +
    '      const first = focusable[0];\n' +
    '      const last = focusable[focusable.length - 1];\n' +
    '      if (event.shiftKey && document.activeElement === first) {\n' +
    '        event.preventDefault();\n' +
    '        last.focus();\n' +
    '      } else if (!event.shiftKey && document.activeElement === last) {\n' +
    '        event.preventDefault();\n' +
    '        first.focus();\n' +
    '      }\n' +
    '    }\n' +
    '\n' +
    '    // Closing the dialog, leaving focus where it was. The two ways out --\n' +
    '    // the confirming press and backing out -- differ only in what happens\n' +
    '    // to focus, so the switch itself is written once.\n' +
    '    function closeConfirm() {\n' +
    '      pendingDelete = null;\n' +
    '      if (confirm) {\n' +
    '        confirm.classList.remove("is-open");\n' +
    '      }\n' +
    '    }\n' +
    '\n' +
    '    // Backing out hands focus back to the Delete that asked, so the next\n' +
    '    // Tab is where the officer left off rather than the top of the page.\n' +
    '    function cancelDelete() {\n' +
    '      closeConfirm();\n' +
    '      const trigger = pendingTrigger;\n' +
    '      pendingTrigger = null;\n' +
    '      if (trigger && trigger.isConnected) {\n' +
    '        trigger.focus();\n' +
    '      }\n' +
    '    }\n' +
    '\n' +
    '    function requestDelete(id, trigger = null) {\n',
);

sub(
  '      pendingDelete = id;\n      if (confirmId) {\n',
  '      pendingDelete = id;\n      pendingTrigger = trigger ?? document.activeElement ?? null;\n      if (confirmId) {\n',
);

sub(
  '    function cancelDelete() {\n      pendingDelete = null;\n      if (confirm) {\n        confirm.classList.remove("is-open");\n      }\n    }\n\n',
  '',
);

sub(
  '      cancelDelete();\n      const api = window.DRISHTI_API;\n',
  '      closeConfirm();\n      pendingTrigger = null;\n      const api = window.DRISHTI_API;\n',
);

sub(
  '      requestDelete(trigger.dataset.rowId);\n',
  '      requestDelete(trigger.dataset.rowId, trigger);\n',
);

sub(
  '    if (confirmCancel) {\n      confirmCancel.addEventListener("click", cancelDelete);\n    }\n',
  '    if (confirmCancel) {\n' +
    '      confirmCancel.addEventListener("click", cancelDelete);\n' +
    '    }\n' +
    '\n' +
    '    // Both keys are answered on the dialog itself: the trap keeps focus\n' +
    '    // inside it, so a document listener would only be a wider target for\n' +
    '    // the same keys.\n' +
    '    if (confirm) {\n' +
    '      confirm.addEventListener("keydown", (event) => {\n' +
    '        if (event.key === "Tab") {\n' +
    '          trapTabKey(confirm, event);\n' +
    '        } else if (event.key === "Escape") {\n' +
    '          event.preventDefault();\n' +
    '          cancelDelete();\n' +
    '        }\n' +
    '      });\n' +
    '    }\n',
);

sub(
  '      requestDelete,\n      cancelDelete,\n',
  '      requestDelete,\n      cancelDelete,\n      closeConfirm,\n',
);

fs.writeFileSync(file, crlf ? src.replace(/\n/g, "\r\n") : src);
console.log("patched " + file);
