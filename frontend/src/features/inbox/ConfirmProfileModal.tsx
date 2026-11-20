/** The modal asking the user to confirm their profile before applying. */
import { useNavigate } from 'react-router';
import { paths } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import styles from './ConfirmProfileModal.module.css';

/** Shown when the user presses Apply before finishing setup. */
export function ConfirmProfileModal() {
  const { close } = useOverlays();
  const navigate = useNavigate();
  const checkProfile = () => {
    close();
    navigate(paths.setupProfile);
  };
  return (
    <Modal labelledBy="confirm-profile-title" onClose={close}>
      <h2 className="h2" id="confirm-profile-title">
        Confirm your profile first
      </h2>
      <p className="ink2">
        Applications only use your profile after you’ve checked it once. It takes about two minutes,
        and nothing is sent until you do.
      </p>
      <div className={styles.row}>
        <Button variant="primary" onClick={checkProfile}>
          Check my profile
        </Button>
        <Button variant="ghost" onClick={close}>
          Not now
        </Button>
      </div>
    </Modal>
  );
}
