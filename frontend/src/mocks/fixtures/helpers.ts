/** Small date and text helpers shared by the mock fixtures. */

const HOUR_MS = 3_600_000;
const DAY_MS = 24 * HOUR_MS;

/** An ISO timestamp `days` and `hours` before now. */
export const isoAgo = (days: number, hours = 0) =>
  new Date(Date.now() - days * DAY_MS - hours * HOUR_MS).toISOString();

/** A YYYY-MM-DD date `days` from today. */
export const dateIn = (days: number) =>
  new Date(Date.now() + days * DAY_MS).toISOString().slice(0, 10);

/** Lowercase letters only, for building board URLs from a company name. */
export const slugify = (text: string) => text.toLowerCase().replace(/[^a-z]+/g, '');
