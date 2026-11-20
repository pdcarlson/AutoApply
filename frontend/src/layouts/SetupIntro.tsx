/** The title and lead paragraph at the top of a setup step. */
import type { ReactNode } from 'react';
import styles from './SetupIntro.module.css';

interface SetupIntroProps {
  title: string;
  children: ReactNode;
}

/** Title and lead paragraph at the top of a setup step. */
export function SetupIntro({ title, children }: SetupIntroProps) {
  return (
    <div className={styles.intro}>
      <h1 className="h1">{title}</h1>
      <p className="lede">{children}</p>
    </div>
  );
}
