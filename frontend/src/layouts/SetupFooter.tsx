/** The Back / Continue row under a setup step. */
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { cx } from '@/lib/cx';
import styles from './SetupFooter.module.css';

interface SetupFooterProps {
  onBack?: () => void;
  onNext: () => void;
  nextLabel: string;
  nextDisabled?: boolean;
  loading?: boolean;
  /** Why Next is disabled, shown beside it. */
  note?: string | null;
}

/** Back / Continue row under a setup step's content. */
export function SetupFooter({
  onBack,
  onNext,
  nextLabel,
  nextDisabled,
  loading,
  note,
}: SetupFooterProps) {
  return (
    <footer className={styles.foot}>
      {onBack && (
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
      )}
      <div className={styles.footRight}>
        {note && <span className={cx('small muted', styles.footNote)}>{note}</span>}
        <Button variant="primary" disabled={nextDisabled} loading={loading} onClick={onNext}>
          {nextLabel}
          <Icon name="right" size={16} stroke={2} />
        </Button>
      </div>
    </footer>
  );
}
