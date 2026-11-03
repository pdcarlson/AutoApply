import { describe, expect, it } from 'vitest';
import { daysAgo, formatSpan, graduationOptions, plural, toBullets } from './format';

describe('format', () => {
  it('pluralizes', () => {
    expect(plural(1, 'job', 'jobs')).toBe('1 job');
    expect(plural(3, 'job', 'jobs')).toBe('3 jobs');
  });

  it('counts days ago from today', () => {
    const now = new Date(2026, 9, 20, 15);
    expect(daysAgo(new Date(2026, 9, 20, 9).toISOString(), now)).toBe('today');
    expect(daysAgo(new Date(2026, 9, 16, 9).toISOString(), now)).toBe('4 days ago');
  });

  it('formats date spans with open ends', () => {
    expect(formatSpan('', '')).toBe('');
    expect(formatSpan('2024-05-13', '', true)).toBe('May 13, 2024 – Present');
    expect(formatSpan('', '2027-05-15')).toBe('Start ? – May 15, 2027');
  });

  it('splits descriptions into bullets', () => {
    expect(toBullets('- Built it\n\n• Shipped it\n  * Kept it')).toEqual([
      'Built it',
      'Shipped it',
      'Kept it',
    ]);
  });

  it('offers only upcoming graduation terms', () => {
    const options = graduationOptions(new Date(2026, 8, 1), 2);
    expect(options[0]).toBe('December 2026');
    expect(options).toContain('May 2027');
    expect(options).not.toContain('May 2026');
  });
});
