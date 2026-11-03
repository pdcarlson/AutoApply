import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAnswers, useApplications, useDeleteAccount, useSession } from '@/api/queries';
import { paths } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { Button } from '@/components/ui/Button';
import { ErrorBox } from '@/components/ui/Callouts';
import { TextField } from '@/components/ui/Form';
import { Icon } from '@/components/ui/Icon';
import { Modal } from '@/components/ui/Overlay';
import { plural } from '@/lib/format';
import styles from './DeleteAccountModal.module.css';

/** Lists what will be removed and asks the user to type DELETE first. */
export function DeleteAccountModal() {
  const { close } = useOverlays();
  const navigate = useNavigate();
  const email = useSession().data?.user.email;
  const answerCount = useAnswers().data?.length;
  const appCount = useApplications().data?.length;
  const remove = useDeleteAccount();
  const [confirmText, setConfirmText] = useState('');
  const confirmed = confirmText.trim().toUpperCase() === 'DELETE';

  const removed = [
    'Your profile and resume file',
    answerCount === undefined
      ? 'Your saved answers'
      : plural(answerCount, 'saved answer', 'saved answers'),
    `${appCount === undefined ? 'Your applications' : plural(appCount, 'application', 'applications')}, with what was sent and the screenshots`,
    'Your job preferences and agent controls',
  ];

  return (
    <Modal labelledBy="delete-title" onClose={close}>
      <h2 className="h2" id="delete-title">
        Delete your account?
      </h2>
      <p className="ink2">This removes everything Auto Apply has{email ? ` for ${email}` : ''}:</p>
      <ul className={styles.list}>
        {removed.map((item) => (
          <li key={item}>
            <Icon name="close" size={14} stroke={2.4} />
            {item}
          </li>
        ))}
      </ul>
      <p className="small ink2">
        Applications already submitted stay with the employers. This can’t be undone.
      </p>
      <TextField
        label="Type DELETE to confirm"
        autoComplete="off"
        value={confirmText}
        onChange={setConfirmText}
      />
      {remove.isError && (
        <ErrorBox>We couldn’t delete your account. {remove.error.message}</ErrorBox>
      )}
      <div className={styles.buttons}>
        <Button
          variant="dangerSolid"
          disabled={!confirmed}
          loading={remove.isPending}
          onClick={() =>
            remove.mutate(undefined, {
              onSuccess: () => {
                close();
                navigate(paths.accountDeleted, { replace: true });
              },
            })
          }
        >
          Delete everything
        </Button>
        <Button variant="ghost" onClick={close}>
          Cancel
        </Button>
      </div>
    </Modal>
  );
}
