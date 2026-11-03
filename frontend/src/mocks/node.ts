import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/** The same mock API, for tests running in Node. */
export const server = setupServer(...handlers);
