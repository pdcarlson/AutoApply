/** Banner pointing to Inbox questions the agent is waiting on. */
import { useNavigate } from 'react-router';
import { useJobs } from '@/api/queries';
import { inboxJob } from '@/app/paths';
import { Dot } from '@/components/ui/Badges';
import { Button } from '@/components/ui/Button';
import { Banner } from '@/components/ui/Callouts';
import { plural } from '@/lib/format';

/** Shows the first waiting question and a link to answer it; renders nothing if none wait. */
export function WaitingQuestionBanner() {
  const navigate = useNavigate();
  const jobs = useJobs().data ?? [];
  const waiting = jobs.filter((job) => job.state === 'needs_input' && job.question);
  const first = waiting[0];
  if (!first?.question) return null;

  return (
    <Banner
      tone="amber"
      leading={<Dot tone="amber" />}
      title={`${plural(waiting.length, 'question', 'questions')} waiting for an answer`}
      action={
        <Button size="sm" onClick={() => navigate(inboxJob(first.id))}>
          Answer in Inbox
        </Button>
      }
    >
      {first.company}’s form asks: “{first.question.field}”
    </Banner>
  );
}
