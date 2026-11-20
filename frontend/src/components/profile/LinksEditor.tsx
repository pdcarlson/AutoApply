/** Editor for the profile's links (website, LinkedIn, GitHub and custom ones). */
import type { ProfileLink } from '@/api/types';
import { IconButton } from '@/components/ui/Button';
import { inputClass } from '@/components/ui/classNames';
import { Icon } from '@/components/ui/Icon';
import { newId } from '@/lib/newId';
import { AddButton } from './AddButton';
import styles from './KeyValueList.module.css';

const FIXED_LINK_PLACEHOLDERS: Record<string, string> = {
  Website: 'https://yourname.dev',
  'Website / portfolio': 'https://yourname.dev',
  LinkedIn: 'https://linkedin.com/in/…',
  GitHub: 'https://github.com/…',
};

interface LinksEditorProps {
  links: ProfileLink[];
  onChange: (links: ProfileLink[]) => void;
}

/** Rows of link name and URL; fixed links keep their name and can't be removed. */
export function LinksEditor({ links, onChange }: LinksEditorProps) {
  const updateLink = (id: string, patch: Partial<ProfileLink>) =>
    onChange(links.map((link) => (link.id === id ? { ...link, ...patch } : link)));
  const removeLink = (id: string) => onChange(links.filter((link) => link.id !== id));
  const addLink = () =>
    onChange([...links, { id: newId('link'), label: '', url: '', fixed: false }]);

  return (
    <div className={styles.list}>
      {links.map((link) => (
        <div key={link.id} className={styles.row}>
          {link.fixed ? (
            <label className={styles.label} htmlFor={`link-${link.id}`}>
              {link.label}
            </label>
          ) : (
            <input
              className={inputClass()}
              aria-label="Link name"
              placeholder="Name, e.g. Blog"
              value={link.label}
              onChange={(event) => updateLink(link.id, { label: event.target.value })}
            />
          )}
          <input
            id={`link-${link.id}`}
            className={inputClass()}
            type="url"
            inputMode="url"
            placeholder={FIXED_LINK_PLACEHOLDERS[link.label] ?? 'https://'}
            value={link.url}
            onChange={(event) => updateLink(link.id, { url: event.target.value })}
          />
          {link.fixed ? (
            <span />
          ) : (
            <IconButton
              plain
              label={`Remove ${link.label || 'link'}`}
              onClick={() => removeLink(link.id)}
            >
              <Icon name="close" size={16} />
            </IconButton>
          )}
        </div>
      ))}
      <AddButton onClick={addLink}>Add another link</AddButton>
    </div>
  );
}
