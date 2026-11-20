/** Shared building blocks for the mock API's request handlers. */
import { delay, HttpResponse, type JsonBodyType } from 'msw';
import { db, persist } from '@/mocks/db';

const IS_TEST = import.meta.env.MODE === 'test';
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '');
const LATENCY_MS = 250;

/** The full URL pattern MSW matches for an API path such as `/jobs/:id`. */
export const apiPath = (path: string) => `${API_BASE}${path}`;

/** Realistic-feeling latency in the browser; none in tests. */
export const latency = () => (IS_TEST ? Promise.resolve() : delay(LATENCY_MS));

/** A longer wait for slow work such as opening a posting or submitting a form; none in tests. */
export const slowWork = (ms: number) => delay(IS_TEST ? 0 : ms);

/** A success response (204 when there is no body). Saves the state first. */
export function ok(body?: JsonBodyType, status = 200) {
  persist();
  return body === undefined
    ? new HttpResponse(null, { status: 204 })
    : HttpResponse.json(body, { status });
}

/** An error response in the API's `{ code, message, details }` shape. */
export const fail = (
  status: number,
  code: string,
  message: string,
  details?: Record<string, unknown>,
) => HttpResponse.json({ code, message, details }, { status });

/** 401 for requests made while signed out. */
export const unauthenticated = () => fail(401, 'unauthenticated', 'Sign in to continue.');

/** 404 naming what wasn't found. */
export const notFound = (what: string) => fail(404, 'not_found', `${what} not found.`);

/** The job with this id, from a route param. */
export const findJob = (id: string | readonly string[] | undefined) =>
  db.jobs.find((job) => job.id === id);

/** FormData file entries; checked by shape because jsdom and Node have different File classes. */
export const isFile = (value: FormDataEntryValue | null): value is File =>
  typeof value === 'object' && value !== null && 'name' in value && 'size' in value;
