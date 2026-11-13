// Runs on Lever job pages. On the application form it fills in AutoApply's answers (by itself
// when AutoApply opened the page, otherwise on a click); on the thank-you page it tells AutoApply
// the application went out. It never presses Submit.
(() => {
  const SUBMITTED_KEY = 'autoapply-submitting';
  const FILL_ON_OPEN = '#autoapply-fill'; // AutoApply's "Open the form" adds this to the link
  const send = (message) => chrome.runtime.sendMessage(message);
  const onForm = () => Boolean(document.querySelector('#application-form'));
  const onThanks = () => location.pathname.replace(/\/$/, '').endsWith('/thanks');

  function panel() {
    const box = document.createElement('div');
    box.id = 'autoapply-panel';
    box.innerHTML =
      '<strong>AutoApply</strong><p class="autoapply-status"></p>' +
      '<button type="button" class="autoapply-fill">Fill in my answers</button>' +
      '<ul class="autoapply-notes"></ul>';
    document.body.appendChild(box);
    return {
      say: (text) => {
        box.querySelector('.autoapply-status').textContent = text;
      },
      note: (text) => {
        const item = document.createElement('li');
        item.textContent = text;
        box.querySelector('.autoapply-notes').appendChild(item);
      },
      clearNotes: () => {
        box.querySelector('.autoapply-notes').innerHTML = '';
      },
      button: box.querySelector('.autoapply-fill'),
    };
  }

  function toFile(resume, name) {
    const binary = atob(resume.base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return new File([bytes], name, { type: resume.type });
  }

  async function fill(ui) {
    ui.button.disabled = true;
    ui.clearNotes();
    ui.say('Getting your answers from AutoApply...');
    const plan = await send({ type: 'plan', url: location.href });
    if (!plan.ok) {
      ui.say(plan.message);
      ui.button.disabled = false;
      return;
    }
    let resumeFile = null;
    if (plan.body.resume) {
      const resume = await send({ type: 'resume', url: plan.body.resume.url });
      if (resume.ok) resumeFile = toFile(resume, plan.body.resume.name);
      else ui.note(resume.message);
    }
    ui.say('Filling the form...');
    const result = await globalThis.AutoApplyFill.fillLever(plan.body, resumeFile);
    sessionStorage.setItem(SUBMITTED_KEY, plan.body.jobId);
    ui.say(`Filled ${result.filled.length} answers. Check them, then press Submit yourself.`);
    result.missed.forEach((label) => ui.note(`Couldn't fill: ${label}`));
    plan.body.unanswered.forEach((label) => ui.note(`Needs your answer: ${label}`));
    plan.body.protected.forEach((label) => ui.note(`Yours to do: ${label}`));
    ui.button.textContent = 'Fill again';
    ui.button.disabled = false;
  }

  async function reportSubmitted() {
    const jobId = sessionStorage.getItem(SUBMITTED_KEY);
    if (!jobId) return;
    sessionStorage.removeItem(SUBMITTED_KEY);
    const ui = panel();
    ui.button.remove();
    const result = await send({ type: 'submitted', jobId });
    ui.say(
      result.ok
        ? "Recorded in AutoApply. It's in your Applications."
        : `Submitted, but AutoApply didn't record it: ${result.message}`,
    );
  }

  if (onThanks()) {
    reportSubmitted();
  } else if (onForm()) {
    const ui = panel();
    ui.button.addEventListener('click', () => fill(ui));
    if (location.hash === FILL_ON_OPEN) {
      history.replaceState(null, '', location.pathname + location.search); // fill once only
      fill(ui);
    } else {
      ui.say('Your answers are ready to fill in.');
    }
  }
})();
