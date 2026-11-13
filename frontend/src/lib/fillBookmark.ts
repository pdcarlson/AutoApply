/**
 * The "Fill with AutoApply" bookmark: dragged to the bookmarks bar once, then clicked on a job's
 * application page in any browser. It opens AutoApply's small fill window (served by the local
 * backend), which sends back the job's answers, resume and fill script; the page then fills its
 * own form. It never presses Submit. Messages are only accepted from AutoApply's own address.
 */
export const AUTOAPPLY_ORIGIN = 'http://localhost:8080';

const SOURCE = `(() => {
  const AUTOAPPLY = '${AUTOAPPLY_ORIGIN}';
  const win = window.open(
    AUTOAPPLY + '/api/extension/fill-window?url=' + encodeURIComponent(location.href),
    'autoapply-fill',
    'width=440,height=560',
  );
  if (!win) {
    alert('Allow pop-ups for this site, then click Fill with AutoApply again.');
    return;
  }
  const onMessage = async (event) => {
    if (event.origin !== AUTOAPPLY || !event.data || event.data.type !== 'autoapply-fill') return;
    removeEventListener('message', onMessage);
    new Function(event.data.fill)();
    const resume = event.data.resume;
    const file = resume ? new File([resume.buffer], resume.name, { type: resume.type }) : null;
    const result = await AutoApplyFill.fillLever(event.data.plan, file);
    win.postMessage({ type: 'autoapply-filled', filled: result.filled, missed: result.missed }, AUTOAPPLY);
  };
  addEventListener('message', onMessage);
})();`;

/** The bookmark's address (a `javascript:` link). */
export const FILL_BOOKMARK = `javascript:${encodeURIComponent(SOURCE.replace(/\s*\n\s*/g, ' '))}`;

/** The same code, for tests that run it without a bookmark. */
export const FILL_BOOKMARK_SOURCE = SOURCE;
