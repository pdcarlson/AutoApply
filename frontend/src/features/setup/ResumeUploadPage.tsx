/** The first setup step: upload a resume and watch it being read. */
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useResumeParse, useUploadResume } from '@/api/queries';
import { paths } from '@/app/paths';
import { Button, LinkButton } from '@/components/ui/Button';
import { ErrorBox } from '@/components/ui/Callouts';
import { Loading } from '@/components/ui/LoadStates';
import { SetupFooter } from '@/layouts/SetupFooter';
import { SetupIntro } from '@/layouts/SetupIntro';
import { validateResumeFile } from '@/lib/resumeFile';
import { ResumeDropZone } from './ResumeDropZone';
import { ResumeParseProgress } from './ResumeParseProgress';
import styles from './ResumeUploadPage.module.css';

/** Uploads a resume, shows parse progress, and offers filling the profile by hand. */
export function ResumeUploadPage() {
  const navigate = useNavigate();
  const parse = useResumeParse(true);
  const upload = useUploadResume();
  const [clientError, setClientError] = useState<string | null>(null);

  const current = parse.data;
  const failure = current?.status === 'failed' ? current.error : null;
  const isShowingProgress = current && current.status !== 'failed';
  const uploadError = upload.error?.message ?? null;
  const error = clientError ?? failure?.message ?? uploadError;
  const fillByHand = () => navigate(paths.setupProfile);

  const chooseFile = (file: File | undefined) => {
    if (!file) return;
    const problem = validateResumeFile(file);
    setClientError(problem);
    if (!problem) upload.mutate(file);
  };

  return (
    <>
      <SetupIntro title="Start with your resume">
        We read it once and fill in your profile. You check everything on the next step.
      </SetupIntro>
      <div className={styles.uploadColumn}>
        {error && (
          <ErrorBox>
            <span>{error}</span>
            {failure?.code === 'unreadable' && (
              <span>
                <Button size="xs" onClick={fillByHand}>
                  Fill it in by hand
                </Button>
              </span>
            )}
          </ErrorBox>
        )}
        {parse.isPending ? (
          <Loading />
        ) : isShowingProgress ? (
          <ResumeParseProgress parse={current} />
        ) : (
          <>
            <ResumeDropZone onFile={chooseFile} uploading={upload.isPending} />
            <div className={styles.alternatives}>
              <LinkButton onClick={fillByHand}>
                I don’t have a resume. Fill it in by hand.
              </LinkButton>
            </div>
          </>
        )}
      </div>
      <SetupFooter
        onNext={() => navigate(paths.setupProfile)}
        nextLabel="Check what we pulled"
        nextDisabled={current?.status !== 'done'}
        note={current?.status === 'done' ? null : 'Upload a file to continue'}
      />
    </>
  );
}
