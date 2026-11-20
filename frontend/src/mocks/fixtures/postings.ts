/** The open postings on the mock job board, already ranked by fit. */
import type { Ats, Posting } from '@/api/types';
import { isoAgo, slugify } from './helpers';

interface PostingSeed {
  id: string;
  company: string;
  role: string;
  location: string;
  ats: Ats;
  ageDays: number;
  score: number;
  reasons: string[];
}

const POSTING_SEEDS: PostingSeed[] = [
  {
    id: 'p-2001',
    company: 'Northwind Data',
    role: 'Software Engineer Intern',
    location: 'Remote (US)',
    ats: 'Greenhouse',
    ageDays: 2,
    score: 92,
    reasons: ['Close to Software engineer', 'Asks for Python, SQL', 'Internship', 'In Remote (US)'],
  },
  {
    id: 'p-2002',
    company: 'Brightline Robotics',
    role: 'Frontend Engineer',
    location: 'Chicago, IL',
    ats: 'Ashby',
    ageDays: 5,
    score: 74,
    reasons: ['Close to Frontend', 'Asks for React, TypeScript'],
  },
  {
    id: 'p-2003',
    company: 'Harbor Freight Analytics',
    role: 'Data Analyst',
    location: 'Austin, TX',
    ats: 'Greenhouse',
    ageDays: 9,
    score: 26,
    reasons: ['Asks for SQL'],
  },
  {
    id: 'p-2004',
    company: 'Kestrel Health',
    role: 'Account Executive',
    location: 'London',
    ats: 'Ashby',
    ageDays: 12,
    score: 9,
    reasons: [],
  },
];

/** An open posting built from its seed. */
function makePosting(seed: PostingSeed): Posting {
  const company = slugify(seed.company);
  return {
    id: seed.id,
    company: seed.company,
    role: seed.role,
    location: seed.location,
    ats: seed.ats,
    url:
      seed.ats === 'Greenhouse'
        ? `https://boards.greenhouse.io/${company}/jobs/${seed.id.replace(/\D/g, '')}`
        : `https://jobs.ashbyhq.com/${company}/${seed.id}`,
    postedAt: isoAgo(seed.ageDays),
    internship: /intern/i.test(seed.role),
    fit: { score: seed.score, reasons: [...seed.reasons] },
    status: 'open',
    jobId: null,
  };
}

/** The starting job board. */
export const seedPostings = (): Posting[] => POSTING_SEEDS.map(makePosting);
