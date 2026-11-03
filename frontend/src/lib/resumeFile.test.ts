import { describe, expect, it } from 'vitest';
import { validateResumeFile } from './resumeFile';

const file = (name: string, bytes: number) => new File([new Uint8Array(bytes)], name);

describe('validateResumeFile', () => {
  it('accepts PDF and DOCX up to 5 MB', () => {
    expect(validateResumeFile(file('resume.pdf', 1000))).toBeNull();
    expect(validateResumeFile(file('Resume.DOCX', 1000))).toBeNull();
  });

  it('rejects other types and big files', () => {
    expect(validateResumeFile(file('resume.png', 10))).toMatch(/is a \.png file/);
    expect(validateResumeFile(file('resume', 10))).toMatch(/has no file type/);
    expect(validateResumeFile(file('resume.pdf', 6 * 1024 * 1024))).toMatch(/limit is 5 MB/);
  });
});
