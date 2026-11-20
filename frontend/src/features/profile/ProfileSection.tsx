/** One titled section of the Profile page. */
import type { ReactNode } from 'react';
import { sectionElementId, SECTIONS, type SectionKey } from './sections';
import styles from './ProfileSection.module.css';

interface ProfileSectionProps {
  id: SectionKey;
  children: ReactNode;
}

/** A `<section>` with the section's heading and description above its content. */
export function ProfileSection({ id, children }: ProfileSectionProps) {
  const [title, description] = SECTIONS[id];
  const elementId = sectionElementId(id);
  return (
    <section className={styles.section} id={elementId} aria-labelledby={`${elementId}-title`}>
      <div className={styles.sectionHead}>
        <h2 className="h2" id={`${elementId}-title`}>
          {title}
        </h2>
        <p className="small ink2">{description}</p>
      </div>
      <div className={styles.sectionBody}>{children}</div>
    </section>
  );
}
