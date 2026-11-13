import type { Ats, Job } from '@/api/types';

/** Job boards Auto Apply can apply through, keyed by the domain their links use. */
export const SUPPORTED_BOARDS: readonly { domain: string; ats: Ats; example: string }[] = [
  { domain: 'greenhouse.io', ats: 'Greenhouse', example: 'boards.greenhouse.io' },
  { domain: 'ashbyhq.com', ats: 'Ashby', example: 'jobs.ashbyhq.com' },
  { domain: 'lever.co', ats: 'Lever', example: 'jobs.lever.co' },
];

export const SUPPORTED_HINT = `Supported: ${SUPPORTED_BOARDS.map((b) => b.example).join(' · ')}`;

export type LinkCheck =
  | { ok: true; url: string; ats: Ats }
  | { ok: false; title: string; text: string; hint?: string };

/**
 * Quick client-side check of a pasted job link, so obvious mistakes get instant feedback.
 * The backend validates again and is the authority on closed or duplicate postings.
 */
export function checkJobLink(input: string): LinkCheck {
  const text = input.trim();
  let url: URL;
  try {
    url = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`);
  } catch {
    return notALink;
  }
  if (!url.hostname.includes('.')) return notALink;

  const host = url.hostname.replace(/^www\./, '');
  const board = SUPPORTED_BOARDS.find((b) => host === b.domain || host.endsWith(`.${b.domain}`));
  if (!board) {
    const names = SUPPORTED_BOARDS.map((b) => b.ats)
      .join(', ')
      .replace(/, ([^,]*)$/, ' and $1');
    return {
      ok: false,
      title: 'This site isn’t supported',
      hint: SUPPORTED_HINT,
      text: `Auto Apply adds jobs from ${names} links. This one is from ${host}. Find the job on the company’s own careers page and paste that link instead.`,
    };
  }
  return { ok: true, url: `${url.origin}${url.pathname}`.replace(/\/$/, ''), ats: board.ats };
}

const notALink: LinkCheck = {
  ok: false,
  title: 'That doesn’t look like a link',
  text: 'Copy the job’s full address from your browser’s address bar, then paste it here.',
};

/**
 * Sites that turn applications from the agent's browser away (Lever's bot check). The person
 * presses Submit in their own browser instead; the AutoApply Filler extension fills the form.
 */
export const finishesInBrowser = (job: Pick<Job, 'ats'>) => job.ats === 'Lever';

/** Tells the AutoApply Filler extension to fill the form as soon as it opens. */
export const FILL_ON_OPEN = '#autoapply-fill';

/**
 * Where "Open the form" goes: the job link, or for Lever its application page, marked so the
 * extension fills it on open (without the extension the page just opens).
 */
export function formUrl(job: Pick<Job, 'ats' | 'url'>): string {
  if (!finishesInBrowser(job)) return job.url;
  const base = job.url.replace(/[?#].*$/, '').replace(/\/(apply)?\/?$/, '');
  return `${base}/apply${FILL_ON_OPEN}`;
}
