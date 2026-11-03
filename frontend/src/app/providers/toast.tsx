import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import styles from './toast.module.css';

interface ToastOptions {
  /** Shows an Undo button that runs this. */
  undo?: () => void;
  /** Shows a second button, e.g. "Review it". */
  action?: { label: string; run: () => void };
}

interface Toast extends ToastOptions {
  id: number;
  text: string;
}

type Notify = (text: string, options?: ToastOptions) => void;

const ToastContext = createContext<Notify | null>(null);

const PLAIN_MS = 5000;
const WITH_BUTTON_MS = 7000;

/** One toast at a time; a new one replaces the last. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const seq = useRef(0);

  const notify = useCallback<Notify>((text, options = {}) => {
    seq.current += 1;
    setToast({ id: seq.current, text, ...options });
  }, []);
  const dismiss = useCallback(() => setToast(null), []);

  return (
    <ToastContext value={notify}>
      {children}
      {toast && <ToastView key={toast.id} toast={toast} onDone={dismiss} />}
    </ToastContext>
  );
}

function ToastView({ toast, onDone }: { toast: Toast; onDone: () => void }) {
  const hasButton = Boolean(toast.undo || toast.action);

  useEffect(() => {
    const timer = setTimeout(onDone, hasButton ? WITH_BUTTON_MS : PLAIN_MS);
    return () => clearTimeout(timer);
  }, [hasButton, onDone]);

  const run = (fn: () => void) => () => {
    onDone();
    fn();
  };

  return (
    <div className={styles.toast} role="status">
      <span>{toast.text}</span>
      {toast.undo && (
        <button type="button" className={styles.button} onClick={run(toast.undo)}>
          Undo
        </button>
      )}
      {toast.action && (
        <button type="button" className={styles.button} onClick={run(toast.action.run)}>
          {toast.action.label}
        </button>
      )}
    </div>
  );
}

export function useToast() {
  const notify = useContext(ToastContext);
  if (!notify) throw new Error('useToast must be used inside ToastProvider');
  return useMemo(() => notify, [notify]);
}
