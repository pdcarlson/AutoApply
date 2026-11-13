import { describe, expect, it } from 'vitest';
import { FILL_BOOKMARK, FILL_BOOKMARK_SOURCE } from './fillBookmark';

describe('fill bookmark', () => {
  it('is a javascript: link whose code still parses once squeezed onto one line', () => {
    expect(FILL_BOOKMARK.startsWith('javascript:')).toBe(true);
    const code = decodeURIComponent(FILL_BOOKMARK.slice('javascript:'.length));
    expect(code).not.toContain('\n');
    expect(() => new Function(code)).not.toThrow();
  });

  it('only listens to AutoApply on this computer and never submits', () => {
    expect(FILL_BOOKMARK_SOURCE).toContain('event.origin !== AUTOAPPLY');
    expect(FILL_BOOKMARK_SOURCE).toContain("'http://localhost:8080'");
    expect(FILL_BOOKMARK_SOURCE).not.toMatch(/submit\(|btn-submit/);
  });
});
