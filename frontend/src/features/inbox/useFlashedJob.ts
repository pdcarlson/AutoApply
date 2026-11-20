/** Briefly highlights a job row, such as one just added. */
import { useEffect, useState } from 'react';

const FLASH_MS = 2400;

/** Returns the flashing job's id and a setter; the highlight clears itself. */
export function useFlashedJob() {
  const [flashId, setFlashId] = useState<string | null>(null);

  useEffect(() => {
    if (!flashId) return;
    const timer = setTimeout(() => setFlashId(null), FLASH_MS);
    return () => clearTimeout(timer);
  }, [flashId]);

  return [flashId, setFlashId] as const;
}
