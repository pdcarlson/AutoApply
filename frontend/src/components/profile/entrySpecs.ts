/** How each kind of profile entry (education, experience, project) is summarised and edited. */
import { EXPERIENCE_KINDS, type Education, type Experience, type Project } from '@/api/types';
import { formatSpan } from '@/lib/format';

/** The lists of entries a profile holds. */
export type EntryKind = 'education' | 'experience' | 'projects';

/** The entry type stored in each list. */
export type EntryOf<K extends EntryKind> = K extends 'education'
  ? Education
  : K extends 'experience'
    ? Experience
    : Project;

/** One input in an entry's edit form: key, label, input type and placeholder. */
export type FieldSpec = [
  key: string,
  label: string,
  type: 'text' | 'date' | 'textarea',
  placeholder?: string,
];

/** What the list needs to know about one kind of entry. */
export interface EntrySpec<E> {
  /** Label of the button that adds an entry. */
  add: string;
  title: (entry: E) => string;
  /** The muted line under the title. */
  sub: (entry: E) => string;
  blank: () => Omit<E, 'id'>;
  fields: FieldSpec[];
}

/** Hint under every Description box. */
export const DESCRIPTION_HINT =
  'Each line becomes a bullet. The agent writes answers only from what’s here.';

const joinParts = (parts: (string | false | undefined)[]) => parts.filter(Boolean).join(' · ');

const experienceSpec: EntrySpec<Experience> = {
  add: 'Add experience',
  title: (entry) => joinParts([entry.title, entry.org]) || 'New experience',
  sub: (entry) =>
    joinParts([
      entry.kind !== 'work' && EXPERIENCE_KINDS.find((kind) => kind.value === entry.kind)?.label,
      formatSpan(entry.start, entry.end, entry.current),
      entry.location,
    ]),
  blank: () => ({
    kind: 'work',
    title: '',
    org: '',
    location: '',
    start: '',
    end: '',
    current: false,
    detail: '',
  }),
  fields: [
    ['title', 'Title', 'text', 'e.g. Software Intern or Club President'],
    ['org', 'Organization', 'text', 'Company or organization'],
    ['location', 'Location', 'text', 'City, State or Remote'],
    ['start', 'Start date', 'date'],
    ['end', 'End date', 'date'],
    [
      'detail',
      'Description',
      'textarea',
      'One bullet per line, e.g.\nBuilt the Python service that tracked robot telemetry',
    ],
  ],
};

const educationSpec: EntrySpec<Education> = {
  add: 'Add education',
  title: (entry) => entry.school || 'New education',
  sub: (entry) =>
    joinParts([
      [entry.degreeType, entry.major].filter(Boolean).join(', '),
      entry.gpa && `GPA ${entry.gpa}`,
      entry.location,
      formatSpan(entry.start, entry.end),
    ]),
  blank: () => ({
    school: '',
    degreeType: '',
    major: '',
    gpa: '',
    location: '',
    start: '',
    end: '',
    coursework: '',
  }),
  fields: [
    ['school', 'School', 'text', 'School name'],
    ['location', 'Location', 'text', 'City, State'],
    ['degreeType', 'Degree type', 'text', 'e.g. Bachelor of Science (B.S.)'],
    ['major', 'Major', 'text', 'e.g. Computer Science'],
    ['gpa', 'GPA', 'text', 'e.g. 3.4'],
    ['start', 'Start date', 'date'],
    ['end', 'End date (or expected)', 'date'],
    ['coursework', 'Relevant coursework', 'textarea', 'e.g. Data Structures, Operating Systems'],
  ],
};

const projectSpec: EntrySpec<Project> = {
  add: 'Add project',
  title: (project) => project.name || 'New project',
  sub: (project) => project.tech,
  blank: () => ({ name: '', tech: '', detail: '' }),
  fields: [
    ['name', 'Project', 'text', 'Project name'],
    ['tech', 'Tools', 'text', 'e.g. React, Firebase'],
    [
      'detail',
      'Description',
      'textarea',
      'One bullet per line, e.g.\nBuilt the frontend with one other student',
    ],
  ],
};

const ENTRY_SPECS: { [K in EntryKind]: EntrySpec<EntryOf<K>> } = {
  experience: experienceSpec,
  education: educationSpec,
  projects: projectSpec,
};

/** The spec for one kind of entry. */
export function entrySpecFor<K extends EntryKind>(kind: K) {
  // TypeScript can't narrow a mapped type through a generic key, so name the result's type.
  return ENTRY_SPECS[kind] as EntrySpec<EntryOf<K>>;
}
