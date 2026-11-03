import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cx } from '@/lib/cx';
import { IconButton } from './Button';
import { Icon } from './Icon';
import styles from './Overlay.module.css';

const FOCUSABLE = 'input, select, textarea, button, [href], [tabindex]:not([tabindex="-1"])';

/** Focuses the first control on open, closes on Escape, and gives focus back on close. */
function useDialogBehavior(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCloseRef.current();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previous?.focus?.();
    };
  }, []);

  return ref;
}

interface ModalProps {
  labelledBy: string;
  onClose: () => void;
  wide?: boolean;
  children: ReactNode;
}

export function Modal({ labelledBy, onClose, wide, children }: ModalProps) {
  const ref = useDialogBehavior(onClose);
  return createPortal(
    <div className={styles.modalLayer}>
      <div className={styles.scrim} onClick={onClose} />
      <div
        ref={ref}
        className={cx(styles.modal, wide && styles.wide)}
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

/** Title row for a modal, with a close button. */
export function ModalHead({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className={styles.modalHead}>
      {children}
      <IconButton label="Close" plain onClick={onClose}>
        <Icon name="close" size={20} />
      </IconButton>
    </div>
  );
}

interface DrawerProps {
  labelledBy: string;
  onClose: () => void;
  head: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}

/** Panel that slides in from the right, for details about one job or application. */
export function Drawer({ labelledBy, onClose, head, footer, children }: DrawerProps) {
  const ref = useDialogBehavior(onClose);
  return createPortal(
    <>
      <div className={styles.scrim} onClick={onClose} />
      <div
        ref={ref}
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
      >
        <div className={styles.drawerHead}>
          {head}
          <IconButton label="Close" plain className={styles.drawerClose} onClick={onClose}>
            <Icon name="close" size={20} />
          </IconButton>
        </div>
        <div className={styles.drawerBody}>{children}</div>
        {footer && <div className={styles.drawerFoot}>{footer}</div>}
      </div>
    </>,
    document.body,
  );
}

export function DrawerSection({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className={styles.drawerSection}>
      <div className={styles.drawerSectionHead}>
        <h3 className="eyebrow">{title}</h3>
        {aside && <span className="tiny muted">{aside}</span>}
      </div>
      {children}
    </section>
  );
}
