/** App-wide state for which drawer or dialog is open. */
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

/** Dialogs and drawers any screen can open. AppShell renders whichever is open. */
export type Overlay =
  | { type: 'job'; jobId: string }
  | { type: 'application'; applicationId: string }
  | { type: 'review'; jobId: string }
  | { type: 'screenshot'; applicationId: string }
  | { type: 'confirmProfile' }
  | { type: 'deleteAccount' };

interface OverlayContextValue {
  overlay: Overlay | null;
  open: (overlay: Overlay) => void;
  close: () => void;
}

const OverlayContext = createContext<OverlayContextValue | null>(null);

interface OverlayProviderProps {
  children: ReactNode;
}

/** Holds the open overlay; at most one is open at a time. */
export function OverlayProvider({ children }: OverlayProviderProps) {
  const [overlay, setOverlay] = useState<Overlay | null>(null);
  const value = useMemo(
    () => ({ overlay, open: setOverlay, close: () => setOverlay(null) }),
    [overlay],
  );
  return <OverlayContext value={value}>{children}</OverlayContext>;
}

/** The open overlay, and functions to open another or close it. */
export function useOverlays() {
  const value = useContext(OverlayContext);
  if (!value) throw new Error('useOverlays must be used inside OverlayProvider');
  return value;
}
