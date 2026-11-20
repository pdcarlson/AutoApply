/** The form's fixed options as buttons, for fields that only take one of them. */
import { useId, useState } from 'react';
import { Button } from '@/components/ui/Button';
import styles from './OptionPicker.module.css';

/** Option lists longer than this get a filter box above the buttons. */
const BUTTONS_WITHOUT_FILTER = 12;
/** How many matching options a filtered list shows at once. */
const SHOWN_WHEN_FILTERED = 12;

interface OptionPickerProps {
  options: string[];
  disabled: boolean;
  onPick: (value: string) => void;
  isError: boolean;
}

/** One button per option; a long list gets a filter box that only narrows the list. */
export function OptionPicker({ options, disabled, onPick, isError }: OptionPickerProps) {
  const [filter, setFilter] = useState('');
  const filterId = useId();
  const isLong = options.length > BUTTONS_WITHOUT_FILTER;
  const wanted = filter.trim().toLowerCase();
  const matches = wanted
    ? options.filter((option) => option.toLowerCase().includes(wanted))
    : options;
  const shown = isLong ? matches.slice(0, SHOWN_WHEN_FILTERED) : matches;
  const hiddenCount = matches.length - shown.length;

  return (
    <>
      {isLong && (
        <div className={styles.filter}>
          <label className="sr-only" htmlFor={filterId}>
            Filter options
          </label>
          <input
            id={filterId}
            type="search"
            placeholder={`Filter ${options.length} options…`}
            value={filter}
            autoComplete="off"
            onChange={(event) => setFilter(event.target.value)}
          />
        </div>
      )}
      <div className={styles.row} role="group" aria-label="Options">
        {!isLong && <span className="small">Pick one:</span>}
        {shown.map((option) => (
          <Button key={option} size="sm" disabled={disabled} onClick={() => onPick(option)}>
            {option}
          </Button>
        ))}
        {shown.length === 0 && <span className="small muted">No option matches that.</span>}
      </div>
      {hiddenCount > 0 && (
        <span className="tiny muted">
          {hiddenCount} more {hiddenCount === 1 ? 'option matches' : 'options match'}. Keep typing
          to narrow the list.
        </span>
      )}
      {isError && (
        <span className="tiny" role="alert">
          That didn’t go through. Try again.
        </span>
      )}
      <span className="tiny muted">
        This field only takes one of the form’s options. You’ll see your pick before it’s used.
      </span>
    </>
  );
}
