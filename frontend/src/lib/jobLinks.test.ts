import { describe, expect, it } from 'vitest';
import { checkJobLink } from './jobLinks';

describe('checkJobLink', () => {
  it('accepts Greenhouse and Ashby links and normalizes them', () => {
    expect(checkJobLink('https://boards.greenhouse.io/acme/jobs/123?gh_src=x')).toEqual({
      ok: true,
      ats: 'Greenhouse',
      url: 'https://boards.greenhouse.io/acme/jobs/123',
    });
    expect(checkJobLink('jobs.ashbyhq.com/acme/abc/')).toEqual({
      ok: true,
      ats: 'Ashby',
      url: 'https://jobs.ashbyhq.com/acme/abc',
    });
  });

  it('rejects Lever and other boards', () => {
    const result = checkJobLink('https://jobs.lever.co/acme/123');
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.title).toBe('This site isn’t supported');
  });

  it('rejects text that is not a link', () => {
    const result = checkJobLink('software engineer');
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.title).toBe('That doesn’t look like a link');
  });
});
