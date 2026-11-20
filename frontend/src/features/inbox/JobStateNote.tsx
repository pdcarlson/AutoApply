/** The note in the "Watch it fill" drawer explaining what the job is waiting for. */
import type { Job } from '@/api/types';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Note } from '@/components/ui/Callouts';
import { VerificationCodeForm } from '@/components/jobs/VerificationCodeForm';

interface JobStateNoteProps {
  job: Job;
}

/** A note for ready, waiting and handoff jobs; a code form when the site emailed one. */
export function JobStateNote({ job }: JobStateNoteProps) {
  const { close } = useOverlays();
  const notify = useToast();

  if (job.state === 'ready') {
    return (
      <Note tone="teal" title="Ready for your review">
        Every field is filled. The agent stopped before Submit and waits for you to approve it.
      </Note>
    );
  }
  if (job.state === 'needs_input') {
    return (
      <Note tone="amber" title="Waiting for you">
        The agent moved on to other jobs. Answer the question in your Inbox and this one picks up
        where it stopped.
      </Note>
    );
  }
  if (job.state !== 'handoff') return null;
  if (!job.asksForCode) {
    return (
      <Note tone="amber" title="Stopped at a CAPTCHA">
        Finish it on {job.company}’s site. These are the answers to copy over.
      </Note>
    );
  }
  return (
    <>
      <Note tone="amber" title={`${job.ats} emailed you a verification code`}>
        The agent pressed Submit and the form is still open. Enter the code to finish.
      </Note>
      <VerificationCodeForm
        job={job}
        onSubmitted={(application) => {
          close();
          notify(`Submitted to ${application.company}. Their confirmation page came back.`);
        }}
      />
    </>
  );
}
