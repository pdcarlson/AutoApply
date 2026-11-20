/** Local state for the confidence threshold slider and number box. */
import { useState } from 'react';
import { useUpdateAgentSettings } from '@/api/queries';
import { useToast } from '@/app/providers/toast';

const MAX_THRESHOLD = 100;

/** Keeps the slider and text box in step, and saves a new threshold once it's settled. */
export function useThresholdDraft(saved: number) {
  const notify = useToast();
  const update = useUpdateAgentSettings();
  const [value, setValue] = useState(saved);
  const [text, setText] = useState(String(saved));
  const [error, setError] = useState<string | null>(null);

  const commit = (next: number) => {
    if (next === saved) return;
    update.mutate(
      { confidenceThreshold: next },
      {
        onSuccess: () =>
          notify(`Threshold set to ${next}. It applies from the next field the agent fills.`),
      },
    );
  };

  /** Moves the slider; the save happens when the pointer or key is released. */
  const slideTo = (next: string) => {
    setValue(Number(next));
    setText(next);
    setError(null);
  };

  /** Validates the typed number and saves it, or explains what's wrong. */
  const commitText = () => {
    const trimmed = text.trim();
    const typed = Number(trimmed);
    if (!/^\d{1,3}$/.test(trimmed) || typed > MAX_THRESHOLD) {
      setError(`Enter a whole number from 0 to 100. Your threshold is still ${saved}.`);
      return;
    }
    setError(null);
    setValue(typed);
    commit(typed);
  };

  return { value, text, error, setText, slideTo, commitSlider: () => commit(value), commitText };
}
