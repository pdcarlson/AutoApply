/** Mock handlers for the profile, the resume, common questions, and job preferences. */
import { http } from 'msw';
import type { CommonAnswers, JobPreferences, ProfileUpdate, ResumeFile } from '@/api/types';
import { RESUME_MAX_BYTES } from '@/lib/resumeFile';
import { db } from '@/mocks/db';
import { emptyProfile, PARSE_SECTIONS, parsedProfile } from '@/mocks/fixtures/profile';
import { currentSession } from '@/mocks/wire';
import { apiPath, fail, isFile, latency, notFound, ok, unauthenticated } from './respond';

const RESUME_TYPES = /\.(pdf|docx)$/i;
/** How many more parse progress lines show up on each poll. */
const SECTIONS_PER_POLL = 2;

/** The stored description of an uploaded resume file. */
const describeFile = (file: File): ResumeFile => ({
  name: file.name,
  sizeBytes: file.size,
  pageCount: 1,
  uploadedAt: new Date().toISOString(),
});

const profileHandlers = [
  http.get(apiPath('/profile'), async () => {
    await latency();
    return db.signedIn ? ok(db.profile) : unauthenticated();
  }),
  http.put(apiPath('/profile'), async ({ request }) => {
    await latency();
    const update = (await request.json()) as ProfileUpdate;
    db.profile = { ...db.profile, ...update };
    return ok(db.profile);
  }),
  http.post(apiPath('/profile/unplaced/:id'), async ({ params, request }) => {
    await latency();
    const { action } = (await request.json()) as { action: 'accept' | 'dismiss' };
    const section = db.profile.unplaced.find((unplaced) => unplaced.id === params.id);
    if (!section) return notFound('Section');
    if (action === 'accept' && db.profile.education[0]) {
      db.profile.education[0].coursework = section.text.replace(/^Relevant Coursework:\s*/i, '');
    }
    db.profile.unplaced = db.profile.unplaced.filter((unplaced) => unplaced.id !== section.id);
    return ok(db.profile);
  }),
  http.post(apiPath('/profile/confirm'), async () => {
    await latency();
    db.session.profileConfirmed = true;
    return ok(currentSession());
  }),
];

const resumeHandlers = [
  http.post(apiPath('/resume'), async ({ request }) => {
    await latency();
    const file = (await request.formData()).get('file');
    if (!isFile(file)) return fail(422, 'invalid_type', 'Upload your resume as a PDF or DOCX.');
    if (!RESUME_TYPES.test(file.name)) {
      return fail(
        422,
        'invalid_type',
        `${file.name} isn’t a PDF or DOCX. Upload your resume as a PDF or DOCX.`,
      );
    }
    if (file.size > RESUME_MAX_BYTES) {
      return fail(422, 'too_large', `${file.name} is over the 5 MB limit.`);
    }
    const resume = describeFile(file);
    db.resumeParse = { status: 'parsing', file: resume, sections: [], error: null };
    db.profile = { ...emptyProfile(), resume };
    return ok(db.resumeParse, 202);
  }),
  http.get(apiPath('/resume/parse'), async () => {
    await latency();
    const parse = db.resumeParse;
    if (!parse) return notFound('Resume');
    if (parse.status === 'parsing') {
      parse.sections = PARSE_SECTIONS.slice(0, parse.sections.length + SECTIONS_PER_POLL);
      if (parse.sections.length >= PARSE_SECTIONS.length) {
        parse.status = 'done';
        db.profile = parsedProfile(parse.file.name, parse.file.sizeBytes);
      }
    }
    return ok(parse);
  }),
  http.put(apiPath('/resume/file'), async ({ request }) => {
    await latency();
    const file = (await request.formData()).get('file');
    if (!isFile(file) || !RESUME_TYPES.test(file.name)) {
      return fail(422, 'invalid_type', 'Upload your resume as a PDF or DOCX.');
    }
    db.profile.resume = describeFile(file);
    return ok(db.profile.resume);
  }),
];

const answerHandlers = [
  http.get(apiPath('/common-answers'), async () => {
    await latency();
    return ok(db.commonAnswers);
  }),
  http.put(apiPath('/common-answers'), async ({ request }) => {
    await latency();
    db.commonAnswers = (await request.json()) as CommonAnswers;
    return ok(db.commonAnswers);
  }),
  http.get(apiPath('/preferences'), async () => {
    await latency();
    return ok(db.preferences);
  }),
  http.put(apiPath('/preferences'), async ({ request }) => {
    db.preferences = (await request.json()) as JobPreferences;
    return ok(db.preferences);
  }),
];

/** Everything the setup steps and the Profile screen call. */
export const setupHandlers = [...profileHandlers, ...resumeHandlers, ...answerHandlers];
