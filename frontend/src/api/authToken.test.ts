/** Tests that API requests carry the session token when sign-in provides one. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { authHeaders, authToken, setTokenSource } from './authToken';
import { http } from './client';

afterEach(() => {
  setTokenSource(null);
  vi.unstubAllGlobals();
});

const okJson = () =>
  new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });

describe('auth tokens', () => {
  it('sends nothing when no token source is registered', async () => {
    expect(await authToken()).toBeNull();
    expect(await authHeaders()).toEqual({});
  });

  it('sends the session token with API requests', async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) => Promise.resolve(okJson()));
    vi.stubGlobal('fetch', fetchMock);
    setTokenSource(() => Promise.resolve('token-1'));

    await http.get('/jobs');

    const headers = fetchMock.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer token-1');
  });

  it('asks for a fresh token on every request', async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) => Promise.resolve(okJson()));
    vi.stubGlobal('fetch', fetchMock);
    const tokens = ['first', 'second'];
    setTokenSource(() => Promise.resolve(tokens.shift() ?? null));

    await http.get('/jobs');
    await http.get('/jobs');
    await http.get('/jobs');

    const sent = fetchMock.mock.calls.map(
      (call) => (call[1]?.headers as Record<string, string>).Authorization,
    );
    expect(sent).toEqual(['Bearer first', 'Bearer second', undefined]);
  });
});
