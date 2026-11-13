// Puts AutoApply's answers into a Lever application form. No Chrome APIs here, so the tests can
// load this file into a plain page. It never presses Submit and never touches a CAPTCHA.
(() => {
  const US_STATES = {
    alabama: 'al',
    alaska: 'ak',
    arizona: 'az',
    arkansas: 'ar',
    california: 'ca',
    colorado: 'co',
    connecticut: 'ct',
    delaware: 'de',
    florida: 'fl',
    georgia: 'ga',
    hawaii: 'hi',
    idaho: 'id',
    illinois: 'il',
    indiana: 'in',
    iowa: 'ia',
    kansas: 'ks',
    kentucky: 'ky',
    louisiana: 'la',
    maine: 'me',
    maryland: 'md',
    massachusetts: 'ma',
    michigan: 'mi',
    minnesota: 'mn',
    mississippi: 'ms',
    missouri: 'mo',
    montana: 'mt',
    nebraska: 'ne',
    nevada: 'nv',
    'new hampshire': 'nh',
    'new jersey': 'nj',
    'new mexico': 'nm',
    'new york': 'ny',
    'north carolina': 'nc',
    'north dakota': 'nd',
    ohio: 'oh',
    oklahoma: 'ok',
    oregon: 'or',
    pennsylvania: 'pa',
    'rhode island': 'ri',
    'south carolina': 'sc',
    'south dakota': 'sd',
    tennessee: 'tn',
    texas: 'tx',
    utah: 'ut',
    vermont: 'vt',
    virginia: 'va',
    washington: 'wa',
    'west virginia': 'wv',
    wisconsin: 'wi',
    wyoming: 'wy',
    'district of columbia': 'dc',
  };
  const SUGGESTION_WAIT_MS = 8000;
  const RESUME_WAIT_MS = 30000;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const byName = (key) => Array.from(document.getElementsByName(key));
  const fire = (element, type) => element.dispatchEvent(new Event(type, { bubbles: true }));

  async function waitFor(check, timeoutMs) {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const found = check();
      if (found) return found;
      if (Date.now() > deadline) return null;
      await sleep(100);
    }
  }

  function setValue(element, value) {
    element.focus();
    element.value = value;
    fire(element, 'input');
    fire(element, 'change');
  }

  // A dropdown's answer is the text of one of its options.
  function chooseOption(select, value) {
    const wanted = value.trim().toLowerCase();
    const option = Array.from(select.options).find(
      (candidate) => candidate.text.trim().replace(/\s+/g, ' ').toLowerCase() === wanted,
    );
    if (!option) return false;
    select.value = option.value;
    fire(select, 'change');
    return true;
  }

  // Radio buttons and checkboxes share a name, and the answer is one's value.
  function chooseBox(boxes, value) {
    const box = boxes.find((candidate) => candidate.value === value);
    if (!box) return false;
    if (!box.checked) box.click();
    return box.checked;
  }

  // (city, state) from how a person writes a place: "Troy, NY", "Troy, New York" or, without
  // the comma, "Troy NY". The state is "" when there isn't one, as in "New York".
  function splitPlace(value) {
    const parts = value
      .split(',')
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean);
    if (parts.length >= 2) return [parts[0], parts[1]];
    const words = value.toLowerCase().split(/\s+/).filter(Boolean);
    const codes = Object.values(US_STATES);
    for (const size of [3, 2, 1]) {
      const tail = words.slice(-size).join(' ');
      if (words.length > size && (tail in US_STATES || codes.includes(tail))) {
        return [words.slice(0, -size).join(' '), tail];
      }
    }
    return [words.join(' '), ''];
  }

  // Lever's city box only suggests places as keys are pressed, and takes a suggestion on mouse-down.
  // Never picks a same-named city in another state.
  async function chooseLocation(box, value) {
    const [city, state] = splitPlace(value);
    const states = [state, US_STATES[state] || state].filter(Boolean);
    setValue(box, city);
    // Lever looks places up on a key press, not on the text changing
    box.dispatchEvent(new KeyboardEvent('keydown', { key: 'Unidentified', bubbles: true }));
    const matches = (option) => {
      const parts = option.textContent.split(',').map((part) => part.trim().toLowerCase());
      return parts[0] === city && (!states.length || states.includes(parts[1]));
    };
    const option = await waitFor(
      () =>
        Array.from(document.querySelectorAll('.dropdown-results .dropdown-location')).find(matches),
      SUGGESTION_WAIT_MS,
    );
    if (!option) return false;
    option.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    return true;
  }

  // Attach the resume the way a person picking a file would, then wait for Lever to read it.
  async function attachResume(key, file) {
    const input = byName(key).find((element) => element.type === 'file');
    if (!input) return false;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    fire(input, 'change');
    const shown = (selector) => {
      const note = document.querySelector(selector);
      return note && getComputedStyle(note).display !== 'none';
    };
    await waitFor(
      () => shown('.resume-upload-success') || shown('.resume-upload-failure'),
      RESUME_WAIT_MS,
    );
    return input.files.length === 1;
  }

  async function fillField(field) {
    const elements = byName(field.key).filter((element) => element.type !== 'hidden');
    if (!elements.length) return false;
    const first = elements[0];
    if (field.kind === 'location') return chooseLocation(first, field.value);
    if (first.tagName === 'SELECT') return chooseOption(first, field.value);
    if (first.type === 'radio' || first.type === 'checkbox')
      return chooseBox(elements, field.value);
    setValue(first, field.value);
    return true;
  }

  // Fills every field in the plan, resume first because Lever fills boxes from it.
  // Returns the labels it filled and the ones it couldn't.
  async function fillLever(plan, resumeFile) {
    const filled = [];
    const missed = [];
    if (plan.resume && resumeFile) {
      ((await attachResume(plan.resume.key, resumeFile)) ? filled : missed).push('Resume/CV');
    }
    for (const field of plan.fields) {
      let ok = false;
      try {
        ok = await fillField(field);
      } catch {
        ok = false;
      }
      (ok ? filled : missed).push(field.label);
    }
    return { filled, missed };
  }

  globalThis.AutoApplyFill = { fillLever };
})();
