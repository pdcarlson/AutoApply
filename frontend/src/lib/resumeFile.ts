export const RESUME_MAX_BYTES = 5 * 1024 * 1024;

export const RESUME_ACCEPT =
  '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document';

/** Client-side check before uploading; the backend checks again. Returns a message or null. */
export function validateResumeFile(file: File): string | null {
  const extension = file.name.includes('.') ? file.name.split('.').pop()!.toLowerCase() : '';
  if (extension !== 'pdf' && extension !== 'docx') {
    const kind = extension ? ` is a .${extension} file.` : ' has no file type.';
    return `${file.name}${kind} Upload your resume as a PDF or DOCX.`;
  }
  if (file.size > RESUME_MAX_BYTES) {
    const mb = (file.size / 1024 / 1024).toFixed(1);
    return `${file.name} is ${mb} MB. The limit is 5 MB. Export a smaller PDF and try again.`;
  }
  return null;
}
