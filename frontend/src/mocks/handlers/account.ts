/** Mock handlers for signing in and out, and for exporting or deleting the account. */
import { http, HttpResponse } from 'msw';
import { db, resetDb } from '@/mocks/db';
import { currentSession } from '@/mocks/wire';
import { apiPath, latency, ok, unauthenticated } from './respond';

/** Session, sign-in, sign-out, export, and account deletion. */
export const accountHandlers = [
  http.get(apiPath('/session'), async () => {
    await latency();
    return db.signedIn ? ok(currentSession()) : unauthenticated();
  }),
  http.post(apiPath('/auth/google'), async () => {
    await latency();
    // The real backend returns Google's URL; the mock skips Google and comes straight back.
    db.signedIn = true;
    return ok({ authorizationUrl: '/auth/callback' });
  }),
  http.post(apiPath('/auth/logout'), async () => {
    db.signedIn = false;
    return ok();
  }),
  http.get(apiPath('/account/export'), async () => {
    await latency();
    const data = {
      profile: db.profile,
      commonAnswers: db.commonAnswers,
      preferences: db.preferences,
      answers: db.answers,
      applications: db.applications.map(({ screenshotUrl: _screenshotUrl, ...rest }) => rest),
    };
    return new HttpResponse(JSON.stringify(data, null, 2), {
      headers: {
        'Content-Type': 'application/json',
        'Content-Disposition': 'attachment; filename="auto-apply-export.json"',
      },
    });
  }),
  http.delete(apiPath('/account'), async () => {
    await latency();
    resetDb();
    return ok();
  }),
];
