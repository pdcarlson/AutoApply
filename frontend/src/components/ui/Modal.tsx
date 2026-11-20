/** A centered dialog over a dimmed page, and its title row. */
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cx } from '@/lib/cx';
import { IconButton } from './Button';
import { Icon } from './Icon';
import { useDialogBehavior } from './useDialogBehavior';
import styles from './Modal.module.css';

interface ModalProps {
  labelledBy: string;
  onClose: () => void;
  wide?: boolean;
  /** As wide as the window allows, for a modal with something to look at beside its text. */
  full?: boolean;
  children: ReactNode;
}

/** Centered dialog; clicking outside it or pressing Escape closes it. */
export function Modal({ labelledBy, onClose, wide, full, children }: ModalProps) {
  const ref = useDialogBehavior(onClose);
  return createPortal(
    <div className={styles.modalLayer}>
      <div className={styles.scrim} onClick={onClose} />
      <div
        ref={ref}
        className={cx(styles.modal, wide && styles.wide, full && styles.full)}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}

interface ModalHeadProps {
  children: ReactNode;
  onClose: () => void;
}

/** Title row for a modal, with a close button. */
export function ModalHead({ children, onClose }: ModalHeadProps) {
  return (
    <div className={styles.modalHead}>
      {children}
      <IconButton label="Close" plain onClick={onClose}>
        <Icon name="close" size={20} />
      </IconButton>
    </div>
  );
}
