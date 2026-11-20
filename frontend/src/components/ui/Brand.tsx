/** The Auto Apply logo and name. */
import { cx } from '@/lib/cx';
import styles from './Brand.module.css';

interface BrandProps {
  large?: boolean;
}

/** The "AA" mark beside the product name. */
export function Brand({ large }: BrandProps) {
  return (
    <span className={cx(styles.brand, large && styles.brandLarge)}>
      <span className={styles.brandMark} aria-hidden="true">
        AA
      </span>
      <span>Auto Apply</span>
    </span>
  );
}
