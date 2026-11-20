/** App-wide toasts: short messages at the bottom of the screen, with optional buttons. */
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
// Longer when there's a button, so there is time to reach it.
const WITH_BUTTON_MS = 7000;

interface ToastProviderProps {
  children: ReactNode;
}

/** One toast at a time; a new one replaces the last. */
export function ToastProvider({ children }: ToastProviderProps) {
  const [toast, setToast] = useState<Toast | null>(null);
  const lastId = useRef(0);

  const notify = useCallback<Notify>((text, options = {}) => {
    lastId.current += 1;
    setToast({ id: lastId.current, text, ...options });
  }, []);
  const dismiss = useCallback(() => setToast(null), []);

  return (
    <ToastContext value={notify}>
      {children}
      {toast && <ToastView key={toast.id} toast={toast} onDone={dismiss} />}
    </ToastContext>
  );
}

interface ToastViewProps {
  toast: Toast;
  onDone: () => void;
}

/** The toast on screen; it closes itself after a few seconds, longer when it has a button. */
function ToastView({ toast, onDone }: ToastViewProps) {
  const hasButton = Boolean(toast.undo || toast.action);

  useEffect(() => {
    const timer = setTimeout(onDone, hasButton ? WITH_BUTTON_MS : PLAIN_MS);
    return () => clearTimeout(timer);
  }, [hasButton, onDone]);

  const closeThen = (action: () => void) => () => {
    onDone();
    action();
  };

  return (
    <div className={styles.toast} role="status">
      <span>{toast.text}</span>
      {toast.undo && (
        <button type="button" className={styles.button} onClick={closeThen(toast.undo)}>
          Undo
        </button>
      )}
      {toast.action && (
        <button type="button" className={styles.button} onClick={closeThen(toast.action.run)}>
          {toast.action.label}
        </button>
      )}
    </div>
  );
}

/** A function that shows a toast. */
export function useToast() {
  const notify = useContext(ToastContext);
  if (!notify) throw new Error('useToast must be used inside ToastProvider');
  return useMemo(() => notify, [notify]);
}
