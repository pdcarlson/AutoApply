/** Banners at the top of the Inbox: ready to review, queue paused, profile unconfirmed. */
import { Link, useNavigate } from 'react-router';
import { useJobs, useSession } from '@/api/queries';
import { paths } from '@/app/paths';
import { Button } from '@/components/ui/Button';
import { buttonClass } from '@/components/ui/classNames';
import { Banner } from '@/components/ui/Callouts';
import { plural } from '@/lib/format';

interface InboxBannersProps {
  paused: boolean;
  onResume: () => void;
}

/** Shows only the banners that apply right now. */
export function InboxBanners({ paused, onResume }: InboxBannersProps) {
  const navigate = useNavigate();
  const session = useSession();
  const readyCount = (useJobs().data ?? []).filter((job) => job.state === 'ready').length;
  const isProfileUnconfirmed = Boolean(session.data && !session.data.profileConfirmed);

  return (
    <>
      {readyCount > 0 && (
        <Banner
          icon="check"
          title={`${plural(readyCount, 'application is', 'applications are')} ready to submit`}
          action={
            <Button
              size="sm"
              variant="primary"
              onClick={() => navigate(`${paths.applications}?filter=ready`)}
            >
              Review
            </Button>
          }
        >
          The agent filled {readyCount === 1 ? 'it' : 'them'} and stopped. Review and approve before
          anything is sent.
        </Banner>
      )}
      {paused && (
        <Banner
          tone="amber"
          icon="pause"
          action={
            <Button size="sm" onClick={onResume}>
              Resume
            </Button>
          }
        >
          The queue is paused. Nothing new is submitted until you resume.
        </Banner>
      )}
      {isProfileUnconfirmed && (
        <Banner
          tone="amber"
          icon="warn"
          title="Your profile isn’t confirmed yet."
          action={
            <Link className={buttonClass({ size: 'sm' })} to={paths.setupProfile}>
              Check my profile
            </Link>
          }
        >
          Applications only use your profile after you’ve checked it once.
        </Banner>
      )}
    </>
  );
}
