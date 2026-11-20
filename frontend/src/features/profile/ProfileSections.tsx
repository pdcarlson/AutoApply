/** Every editable section of the Profile page, each saved on its own. */
import type { Profile } from '@/api/types';
import { Panel } from '@/components/ui/Panel';
import { PillInput } from '@/components/ui/PillInput';
import { ContactFields } from '@/components/profile/ContactFields';
import { CustomFieldsEditor } from '@/components/profile/CustomFieldsEditor';
import { EntryList } from '@/components/profile/EntryList';
import { LinksEditor } from '@/components/profile/LinksEditor';
import { missingName, pickContact } from '@/lib/profileUpdate';
import { ProfileSection } from './ProfileSection';
import { ResumeSection } from './ResumeSection';
import { SaveRow } from './SaveRow';
import { useProfileDraft } from './useProfileDraft';
import { useScrollToHashSection } from './useScrollToHashSection';

const ENTRY_SAVED_MESSAGE = 'Saved. Applications use this from now on.';

interface ProfileSectionsProps {
  profile: Profile;
}

/** Contact, links, entries, skills, custom fields and resume, each with its own save. */
export function ProfileSections({ profile }: ProfileSectionsProps) {
  const { draft, patch, saveFields, isSaving } = useProfileDraft(profile);
  useScrollToHashSection();

  const nameMissing = missingName(draft);
  const contactBlockedReason = nameMissing && `Add your ${nameMissing} to save`;

  return (
    <>
      <ProfileSection id="contact">
        <Panel>
          <ContactFields value={draft} onChange={patch} />
        </Panel>
        <SaveRow
          isSaving={isSaving}
          blockedReason={contactBlockedReason}
          onSave={() => saveFields(pickContact(draft))}
        />
      </ProfileSection>
      <ProfileSection id="links">
        <Panel>
          <LinksEditor links={draft.links} onChange={(links) => patch({ links })} />
        </Panel>
        <SaveRow isSaving={isSaving} onSave={() => saveFields({ links: draft.links })} />
      </ProfileSection>
      <ProfileSection id="education">
        <EntryList
          kind="education"
          entries={draft.education}
          onChange={(education) => patch({ education })}
          onCommit={(education) => saveFields({ education }, ENTRY_SAVED_MESSAGE)}
          saving={isSaving}
        />
      </ProfileSection>
      <ProfileSection id="experience">
        <EntryList
          kind="experience"
          entries={draft.experience}
          onChange={(experience) => patch({ experience })}
          onCommit={(experience) => saveFields({ experience }, ENTRY_SAVED_MESSAGE)}
          saving={isSaving}
        />
      </ProfileSection>
      <ProfileSection id="projects">
        <EntryList
          kind="projects"
          entries={draft.projects}
          onChange={(projects) => patch({ projects })}
          onCommit={(projects) => saveFields({ projects }, ENTRY_SAVED_MESSAGE)}
          saving={isSaving}
        />
      </ProfileSection>
      <ProfileSection id="skills">
        <Panel>
          <PillInput
            items={draft.skills}
            onChange={(skills) => saveFields({ skills }, 'Skills saved.')}
            label="Skills"
            addLabel="Add skill"
            placeholder="e.g. Docker"
          />
        </Panel>
      </ProfileSection>
      <ProfileSection id="custom">
        <Panel>
          <CustomFieldsEditor fields={draft.custom} onChange={(custom) => patch({ custom })} />
        </Panel>
        <SaveRow isSaving={isSaving} onSave={() => saveFields({ custom: draft.custom })} />
      </ProfileSection>
      <ProfileSection id="resume">
        <ResumeSection profile={profile} />
      </ProfileSection>
    </>
  );
}
