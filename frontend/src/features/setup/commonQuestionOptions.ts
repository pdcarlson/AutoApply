/** Answer options and small helpers shared by the setup questions. */

/** The wording of the "decline" answer on self-identification questions. */
export const DECLINE_LABEL = 'I don’t wish to answer';

/** The "decline" option for segmented and radio controls. */
export const DECLINE_OPTION = { value: 'decline', label: DECLINE_LABEL } as const;

/** Radio options for veteran status. */
export const VETERAN_OPTIONS = [
  { value: 'Yes', label: 'I am a protected veteran' },
  { value: 'No', label: 'I am not a protected veteran' },
  DECLINE_OPTION,
] as const;

/** Radio options for disability status. */
export const DISABILITY_OPTIONS = [
  { value: 'Yes', label: 'Yes, I have a disability (or had one in the past)' },
  { value: 'No', label: 'No, I don’t have a disability' },
  DECLINE_OPTION,
] as const;

/** The id of a question's label, which its control points to with `aria-labelledby`. */
export const questionLabelId = (key: string) => `q-${key}`;

/** Keeps a saved value selectable even when it's no longer in the generated list. */
export const withCurrent = (options: string[], current: string | null) =>
  current && !options.includes(current) ? [current, ...options] : options;
