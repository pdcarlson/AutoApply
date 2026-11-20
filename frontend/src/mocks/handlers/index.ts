/** Every mock API handler, backed by the in-memory db. Dev and tests only. */
import { accountHandlers } from './account';
import { agentHandlers } from './agent';
import { answerBankHandlers } from './answers';
import { applicationHandlers } from './applications';
import { jobHandlers } from './jobs';
import { postingHandlers } from './postings';
import { questionHandlers } from './questions';
import { setupHandlers } from './setup';
import { submissionHandlers } from './submissions';

/** The handlers MSW serves, for the browser worker and the test server. */
export const handlers = [
  ...accountHandlers,
  ...setupHandlers,
  ...agentHandlers,
  ...jobHandlers,
  ...submissionHandlers,
  ...postingHandlers,
  ...questionHandlers,
  ...applicationHandlers,
  ...answerBankHandlers,
];
