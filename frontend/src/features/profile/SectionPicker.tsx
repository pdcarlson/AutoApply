/** Phone-only menu that jumps to a Profile section. */
import { useLocation, useNavigate } from 'react-router';
import { profileSection } from '@/app/paths';
import { SECTION_KEYS, SECTIONS, type SectionKey } from './sections';
import styles from './SectionPicker.module.css';

/** Phone-only jump menu; wide screens scroll the page. */
export function SectionPicker() {
  const { hash } = useLocation();
  const navigate = useNavigate();
  const current = (hash.slice(1) || 'contact') as SectionKey;
  return (
    <label className={styles.picker}>
      Profile section
      <select
        value={current}
        onChange={(event) => navigate(profileSection(event.target.value), { replace: true })}
      >
        {SECTION_KEYS.map((key) => (
          <option key={key} value={key}>
            {SECTIONS[key][0]}
          </option>
        ))}
      </select>
    </label>
  );
}
