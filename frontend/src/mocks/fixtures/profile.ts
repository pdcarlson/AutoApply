/** The mock user, their starting profile, and what the mock resume parser reads. */
import type { Profile, ResumeParse, User } from '@/api/types';

/** The one account the mock backend knows. */
export const MOCK_USER: User = {
  id: 'user-1',
  name: 'Sam Rivera',
  email: 'sam.rivera@example.com',
};

/** A profile before any resume has been read. */
export const emptyProfile = (): Profile => ({
  firstName: 'Sam',
  middleName: '',
  lastName: 'Rivera',
  email: MOCK_USER.email,
  phone: '',
  street: '',
  street2: '',
  city: '',
  state: '',
  zip: '',
  country: 'United States',
  links: [
    { id: 'web', label: 'Website / portfolio', url: '', fixed: true },
    { id: 'linkedin', label: 'LinkedIn', url: '', fixed: true },
    { id: 'github', label: 'GitHub', url: '', fixed: true },
  ],
  education: [],
  experience: [],
  projects: [],
  skills: [],
  custom: [],
  resume: null,
  unplaced: [],
});

/** What the mock parser "reads" out of any uploaded resume. */
export const parsedProfile = (fileName: string, sizeBytes: number): Profile => ({
  ...emptyProfile(),
  phone: '(555) 010-2233',
  street: '100 Example Street',
  street2: 'Apt 2',
  city: 'Springfield',
  state: 'IL',
  zip: '62701',
  links: [
    { id: 'web', label: 'Website / portfolio', url: '', fixed: true },
    { id: 'linkedin', label: 'LinkedIn', url: 'https://linkedin.com/in/example', fixed: true },
    { id: 'github', label: 'GitHub', url: 'https://github.com/example', fixed: true },
  ],
  education: [
    {
      id: 'ed-1',
      school: 'Example State University',
      degreeType: 'Bachelor of Science (B.S.)',
      major: 'Computer Science',
      gpa: '3.5',
      location: 'Springfield, IL',
      start: '2023-08-28',
      end: '2027-05-15',
      coursework: '',
    },
  ],
  experience: [
    {
      id: 'x-1',
      kind: 'work',
      title: 'Teaching Assistant',
      org: 'Example State University',
      location: 'Springfield, IL',
      start: '2025-01-13',
      end: '',
      current: true,
      detail: 'Held weekly office hours for 60 students\nGraded programming assignments',
    },
  ],
  projects: [
    { id: 'p-1', name: 'Course planner', tech: 'React, TypeScript', detail: '' },
    {
      id: 'p-2',
      name: 'Study group bot',
      tech: 'Python',
      detail: 'Posts daily practice problems to a class chat',
    },
  ],
  skills: ['TypeScript', 'React', 'Python', 'SQL', 'Git'],
  resume: { name: fileName, sizeBytes, pageCount: 1, uploadedAt: new Date().toISOString() },
  unplaced: [
    {
      id: 'un-1',
      text: 'Relevant Coursework: Data Structures, Operating Systems, Software Design',
      suggestion: 'Add to Education',
    },
  ],
});

/** The progress lines the mock parser reports, a couple more on every poll. */
export const PARSE_SECTIONS: ResumeParse['sections'] = [
  { status: 'ok', label: 'Contact info · 4 fields' },
  { status: 'ok', label: 'Education · Example State University' },
  { status: 'ok', label: 'Experience · 1 role' },
  { status: 'ok', label: 'Projects · 2' },
  { status: 'ok', label: 'Skills · 5' },
  { status: 'warn', label: '1 section we couldn’t place' },
];

/** "First Middle Last" for the session's display name, like the backend builds it. */
export const displayName = (profile: Pick<Profile, 'firstName' | 'middleName' | 'lastName'>) =>
  [profile.firstName, profile.middleName, profile.lastName]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(' ');
