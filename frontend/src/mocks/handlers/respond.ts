/** Shared building blocks for the mock API's request handlers. */
import { HttpResponse, type JsonBodyType } from 'msw';
import { db } from '@/mocks/db';

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '');

/** The full URL pattern MSW matches for an API path such as `/jobs/:id`. */
export const apiPath = (path: string) => `${API_BASE}${path}`;

/** A success response (204 when there is no body). */
export function ok(body?: JsonBodyType, status = 200) {
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
