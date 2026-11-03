import { useState } from 'react';
import { useNavigate } from 'react-router';
import type { ResumeParse } from '@/api/types';
import { useResumeParse, useUploadResume } from '@/api/queries';
import { paths } from '@/app/paths';
import { Button, LinkButton } from '@/components/ui/Button';
import { buttonClass } from '@/components/ui/classNames';
import { ErrorBox } from '@/components/ui/Callouts';
import { Loading } from '@/components/ui/DataDisplay';
import { Icon } from '@/components/ui/Icon';
import { Spinner } from '@/components/ui/Spinner';
import { SetupFooter, SetupIntro } from '@/layouts/SetupLayout';
import { cx } from '@/lib/cx';
import { RESUME_ACCEPT, validateResumeFile } from '@/lib/resumeFile';
import styles from './setup.module.css';

export function ResumeUploadPage() {
  const navigate = useNavigate();
  const parse = useResumeParse(true);
  const upload = useUploadResume();
  const [clientError, setClientError] = useState<string | null>(null);

  const current = parse.data;
  const failed = current?.status === 'failed' ? current.error : null;
  const showProgress = current && current.status !== 'failed';
  const uploadError = upload.error?.message ?? null;
  const error = clientError ?? failed?.message ?? uploadError;
  const fillByHand = () => navigate(paths.setupProfile);

  const choose = (file: File | undefined) => {
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
            {failed?.code === 'unreadable' && (
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
        ) : showProgress ? (
          <ParseProgress parse={current} />
        ) : (
          <>
            <DropZone onFile={choose} uploading={upload.isPending} />
            <div className={styles.alternatives}>
              <LinkButton onClick={fillByHand}>
                I don’t have a resume. Fill it in by hand.
              </LinkButton>
            </div>
          </>
        )}
        <p className="tiny muted">
          Your resume is encrypted and attached to applications exactly as uploaded.
        </p>
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

function DropZone({
  onFile,
  uploading,
}: {
  onFile: (file: File | undefined) => void;
  uploading: boolean;
}) {
  const [dragging, setDragging] = useState(false);
  return (
    <div
      className={cx(styles.dropZone, dragging && styles.dragging)}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        onFile(e.dataTransfer.files[0]);
      }}
    >
      <span className={styles.dropIcon}>
        <Icon name="upload" size={26} stroke={1.75} />
      </span>
      <span className={styles.dropTitle}>Drop your resume here</span>
      <span className="small muted">PDF or DOCX, up to 5 MB</span>
      {uploading ? (
        <span className={styles.uploading}>
          <Spinner /> Uploading…
        </span>
      ) : (
        <label className={buttonClass({ variant: 'primary' })} htmlFor="resume-file">
          Choose a file
        </label>
      )}
      <input
        id="resume-file"
        type="file"
        accept={RESUME_ACCEPT}
        hidden
        onChange={(e) => {
          onFile(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
    </div>
  );
}

function ParseProgress({ parse }: { parse: ResumeParse }) {
  const parsing = parse.status === 'parsing';
  return (
    <div className={styles.parse} aria-live="polite">
      <div className={styles.parseHead}>
        {parsing ? <Spinner /> : <Icon name="check" size={18} stroke={2.5} />}
        <span className={styles.parseHeadText}>
          <b className="small">
            {parsing ? `Reading ${parse.file.name}…` : `Read ${parse.file.name}`}
          </b>
          <span className="tiny muted">
            {parsing ? 'Usually under 15 seconds' : 'Done. Check it on the next step.'}
          </span>
        </span>
      </div>
      <ul className={styles.parseList}>
        {parse.sections.map((section) => (
          <li key={section.label} className={cx(section.status === 'warn' && styles.warn)}>
            <Icon
              name={section.status === 'warn' ? 'warn' : 'check'}
              size={16}
              stroke={section.status === 'warn' ? 2 : 2.5}
            />
            {section.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
