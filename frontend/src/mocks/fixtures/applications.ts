/** The applications the mock backend starts with, and confirmation numbers for new ones. */
import type { ApplicationDetail, ApplicationStatus, Ats, TimelineEvent } from '@/api/types';
import { baseFields } from './forms';
import { isoAgo, slugify } from './helpers';
import { screenshotFor } from './screenshot';

const REFERENCE_STEP = 7919;
let referenceSeed = 100_000;

/** A made-up confirmation number in the board's style, e.g. "GH-207919". */
export const nextReference = (ats: string) =>
  `${ats === 'Ashby' ? 'AS' : 'GH'}-${((referenceSeed += REFERENCE_STEP) % 900_000) + 100_000}`;

interface ApplicationSeed {
  id: string;
  company: string;
  role: string;
  location: string;
  ats: Ats;
  /** How many days ago it was sent. */
  days: number;
  status: ApplicationStatus;
}

const APPLICATION_SEEDS: ApplicationSeed[] = [
  {
    id: 'app-201',
    company: 'Cyberdyne Systems',
    role: 'Backend Engineer I',
    location: 'Remote (US)',
    ats: 'Ashby',
    days: 0,
    status: 'submitted',
  },
  {
    id: 'app-202',
    company: 'Soylent Foods',
    role: 'Full-Stack Engineer, Early Career',
    location: 'Remote (US)',
    ats: 'Greenhouse',
    days: 4,
    status: 'submitted',
  },
  {
    id: 'app-203',
    company: 'Vandelay Industries',
    role: 'Junior Mobile Engineer',
    location: 'Remote (US)',
    ats: 'Ashby',
    days: 18,
    status: 'interviewing',
  },
  {
    id: 'app-204',
    company: 'Massive Dynamic',
    role: 'Software Engineer, New Grad',
    location: 'New York, NY',
    ats: 'Greenhouse',
    days: 29,
    status: 'rejected',
  },
];

/** The last timeline step, which depends on where the application stands. */
function latestEvent({ status, days }: ApplicationSeed, submittedAt: string): TimelineEvent {
  if (status === 'interviewing') {
    return {
      kind: 'accent',
      text: 'You marked it Interviewing',
      at: isoAgo(Math.max(0, days - 3)),
    };
  }
  if (status === 'rejected') {
    return { kind: 'red', text: 'You marked it Rejected', at: isoAgo(Math.max(0, days - 5)) };
  }
  return { kind: 'current', text: 'Waiting for a reply', at: submittedAt };
}

/** A sent application built from its seed. */
function makeApplication(seed: ApplicationSeed): ApplicationDetail {
  const { id, company, role, ats, days } = seed;
  const submittedAt = isoAgo(days, 3);
  const fields = baseFields(company);
  const timeline: TimelineEvent[] = [
    { kind: 'muted', text: `New match from ${ats}`, at: isoAgo(days + 1) },
    { kind: 'muted', text: 'You pressed Apply', at: isoAgo(days, 4) },
    { kind: 'accent', text: `Submitted via ${ats}, ${fields.length} fields`, at: submittedAt },
    latestEvent(seed, submittedAt),
  ];
  return {
    id,
    jobId: `job-${id}`,
    company,
    role,
    location: seed.location,
    ats,
    url: `https://boards.greenhouse.io/${slugify(company)}/jobs/${id.replace(/\D/g, '')}`,
    status: seed.status,
    submittedAt,
    submittedBy: 'agent',
    confirmation: { reference: nextReference(ats), confirmedAt: submittedAt },
    isNew: days === 0,
    fields,
    timeline,
    screenshotUrl: screenshotFor({ company, role, fields }),
  };
}

/** The starting list of sent applications, newest first. */
export const seedApplications = (): ApplicationDetail[] => APPLICATION_SEEDS.map(makeApplication);
