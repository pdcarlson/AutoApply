/** The sections of the Profile page, in order, with their titles and descriptions. */

/** Title and description of each section, keyed by the id used in the URL hash. */
export const SECTIONS = {
  contact: [
    'Contact',
    'How employers reach you. Pulled from your resume; every field is editable.',
  ],
  links: ['Links', 'Portfolio, LinkedIn, GitHub, and anything else forms ask you to link.'],
  education: ['Education', 'Every school with degree, major, GPA, dates, and coursework.'],
  experience: ['Experience', 'Roles from your resume. The agent only writes from what’s here.'],
  projects: ['Projects', 'What you’ve built. Forms often ask what your part was and who used it.'],
  skills: ['Skills', 'Used to check postings against your profile.'],
  custom: [
    'Additional information',
    'Your own fields. Name it the way forms ask for it, then type the value.',
  ],
  resume: ['Resume file', 'The file attached to every application.'],
} as const;

/** A section id such as `education`. */
export type SectionKey = keyof typeof SECTIONS;

/** Every section id, in page order. */
export const SECTION_KEYS = Object.keys(SECTIONS) as SectionKey[];

/** The DOM id of a section, which the URL hash scrolls to. */
export const sectionElementId = (key: string) => `profile-${key}`;
