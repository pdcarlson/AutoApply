/** Makes ids for profile entries added in the browser. */

/** Returns a fresh id such as `link-<uuid>`. */
export const newId = (prefix: string) => `${prefix}-${crypto.randomUUID()}`;
