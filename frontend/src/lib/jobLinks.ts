/** A quick client-side check of pasted job links. */
import type { Ats } from '@/api/types';

/** Job boards Auto Apply can apply through, keyed by the domain their links use. */
export const SUPPORTED_BOARDS: readonly { domain: string; ats: Ats; example: string }[] = [
  { domain: 'greenhouse.io', ats: 'Greenhouse', example: 'boards.greenhouse.io' },
  { domain: 'ashbyhq.com', ats: 'Ashby', example: 'jobs.ashbyhq.com' },
];

/** "Supported: boards.greenhouse.io · jobs.ashbyhq.com". */
export const SUPPORTED_HINT = `Supported: ${SUPPORTED_BOARDS.map((board) => board.example).join(' · ')}`;

/** A usable link with its board, or a message explaining what's wrong with it. */
export type LinkCheck =
  | { ok: true; url: string; ats: Ats }
  | { ok: false; title: string; text: string; hint?: string };

const notALink: LinkCheck = {
  ok: false,
  title: 'That doesn’t look like a link',
  text: 'Copy the job’s full address from your browser’s address bar, then paste it here.',
};

/** Checks a pasted job link so obvious mistakes get instant feedback; the backend checks again. */
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
  const board = SUPPORTED_BOARDS.find(
    (candidate) => host === candidate.domain || host.endsWith(`.${candidate.domain}`),
  );
  if (!board) {
    const names = SUPPORTED_BOARDS.map((supported) => supported.ats).join(' and ');
    return {
      ok: false,
      title: 'This site isn’t supported',
      hint: SUPPORTED_HINT,
      text: `Auto Apply adds jobs from ${names} links. This one is from ${host}. Find the job on the company’s own careers page and paste that link instead.`,
    };
  }
  return { ok: true, url: `${url.origin}${url.pathname}`.replace(/\/$/, ''), ats: board.ats };
}
