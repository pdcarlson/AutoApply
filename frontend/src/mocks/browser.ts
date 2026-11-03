import { setupWorker } from 'msw/browser';
import { createDb, resetDb } from './db';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);

/** Console helpers for development, e.g. `autoApplyMocks.reset()` to start over signed out. */
declare global {
  interface Window {
    autoApplyMocks?: { reset: () => void };
  }
}

window.autoApplyMocks = {
  reset: () => {
    resetDb(createDb());
    window.location.assign('/');
  },
};
