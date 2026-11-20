/** Mock handlers for the agent's settings, status, pause, and resume. */
import { http } from 'msw';
import type { AgentSettings } from '@/api/types';
import { advanceAgent } from '@/mocks/agent';
import { db } from '@/mocks/db';
import { agentStatus } from '@/mocks/wire';
import { apiPath, ok } from './respond';

/** The agent's settings and run state. */
export const agentHandlers = [
  http.get(apiPath('/settings'), async () => {
    return ok(db.settings);
  }),
  http.patch(apiPath('/settings'), async ({ request }) => {
    const patch = (await request.json()) as Partial<AgentSettings>;
    db.settings = { ...db.settings, ...patch };
    // A higher limit lets jobs held for tomorrow go today.
    if (patch.dailyLimit !== undefined && db.sentToday < db.settings.dailyLimit) {
      for (const job of db.jobs) if (job.state === 'waiting') job.state = 'queued';
    }
    return ok(db.settings);
  }),
  http.get(apiPath('/agent/status'), async () => {
    advanceAgent();
    return ok(agentStatus());
  }),
  http.post(apiPath('/agent/pause'), async () => {
    db.paused = true;
    return ok(agentStatus());
  }),
  http.post(apiPath('/agent/resume'), async () => {
    db.paused = false;
    db.lastTick = Date.now();
    return ok(agentStatus());
  }),
];
