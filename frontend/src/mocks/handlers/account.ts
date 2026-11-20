/** Mock handlers for the session, and for exporting or deleting the account. */
import { http, HttpResponse } from 'msw';
import { db, resetDb } from '@/mocks/db';
import { currentSession } from '@/mocks/wire';
import { apiPath, ok, unauthenticated } from './respond';

/** Session, export, and account deletion. */
export const accountHandlers = [
  http.get(apiPath('/session'), async () => {
    return db.signedIn ? ok(currentSession()) : unauthenticated();
  }),
  http.get(apiPath('/account/export'), async () => {
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
    resetDb();
    return ok();
  }),
];
