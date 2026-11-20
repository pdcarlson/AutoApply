/** A panel that slides in from the right, and the sections inside it. */
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { IconButton } from './Button';
import { Icon } from './Icon';
import { useDialogBehavior } from './useDialogBehavior';
import styles from './Drawer.module.css';

interface DrawerProps {
  labelledBy: string;
  onClose: () => void;
  head: ReactNode;
  footer?: ReactNode;
  /** Shown to the left of the drawer, in the rest of the window (wide screens only). */
  aside?: ReactNode;
  children: ReactNode;
}

/** Panel that slides in from the right, for details about one job or application. */
export function Drawer({ labelledBy, onClose, head, footer, aside, children }: DrawerProps) {
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
        {aside && <div className={styles.drawerAside}>{aside}</div>}
      </div>
    </>,
    document.body,
  );
}

interface DrawerSectionProps {
  title: string;
  /** Muted text at the right of the section's title. */
  aside?: ReactNode;
  children: ReactNode;
}

/** A titled block inside a drawer. */
export function DrawerSection({ title, aside, children }: DrawerSectionProps) {
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
