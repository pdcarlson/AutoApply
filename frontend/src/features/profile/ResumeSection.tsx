/** The Profile page's resume file section, with upload and replace. */
import type { ChangeEvent } from 'react';
import type { Profile } from '@/api/types';
import { useReplaceResumeFile } from '@/api/queries';
import { useToast } from '@/app/providers/toast';
import { Panel } from '@/components/ui/Panel';
import { buttonClass } from '@/components/ui/classNames';
import { RESUME_ACCEPT, validateResumeFile } from '@/lib/resumeFile';
import { ResumeFileCard } from '@/components/profile/ResumeFileCard';
import styles from './ResumeSection.module.css';

interface ResumeSectionProps {
  profile: Profile;
}

/** Shows the current resume file and lets the user replace it. */
export function ResumeSection({ profile }: ResumeSectionProps) {
  const notify = useToast();
  const replace = useReplaceResumeFile();

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    const problem = validateResumeFile(file);
    if (problem) {
      notify(`${problem} Your current resume is unchanged.`);
      return;
    }
    replace.mutate(file, {
      onSuccess: (resume) => notify(`Replaced. New applications attach ${resume.name}.`),
      onError: (error) => notify(`${error.message} Your current resume is unchanged.`),
    });
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    handleFile(event.target.files?.[0]);
    // Clear the input so picking the same file again still fires a change.
    event.target.value = '';
  };

  const pickerLabel = replace.isPending
    ? 'Uploading…'
    : profile.resume
      ? 'Replace file'
      : 'Upload a file';
  const picker = (
    <>
      <label className={buttonClass({ size: 'sm' })} htmlFor="resume-replace">
        {pickerLabel}
      </label>
      <input
        id="resume-replace"
        type="file"
        accept={RESUME_ACCEPT}
        hidden
        disabled={replace.isPending}
        onChange={handleInputChange}
      />
    </>
  );

  return (
    <Panel>
      {profile.resume ? (
        <ResumeFileCard bare file={profile.resume} action={picker} />
      ) : (
        <div className={styles.noResume}>
          <span className="small ink2">No resume yet.</span>
          {picker}
        </div>
      )}
      <p className="small ink2">
        Attached to every application exactly as you uploaded it, byte for byte. Replacing it
        doesn’t change applications you’ve already sent.
      </p>
    </Panel>
  );
}
