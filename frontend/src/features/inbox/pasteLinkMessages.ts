/** What the paste-a-link box tells the user, and how backend errors map to it. */
import type { AddJobConflict } from '@/api/types';
import { isApiError } from '@/api/client';
import { SUPPORTED_HINT } from '@/lib/jobLinks';
import { formatDay } from '@/lib/format';

/** A message under the paste box: progress, an error, or a note. */
export type PasteLinkMessage =
  | { kind: 'busy'; text: string }
  | { kind: 'error' | 'info'; title: string; text: string; hint?: string; jobId?: string };

/** Turns an add-job failure from the backend into what to tell the user. */
export function messageForError(error: unknown): PasteLinkMessage {
  if (isApiError(error)) {
    const conflict = error.details as Partial<AddJobConflict>;
    switch (error.code) {
      case 'already_applied':
        return {
          kind: 'info',
          title: 'Already sent',
          text: `You applied to ${conflict.company ?? 'this company'}${conflict.sentAt ? ` on ${formatDay(conflict.sentAt)}` : ''}. Each job is sent once.`,
        };
      case 'already_in_inbox':
        return {
          kind: 'info',
          title: 'Already in your Inbox',
          text: [conflict.company, conflict.role].filter(Boolean).join(' · '),
          jobId: conflict.jobId,
        };
      case 'posting_closed':
        return {
          kind: 'error',
          title: 'This posting is closed',
          text: 'The company isn’t taking applications for it anymore, so there’s nothing to add.',
        };
      case 'unsupported_site':
        return {
          kind: 'error',
          title: 'This site isn’t supported',
          text: error.message,
          hint: SUPPORTED_HINT,
        };
      case 'invalid_url':
        return { kind: 'error', title: 'That doesn’t look like a link', text: error.message };
    }
  }
  return {
    kind: 'error',
    title: 'We couldn’t read that posting',
    text: 'Something went wrong on our side. Try again in a moment.',
  };
}
