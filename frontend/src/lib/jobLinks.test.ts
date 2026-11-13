import { describe, expect, it } from 'vitest';
import { checkJobLink } from './jobLinks';

describe('checkJobLink', () => {
  it('accepts Greenhouse, Ashby and Lever links and normalizes them', () => {
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
    expect(checkJobLink('https://jobs.lever.co/acme/123/apply')).toEqual({
      ok: true,
      ats: 'Lever',
      url: 'https://jobs.lever.co/acme/123/apply',
    });
  });

  it('rejects other boards and names the supported ones', () => {
    const result = checkJobLink('https://www.linkedin.com/jobs/view/1');
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.title).toBe('This site isn’t supported');
      expect(result.text).toContain('Greenhouse, Ashby and Lever links');
    }
  });

  it('rejects text that is not a link', () => {
    const result = checkJobLink('software engineer');
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.title).toBe('That doesn’t look like a link');
  });
});
