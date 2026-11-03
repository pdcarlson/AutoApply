/** "1 job", "3 jobs". */
export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

const DAY_MS = 86_400_000;

/** Parses an ISO timestamp, or a YYYY-MM-DD date as local midnight. */
function toDate(value: string): Date {
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) return new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]));
  return new Date(value);
}

/** "Oct 20". */
export const formatDay = (value: string) =>
  toDate(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

/** "Oct 20, 2026". */
export const formatDate = (value: string) =>
  toDate(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

/** "9:41 AM". */
export const formatTime = (value: string) =>
  toDate(value).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

/** "Oct 20, 9:41 AM". */
export const formatDateTime = (value: string) => `${formatDay(value)}, ${formatTime(value)}`;

/** Whole days between `value` and now (0 for today). */
export function daysSince(value: string, now = new Date()): number {
  const start = toDate(value);
  const startDay = new Date(start.getFullYear(), start.getMonth(), start.getDate()).getTime();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.max(0, Math.round((today - startDay) / DAY_MS));
}

/** "today", "1 day ago", "4 days ago". */
export function daysAgo(value: string, now = new Date()): string {
  const days = daysSince(value, now);
  return days === 0 ? 'today' : `${plural(days, 'day', 'days')} ago`;
}

/** "Oct 1 – Present", "Start ? – May 15, 2027", or "" when no dates are known. */
export function formatSpan(start: string, end: string, current = false): string {
  if (!start && !end && !current) return '';
  const from = start ? formatDate(start) : 'Start ?';
  const to = current ? 'Present' : end ? formatDate(end) : 'End ?';
  return `${from} – ${to}`;
}

/** Splits a description into bullets: one per line, leading "-", "•", or "*" removed. */
export const toBullets = (text: string) =>
  text
    .split(/\n+/)
    .map((line) => line.replace(/^\s*[-•*]\s*/, '').trim())
    .filter(Boolean);

/** Upcoming graduation terms ("May 2027", ...) for the next few years. */
export function graduationOptions(now = new Date(), years = 4): string[] {
  const months = [
    ['May', 4],
    ['August', 7],
    ['December', 11],
  ] as const;
  const options: string[] = [];
  for (let year = now.getFullYear(); year < now.getFullYear() + years; year++) {
    for (const [name, index] of months) {
      if (year > now.getFullYear() || index >= now.getMonth()) options.push(`${name} ${year}`);
    }
  }
  return options;
}
