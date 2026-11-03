import type { ApiErrorBody } from './types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '');

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? {};
  }
}

export const isApiError = (error: unknown, code?: string): error is ApiError =>
  error instanceof ApiError && (code === undefined || error.code === code);

/** Absolute URL for an API path; BASE_URL may be relative (`/api`) or a full origin. */
export const apiUrl = (path: string) =>
  new URL(`${BASE_URL}${path}`, window.location.href).toString();

/** A JSON-serializable object or array, or FormData for file uploads. */
type Body = object;

async function request<T>(method: string, path: string, body?: Body): Promise<T> {
  const isForm = body instanceof FormData;
  const response = await fetch(apiUrl(path), {
    method,
    // The session is an HTTP-only cookie set by the backend.
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(body && !isForm ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<ApiErrorBody> {
  try {
    const body = (await response.json()) as Partial<ApiErrorBody>;
    if (typeof body.code === 'string') {
      return {
        code: body.code,
        message: body.message ?? response.statusText,
        details: body.details,
      };
    }
  } catch {
    // Not JSON; fall through to a generic error.
  }
  return { code: `http_${response.status}`, message: response.statusText || 'Request failed' };
}

/** Downloads a binary response (e.g. the data export) and hands it to the browser as a file. */
async function download(path: string, fallbackName: string): Promise<void> {
  const response = await fetch(apiUrl(path), { credentials: 'include' });
  if (!response.ok) throw new ApiError(response.status, await readError(response));

  const disposition = response.headers.get('Content-Disposition') ?? '';
  const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const link = Object.assign(document.createElement('a'), { href: url, download: name });
  link.click();
  URL.revokeObjectURL(url);
}

export const http = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: Body) => request<T>('POST', path, body),
  put: <T>(path: string, body: Body) => request<T>('PUT', path, body),
  patch: <T>(path: string, body: Body) => request<T>('PATCH', path, body),
  delete: <T = void>(path: string) => request<T>('DELETE', path),
  download,
};
