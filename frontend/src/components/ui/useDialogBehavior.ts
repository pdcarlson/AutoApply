/** Keyboard and focus handling shared by modals and drawers. */
import { useEffect, useRef } from 'react';

const FOCUSABLE = 'input, select, textarea, button, [href], [tabindex]:not([tabindex="-1"])';

/** Focuses the first control on open, closes on Escape, and gives focus back on close. */
export function useDialogBehavior(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  // Kept in a ref so a new onClose each render doesn't re-run the open/close effect.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCloseRef.current();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previous?.focus?.();
    };
  }, []);

  return ref;
}
