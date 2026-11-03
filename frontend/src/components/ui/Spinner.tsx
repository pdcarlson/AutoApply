import styles from './Spinner.module.css';

export function Spinner({ label }: { label?: string }) {
  return (
    <span
      className={styles.spinner}
      role={label ? 'status' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  );
}
