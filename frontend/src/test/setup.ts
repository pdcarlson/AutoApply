import '@testing-library/jest-dom/vitest';
import { Blob as NodeBlob, File as NodeFile } from 'node:buffer';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest';
import { createDb, resetDb } from '@/mocks/db';
import { server } from '@/mocks/node';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
beforeEach(() => resetDb(createDb()));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

// fetch in tests is Node's (undici), which loses the file name when it serializes jsdom's
// FormData/File. Use Node's own File, Blob, and FormData so uploads keep their names. Node's
// FormData constructor isn't a global here, so take it from a parsed request body.
const nodeFormData = await new Request('http://localhost/', {
  method: 'POST',
  body: new URLSearchParams('a=b'),
}).formData();
globalThis.FormData = nodeFormData.constructor as typeof FormData;
globalThis.File = NodeFile as unknown as typeof File;
globalThis.Blob = NodeBlob as unknown as typeof Blob;

// jsdom doesn't implement these.
window.matchMedia ??= ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: () => undefined,
  removeEventListener: () => undefined,
  addListener: () => undefined,
  removeListener: () => undefined,
  dispatchEvent: () => false,
})) as typeof window.matchMedia;
Element.prototype.scrollIntoView ??= () => undefined;
