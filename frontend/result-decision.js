(() => {
  "use strict";

  // Where an officer's own choice is recorded beside the band it was shown:
  // the three choices as a radio group, their remark, the override that is on
  // screen only once the choice disagrees with that band, and the one exchange
  // the form makes: the choice posted to the screening it was made on, after
  // which the form is locked and cannot be sent again.

  // The three choices the abstract gives an officer, in its own order and
  // under the keys they travel by.  app/audit/decision.py names the same three
  // as OFFICER_ACTIONS and is the only place the service spells them, so a
  // case holds these three against that file rather than restating them.
  const OFFICER_ACTIONS = ["allow", "further_inspection", "reject"];

  // The words beside each choice on screen.  A display vocabulary of this
  // module's own: nothing else in the frontend labels a choice and the sheet
  // ships no label for one.  Keys, not choices: nothing here says which key
  // belongs to which band.
  const ACTION_LABELS = {
    allow: "Allow",
    further_inspection: "Further inspection",
    reject: "Reject",
  };

  // The bands in the order the 0-100 scale puts them in.  **A second ordering,
  // held apart from the one above**: no table in this module pairs a band with
  // a choice, because a disagreement is read off two positions rather than
  // looked up in an answer that has already decided it.  This is
  // app/audit/decision.py's own rule (7.10), and the reason the two orderings
  // above are tuples rather than a lookup.
  const BAND_ORDER = ["low", "review", "high"];

  // The radio group name, so the browser holds the three to one another and a
  // page carries no second spelling of the choice to keep in step.
  const ACTION_FIELD = "officer-action";

  // The ids the markup points at: the group names its label, and the remark's
  // label names the field.  Two ids on a page that draws one form.
  const GROUP_LABEL_ID = "decision-group-label";
  const REMARK_ID = "decision-remark";

  const CARD_CLASSES = ["ux4g-card", "ux4g-card-body"];
  const RADIO_CLASSES = ["ux4g-radio", "ux4g-radio-md"];
  const RADIO_INPUT_CLASS = "ux4g-radio-input";
  const RADIO_CONTROL_CLASS = "ux4g-radio-control";
  const RADIO_MARK_CLASS = "ux4g-radiomark";
  const RADIO_CONTENT_CLASS = "ux4g-radio-content";
  const REMARK_LABEL_CLASS = "ux4g-label-m-default";
  const REMARK_CONTAINER_CLASSES = [
    "ux4g-textarea-container",
    "ux4g-textarea-default",
    "ux4g-textarea-md",
  ];
  const REMARK_BOX_CLASS = "ux4g-textarea";
  const REMARK_INPUT_CLASS = "ux4g-textarea-input";
  const REMARK_HELPER_CLASS = "ux4g-textarea-helper";
  const OVERRIDE_CLASSES = ["ux4g-switch", "ux4g-switch-md"];
  const OVERRIDE_INPUT_CLASS = "ux4g-switch-input";
  const OVERRIDE_CONTROL_CLASS = "ux4g-switch-control";
  const OVERRIDE_TRACK_CLASS = "ux4g-switch-track";
  const OVERRIDE_THUMB_CLASS = "ux4g-switch-thumb";
  const OVERRIDE_CONTENT_CLASS = "ux4g-switch-content";
  const OVERRIDE_LABEL_CLASS = "ux4g-switch-label";
  const OVERRIDE_DESCRIPTION_CLASSES = [
    "ux4g-switch-description",
    "ux4g-switch-desc-helper",
  ];
  const SUBMIT_CLASSES = ["ux4g-btn", "ux4g-btn-primary", "ux4g-btn-md"];
  const ALERT_CLASSES = ["ux4g-alert"];
  const ALERT_ERROR_CLASS = "ux4g-alert-error";
  const ALERT_SUCCESS_CLASS = "ux4g-alert-success";

  // The sentences the form says in its own words.  The remark helper says it
  // is optional rather than implying a reason is owed, and the override
  // sentence names the disagreement, because a control that appeared for no
  // stated reason is one an officer has to guess at.
  const GROUP_LABEL = "Decision";
  const REMARK_LABEL = "Remark";
  const REMARK_HELPER = "Optional. Why you recorded this choice.";
  const OVERRIDE_LABEL = "Override the band";
  const OVERRIDE_DESCRIPTION = "This choice goes against the band.";
  const SUBMIT_LABEL = "Record decision";
  const RECORDED_LABEL = "Decision recorded";

  // The exchange itself, in the parts an exchange has: the path is composed
  // rather than configured, so no address is baked into a build, and the three
  // body keys are app.schemas.DecisionRequest's own rather than a second
  // spelling of them.
  const DECISION_PATH = "/api/screenings/";
  const DECISION_TAIL = "/decision";
  const JSON_TYPE = "application/json";
  const ACTION_KEY = "action";
  const REMARK_KEY = "remark";
  const OVERRIDE_KEY = "override";
  const REQUEST_FIELDS = [ACTION_KEY, REMARK_KEY, OVERRIDE_KEY];

  // 18.4 said in the officer's own words: the trail keeps the first choice and
  // a later one takes its place beside it, so nothing here claims the record
  // can be edited.
  const RECORDED_MESSAGE =
    "Recorded on the audit trail. A later choice would be a new record, not " +
    "an edit of this one.";
  const FAILED_MESSAGE =
    "The decision could not be recorded. Try again, and tell an " +
    "administrator if it keeps failing.";

  // 22.11's own words for a line that speaks without being asked.  A refusal
  // and the record are the same kind of announcement, so they are said on one
  // region rather than two.
  const LIVE_ROLE = "status";
  const LIVE_POLITENESS = "polite";

  const REQUIRED_ELEMENTS = ["container"];

  const CONTAINER_MESSAGE = "The decision form needs an element to draw into: ";
  const BAND_MESSAGE =
    "A band is one of the three the engine bands in: " +
    BAND_ORDER.join(", ") +
    ".";
  const ACTION_MESSAGE =
    "A decision is one of the officer three: " +
    OFFICER_ACTIONS.join(", ") +
    ".";
  const NO_FORM_MESSAGE = "There is no decision form drawn to choose on.";
  const NO_CHOICE_MESSAGE =
    "Choose one of the three decisions before recording it.";
  const NO_ID_MESSAGE =
    "There is no screening to record this decision on: the result carries " +
    "no id.";
  const ID_MESSAGE =
    "A screening id is the one string the service looks a row up by: the " +
    "stored result's own id.";
  const NO_API_MESSAGE = "This page cannot reach the quality service.";
  const PENDING_MESSAGE =
    "This decision is already on its way to the service. Wait for the answer.";
  const LOCKED_MESSAGE =
    "This decision is already recorded. It cannot be sent again.";

  class ResultDecisionError extends Error {
    constructor(code, message, cause) {
      super(message);
      this.name = "ResultDecisionError";
      this.code = code;
      if (cause !== undefined) {
        this.cause = cause;
      }
    }
  }

  function readElement(settings, name) {
    const element = settings ? settings[name] : null;
    if (!element) {
      throw new ResultDecisionError(
        "missing_element",
        CONTAINER_MESSAGE + name + ".",
      );
    }
    return element;
  }

  // includes rather than a lookup, so a key named "toString" is a choice no
  // officer makes and answers for nothing.
  function actionRank(action) {
    if (typeof action !== "string" || !OFFICER_ACTIONS.includes(action)) {
      throw new ResultDecisionError("bad_action", ACTION_MESSAGE);
    }
    return OFFICER_ACTIONS.indexOf(action);
  }

  function bandRank(band) {
    if (typeof band !== "string" || !BAND_ORDER.includes(band)) {
      throw new ResultDecisionError("bad_band", BAND_MESSAGE);
    }
    return BAND_ORDER.indexOf(band);
  }

  // Whether the choice disagrees with the band: the two sit at different
  // points on their own orderings, in either direction, because an officer
  // who released a document the system was more worried about is owed the
  // same reading as one who stopped a document it was less worried about.
  // This is app/audit/decision.py contradicts_band, comparing the two
  // orderings above rather than reading a table that would pair them.
  function contradictsBand(band, action) {
    return bandRank(band) !== actionRank(action);
  }

  // A row nothing has scored carries no band, so none was shown to go against
  // and there is nothing to override.  app/audit/decision.py override_required
  // answers the same way for a band of None, and the two agree here rather
  // than one of them being the rule.
  function overrideShown(band, action) {
    if (band === null || band === undefined) {
      return false;
    }
    return contradictsBand(band, action);
  }

  // The path one screening's choice travels, with the id encoded rather than
  // trusted, so a page cannot compose a second spelling of this route.
  function decisionPathFor(screeningId) {
    return DECISION_PATH + encodeURIComponent(screeningId) + DECISION_TAIL;
  }

  // An absent id is an answer -- there is no row to record against -- and an
  // id nobody can look up is a fault, refused by name on the band's reasoning:
  // a typo is a fault and an absent value is an answer.
  function readScreeningId(value) {
    if (value === null || value === undefined) {
      return null;
    }
    if (typeof value !== "string" || value.trim() === "") {
      throw new ResultDecisionError("bad_screening_id", ID_MESSAGE);
    }
    return value.trim();
  }

  // An answer the service could not spell is still an answer: the exchange has
  // happened, and a body nobody can read is not a reason to send it again.
  async function readJson(response) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  function classed(tagName, classNames) {
    const node = document.createElement(tagName);
    for (const name of classNames) {
      node.classList.add(name);
    }
    return node;
  }

  // bindResultDecision wires the officer own half of the result page, and
  // draws nothing until a page calls render().  The band is read off the same
  // result the band line reads, so there is one band vocabulary on the page
  // rather than a second reading of the same record.
  function bindResultDecision(options) {
    const settings = options || {};
    const container = readElement(settings, "container");

    let form = null;
    let current = null;
    let locked = false;
    let pending = false;

    // The band and the id are read before anything is written, so a result this
    // page cannot read leaves the form already standing rather than half
    // replaced.  Both come off the one stored result, so a page cannot draw one
    // screening's choice beside another result's band.
    function measure(result) {
      const band = result ? result.band : null;
      if (band !== null && band !== undefined) {
        bandRank(band);
      }
      return {
        band: band === undefined ? null : band,
        screeningId: readScreeningId(result ? result.screening_id : null),
      };
    }

    function drawRadio(action) {
      const label = classed("label", RADIO_CLASSES);
      const input = classed("input", [RADIO_INPUT_CLASS]);
      input.type = "radio";
      input.name = ACTION_FIELD;
      input.value = action;
      input.checked = false;
      const control = classed("span", [RADIO_CONTROL_CLASS]);
      control.appendChild(classed("span", [RADIO_MARK_CLASS]));
      const content = classed("span", [RADIO_CONTENT_CLASS]);
      content.textContent = ACTION_LABELS[action];
      label.appendChild(input);
      label.appendChild(control);
      label.appendChild(content);
      return { action: action, label: label, input: input };
    }

    function drawRemark() {
      const wrapper = classed("div", REMARK_CONTAINER_CLASSES);
      const label = classed("label", [REMARK_LABEL_CLASS]);
      label.setAttribute("for", REMARK_ID);
      label.textContent = REMARK_LABEL;
      const box = classed("div", [REMARK_BOX_CLASS]);
      const input = classed("textarea", [REMARK_INPUT_CLASS]);
      input.id = REMARK_ID;
      input.value = "";
      box.appendChild(input);
      const helper = classed("span", [REMARK_HELPER_CLASS]);
      helper.textContent = REMARK_HELPER;
      wrapper.appendChild(label);
      wrapper.appendChild(box);
      wrapper.appendChild(helper);
      return { wrapper: wrapper, input: input };
    }

    // The override is drawn hidden rather than drawn later: a control that
    // appears only on disagreement is absent until the officer has disagreed,
    // and hidden says that without a rule of this project own.  The loading
    // container and 23.3 regions ship the same attribute.
    function drawOverride() {
      const label = classed("label", OVERRIDE_CLASSES);
      label.hidden = true;
      const input = classed("input", [OVERRIDE_INPUT_CLASS]);
      input.type = "checkbox";
      input.setAttribute("role", "switch");
      input.checked = false;
      const control = classed("span", [OVERRIDE_CONTROL_CLASS]);
      const track = classed("span", [OVERRIDE_TRACK_CLASS]);
      track.appendChild(classed("span", [OVERRIDE_THUMB_CLASS]));
      control.appendChild(track);
      const content = classed("span", [OVERRIDE_CONTENT_CLASS]);
      const labelText = classed("span", [OVERRIDE_LABEL_CLASS]);
      labelText.textContent = OVERRIDE_LABEL;
      const description = classed("span", OVERRIDE_DESCRIPTION_CLASSES);
      description.textContent = OVERRIDE_DESCRIPTION;
      content.appendChild(labelText);
      content.appendChild(description);
      label.appendChild(input);
      label.appendChild(control);
      label.appendChild(content);
      return { label: label, input: input };
    }

    function render(result) {
      const read = measure(result);
      clear();
      const card = classed("div", CARD_CLASSES);
      const groupLabel = document.createElement("strong");
      groupLabel.id = GROUP_LABEL_ID;
      groupLabel.textContent = GROUP_LABEL;
      const group = document.createElement("div");
      group.setAttribute("role", "radiogroup");
      group.setAttribute("aria-labelledby", GROUP_LABEL_ID);
      const radios = OFFICER_ACTIONS.map(drawRadio);
      for (const radio of radios) {
        group.appendChild(radio.label);
      }
      const remark = drawRemark();
      const override = drawOverride();
      const button = classed("button", SUBMIT_CLASSES);
      button.type = "button";
      button.textContent = SUBMIT_LABEL;
      const status = classed("div", ALERT_CLASSES);
      status.setAttribute("role", LIVE_ROLE);
      status.setAttribute("aria-live", LIVE_POLITENESS);
      status.hidden = true;
      card.appendChild(groupLabel);
      card.appendChild(group);
      card.appendChild(remark.wrapper);
      card.appendChild(override.label);
      card.appendChild(button);
      card.appendChild(status);
      container.appendChild(card);
      form = {
        card: card,
        radios: radios,
        remark: remark.input,
        override: override,
        button: button,
        status: status,
      };
      current = read;
      // A form drawn afresh is a form that has recorded nothing, so the lock
      // and the pending send go with the card that carried them.
      locked = false;
      pending = false;
      button.addEventListener("click", onClick);
      return true;
    }

    // The whole of the rule, every time a choice is made: the radios follow
    // the choice, and the override is on screen if and only if that choice
    // disagrees with the band.  A hidden override is cleared rather than left
    // holding an answer to a question that is no longer on the page.
    function choose(action) {
      if (form === null) {
        throw new ResultDecisionError("no_form", NO_FORM_MESSAGE);
      }
      // A recorded choice is what the trail holds, so it is not something the
      // form will let an officer edit into a different claim.
      if (locked) {
        throw new ResultDecisionError("already_recorded", LOCKED_MESSAGE);
      }
      const band = current.band;
      const rank = actionRank(action);
      const shown = overrideShown(band, action);
      for (const radio of form.radios) {
        radio.input.checked = OFFICER_ACTIONS.indexOf(radio.action) === rank;
      }
      form.override.label.hidden = !shown;
      form.override.input.checked = shown && form.override.input.checked;
      current = {
        band: band,
        screeningId: current.screeningId,
        action: action,
        overrideShown: shown,
      };
      return true;
    }

    // An override nobody could see is not an override, so a hidden control
    // answers false however its input stands.
    function readOverride() {
      return form === null || form.override.label.hidden
        ? false
        : form.override.input.checked;
    }

    // One line under the form, hidden while there is nothing to say: a refusal
    // the officer caused, the service's own words when the network refused, or
    // the record that is now on the trail.  The variant follows the sentence
    // rather than the reverse, so a confirmation is never drawn as a fault.
    function say(message, variant) {
      form.status.classList.remove(ALERT_ERROR_CLASS, ALERT_SUCCESS_CLASS);
      if (variant) {
        form.status.classList.add(variant);
      }
      form.status.textContent = message;
      form.status.hidden = message === "";
      return message;
    }

    // The body the endpoint reads: the three keys it names and no fourth.  The
    // override sent is the flag read above, so a control nobody could see never
    // travels as an override.
    function readRequestBody() {
      return {
        [ACTION_KEY]: current.action,
        [REMARK_KEY]: form.remark.value,
        [OVERRIDE_KEY]: readOverride(),
      };
    }

    // Every control the officer could change stops answering and the button
    // says the choice is on the trail: a recorded decision cannot be sent a
    // second time, and cannot be edited into a different claim than the one
    // recorded.  Disabling is the platform's own lock, so no class of this
    // project's own is needed.
    function lock() {
      locked = true;
      for (const radio of form.radios) {
        radio.input.disabled = true;
      }
      form.remark.disabled = true;
      form.override.input.disabled = true;
      form.button.disabled = true;
      form.button.textContent = RECORDED_LABEL;
      return true;
    }

    // The click path says a refusal rather than throwing it into the console:
    // an officer pressing the button is owed the sentence, in the words it was
    // refused with.
    function onClick() {
      submit().catch(function (failure) {
        const message =
          failure && typeof failure.message === "string" && failure.message !== ""
            ? failure.message
            : FAILED_MESSAGE;
        say(message, ALERT_ERROR_CLASS);
      });
    }

    // The one send.  Everything it needs is checked before it reaches the
    // network, and the form is locked only once the service has answered: a
    // refused decision is still an officer's decision to make again.
    async function submit() {
      if (form === null) {
        throw new ResultDecisionError("no_form", NO_FORM_MESSAGE);
      }
      if (locked) {
        throw new ResultDecisionError("already_recorded", LOCKED_MESSAGE);
      }
      // Two presses, one decision: the second is refused rather than queued.
      if (pending) {
        throw new ResultDecisionError("pending", PENDING_MESSAGE);
      }
      if (current.action === undefined || current.action === null) {
        throw new ResultDecisionError("no_choice", NO_CHOICE_MESSAGE);
      }
      if (current.screeningId === null) {
        throw new ResultDecisionError("no_screening_id", NO_ID_MESSAGE);
      }
      const api = window.DRISHTI_API;
      if (!api || typeof api.request !== "function") {
        throw new ResultDecisionError("no_api", NO_API_MESSAGE);
      }
      const body = readRequestBody();
      pending = true;
      form.button.disabled = true;
      say("");
      try {
        const response = await api.request(
          decisionPathFor(current.screeningId),
          {
            method: "POST",
            headers: { "Content-Type": JSON_TYPE },
            body: JSON.stringify(body),
          },
        );
        const answer = await readJson(response);
        lock();
        say(RECORDED_MESSAGE, ALERT_SUCCESS_CLASS);
        return answer;
      } finally {
        pending = false;
        // A card taken away mid-flight has nothing left to unlock.
        if (!locked && form !== null) {
          form.button.disabled = false;
        }
      }
    }

    // Only what this module drew is taken away, so a page own children in the
    // same container are none of this module business.
    function clear() {
      const removed = form !== null;
      if (form !== null) {
        container.removeChild(form.card);
        form = null;
        current = null;
        locked = false;
        pending = false;
      }
      return removed;
    }

    return {
      render,
      choose,
      clear,
      submit,
      band: () => (current === null ? null : current.band),
      action: () =>
        current === null || current.action === undefined
          ? null
          : current.action,
      remark: () => (form === null ? null : form.remark.value),
      overrideShown: () =>
        current === null ? false : Boolean(current.overrideShown),
      override: readOverride,
      locked: () => locked,
      pending: () => pending,
    };
  }

  window.DRISHTI_RESULT_DECISION = {
    ACTION_FIELD,
    ACTION_LABELS,
    ALERT_CLASSES,
    ALERT_ERROR_CLASS,
    ALERT_SUCCESS_CLASS,
    BAND_ORDER,
    CARD_CLASSES,
    DECISION_PATH,
    DECISION_TAIL,
    GROUP_LABEL,
    GROUP_LABEL_ID,
    LIVE_POLITENESS,
    LIVE_ROLE,
    NO_CHOICE_MESSAGE,
    OFFICER_ACTIONS,
    OVERRIDE_CLASSES,
    OVERRIDE_DESCRIPTION,
    OVERRIDE_DESCRIPTION_CLASSES,
    OVERRIDE_LABEL,
    RECORDED_LABEL,
    RECORDED_MESSAGE,
    REMARK_HELPER,
    REMARK_ID,
    REMARK_LABEL,
    REQUEST_FIELDS,
    REQUIRED_ELEMENTS,
    SUBMIT_CLASSES,
    SUBMIT_LABEL,
    ResultDecisionError,
    contradictsBand,
    decisionPathFor,
    overrideShown,
    bindResultDecision,
  };
})();