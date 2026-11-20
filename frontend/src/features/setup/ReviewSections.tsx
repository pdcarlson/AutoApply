/** The profile editors shown while reviewing what setup pulled from the resume. */
import type { ReactNode } from 'react';
import type { ProfileUpdate } from '@/api/types';
import { Panel } from '@/components/ui/Panel';
import { PillInput } from '@/components/ui/PillInput';
import { ContactFields } from '@/components/profile/ContactFields';
import { CustomFieldsEditor } from '@/components/profile/CustomFieldsEditor';
import { EntryList } from '@/components/profile/EntryList';
import { LinksEditor } from '@/components/profile/LinksEditor';
import styles from './ReviewSections.module.css';

interface ReviewSectionsProps {
  draft: ProfileUpdate;
  onChange: (changes: Partial<ProfileUpdate>) => void;
}

/** One panel per part of the profile; edits stay in the draft until Continue. */
export function ReviewSections({ draft, onChange }: ReviewSectionsProps) {
  return (
    <div className={styles.reviewSections}>
      <ReviewPanel id="review-contact" title="Contact">
        <ContactFields value={draft} onChange={onChange} />
      </ReviewPanel>
      <ReviewPanel id="review-links" title="Links">
        <LinksEditor links={draft.links} onChange={(links) => onChange({ links })} />
      </ReviewPanel>
      <ReviewPanel id="review-education" title="Education">
        <EntryList
          kind="education"
          entries={draft.education}
          onChange={(education) => onChange({ education })}
        />
      </ReviewPanel>
      <ReviewPanel id="review-experience" title="Experience">
        <EntryList
          kind="experience"
          entries={draft.experience}
          onChange={(experience) => onChange({ experience })}
        />
      </ReviewPanel>
      <ReviewPanel id="review-projects" title="Projects">
        <EntryList
          kind="projects"
          entries={draft.projects}
          onChange={(projects) => onChange({ projects })}
        />
      </ReviewPanel>
      <ReviewPanel id="review-skills" title="Skills">
        <PillInput
          items={draft.skills}
          onChange={(skills) => onChange({ skills })}
          label="Skills"
          addLabel="Add skill"
          placeholder="e.g. Docker"
        />
      </ReviewPanel>
      <ReviewPanel id="review-custom" title="Additional information">
        <CustomFieldsEditor fields={draft.custom} onChange={(custom) => onChange({ custom })} />
      </ReviewPanel>
    </div>
  );
}

interface ReviewPanelProps {
  /** Id of the heading, which labels the panel. */
  id: string;
  title: string;
  children: ReactNode;
}

function ReviewPanel({ id, title, children }: ReviewPanelProps) {
  return (
    <Panel aria-labelledby={id}>
      <h2 className="eyebrow" id={id}>
        {title}
      </h2>
      {children}
    </Panel>
  );
}
