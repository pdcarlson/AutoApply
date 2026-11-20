/** The buttons along the bottom of the "Watch it fill" drawer. */
import { useNavigate } from 'react-router';
import type { Job } from '@/api/types';
import { useMarkSubmitted, usePauseToggle } from '@/api/queries';
import { inboxJob } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';

interface JobDrawerFooterProps {
  job: Job;
}

/** The next step for the job's state, plus a pause/resume button for the queue. */
export function JobDrawerFooter({ job }: JobDrawerFooterProps) {
  const { close, open } = useOverlays();
  const navigate = useNavigate();
  const notify = useToast();
  const { paused, pending, toggle } = usePauseToggle();
  const markSubmitted = useMarkSubmitted();

  const answerInInbox = () => {
    close();
    navigate(inboxJob(job.id));
  };
  const handleMarkSubmitted = () =>
    markSubmitted.mutate(job.id, {
      onSuccess: () => {
        close();
        notify(`Marked as submitted. ${job.company} is in Applications.`);
      },
    });

  return (
    <>
      {job.state === 'ready' && (
        <Button variant="primary" grow onClick={() => open({ type: 'review', jobId: job.id })}>
          Review and submit
        </Button>
      )}
      {job.state === 'needs_input' && (
        <Button variant="primary" grow onClick={answerInInbox}>
          Answer in Inbox
        </Button>
      )}
      {job.state === 'handoff' && !job.asksForCode && (
        <Button
          variant="primary"
          grow
          loading={markSubmitted.isPending}
          onClick={handleMarkSubmitted}
        >
          I submitted it
        </Button>
      )}
      <Button disabled={pending} onClick={toggle}>
        <Icon name={paused ? 'play' : 'pause'} size={15} />
        {paused ? 'Resume queue' : 'Pause queue'}
      </Button>
    </>
  );
}
