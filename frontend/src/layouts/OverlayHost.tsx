import { useOverlays } from '@/app/providers/overlays';
import { ApplicationDrawer } from '@/features/applications/ApplicationDrawer';
import { ReviewModal } from '@/features/applications/ReviewModal';
import { ScreenshotModal } from '@/features/applications/ScreenshotModal';
import { ConfirmProfileModal } from '@/features/inbox/ConfirmProfileModal';
import { JobDrawer } from '@/features/inbox/JobDrawer';
import { DeleteAccountModal } from '@/features/settings/DeleteAccountModal';

/** Renders whichever drawer or dialog is open. Keyed so switching items resets local state. */
export function OverlayHost() {
  const { overlay } = useOverlays();
  switch (overlay?.type) {
    case 'job':
      return <JobDrawer key={overlay.jobId} jobId={overlay.jobId} />;
    case 'application':
      return (
        <ApplicationDrawer key={overlay.applicationId} applicationId={overlay.applicationId} />
      );
    case 'review':
      return <ReviewModal key={overlay.jobId} jobId={overlay.jobId} />;
    case 'screenshot':
      return <ScreenshotModal applicationId={overlay.applicationId} />;
    case 'confirmProfile':
      return <ConfirmProfileModal />;
    case 'deleteAccount':
      return <DeleteAccountModal />;
    default:
      return null;
  }
}
