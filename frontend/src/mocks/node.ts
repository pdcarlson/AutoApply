/** The mock API as a Node server, for tests. */
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/** The mock API server the test setup starts. */
export const server = setupServer(...handlers);
