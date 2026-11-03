import { useEffect, useState, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router';
import type { Profile, ProfileUpdate } from '@/api/types';
import {
  useCommonAnswers,
  usePreferences,
  useProfile,
  useReplaceResumeFile,
  useUpdateCommonAnswers,
  useUpdatePreferences,
  useUpdateProfile,
} from '@/api/queries';
import { profileSection } from '@/app/paths';
import { useToast } from '@/app/providers/toast';
import { Button } from '@/components/ui/Button';
import { buttonClass } from '@/components/ui/classNames';
import { Panel } from '@/components/ui/Callouts';
import { Loading, LoadError } from '@/components/ui/DataDisplay';
import { Choice, PillInput } from '@/components/ui/Form';
import { Page, PageTitle } from '@/layouts/Page';
import { RESUME_ACCEPT, validateResumeFile } from '@/lib/resumeFile';
import { ContactFields, CustomFieldsEditor, EntryList, LinksEditor, type Contact } from './editors';
import { toProfileUpdate } from './profileUpdate';
import { ResumeFileCard } from './ResumeFileCard';
import styles from './ProfilePage.module.css';

const SECTIONS = {
  contact: [
    'Contact',
    'How employers reach you. Pulled from your resume; every field is editable.',
  ],
  links: ['Links', 'Portfolio, LinkedIn, GitHub, and anything else forms ask you to link.'],
  education: ['Education', 'Every school with degree, major, GPA, dates, and coursework.'],
  experience: ['Experience', 'Roles from your resume. The agent only writes from what’s here.'],
  projects: ['Projects', 'What you’ve built. Forms often ask what your part was and who used it.'],
  skills: ['Skills', 'Used to check postings against your profile.'],
  custom: [
    'Additional information',
    'Your own fields. Name it the way forms ask for it, then type the value.',
  ],
  preferences: [
    'Job preferences',
    'Hard preferences. A posting that misses one never reaches your Inbox.',
  ],
  resume: ['Resume file', 'The file attached to every application.'],
} as const;

type SectionKey = keyof typeof SECTIONS;
const SECTION_KEYS = Object.keys(SECTIONS) as SectionKey[];

export function ProfilePage() {
  const profile = useProfile();
  return (
    <Page>
      <SectionPicker />
      <div className={styles.narrow}>
        <PageTitle
          title="Profile"
          lede="Everything the agent fills forms from, on one page. Pulled from your resume; every field is editable."
        />
      </div>
      {profile.isPending ? (
        <Loading />
      ) : profile.isError ? (
        <LoadError what="your profile" onRetry={() => profile.refetch()} />
      ) : (
        <ProfileSections profile={profile.data} />
      )}
    </Page>
  );
}

/** Phone-only jump menu; wide screens scroll the page. */
function SectionPicker() {
  const { hash } = useLocation();
  const navigate = useNavigate();
  const current = (hash.slice(1) || 'contact') as SectionKey;
  return (
    <label className={styles.picker}>
      Profile section
      <select
        value={current}
        onChange={(e) => navigate(profileSection(e.target.value), { replace: true })}
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

function ProfileSections({ profile }: { profile: Profile }) {
  const { hash } = useLocation();
  const notify = useToast();
  const save = useUpdateProfile();
  const [draft, setDraft] = useState<ProfileUpdate>(() => toProfileUpdate(profile));

  // Scroll to the section named in the URL hash (#education etc.).
  useEffect(() => {
    const key = hash.slice(1);
    if (key) document.getElementById(`profile-${key}`)?.scrollIntoView({ block: 'start' });
  }, [hash]);

  const patch = (changes: Partial<ProfileUpdate>) => setDraft((d) => ({ ...d, ...changes }));

  /** Saves just these fields on top of what's on the server, so other sections' edits stay drafts. */
  const saveFields = (
    changes: Partial<ProfileUpdate>,
    message = 'Saved. The next application uses these.',
  ) => {
    patch(changes);
    save.mutate({ ...toProfileUpdate(profile), ...changes }, { onSuccess: () => notify(message) });
  };

  const contact: Contact = draft;
  const saveButton = (fields: Partial<ProfileUpdate>) => (
    <div>
      <Button
        variant="primary"
        size="sm"
        loading={save.isPending}
        onClick={() => saveFields(fields)}
      >
        Save changes
      </Button>
    </div>
  );

  return (
    <>
      <Section id="contact">
        <Panel>
          <ContactFields value={contact} onChange={patch} />
        </Panel>
        {saveButton({
          name: draft.name,
          email: draft.email,
          phone: draft.phone,
          street: draft.street,
          street2: draft.street2,
          city: draft.city,
          state: draft.state,
          zip: draft.zip,
          country: draft.country,
        })}
      </Section>
      <Section id="links">
        <Panel>
          <LinksEditor links={draft.links} onChange={(links) => patch({ links })} />
        </Panel>
        {saveButton({ links: draft.links })}
      </Section>
      <Section id="education">
        <EntryList
          kind="education"
          entries={draft.education}
          onChange={(education) => patch({ education })}
          onCommit={(education) =>
            saveFields({ education }, 'Saved. Applications use this from now on.')
          }
          saving={save.isPending}
        />
      </Section>
      <Section id="experience">
        <EntryList
          kind="experience"
          entries={draft.experience}
          onChange={(experience) => patch({ experience })}
          onCommit={(experience) =>
            saveFields({ experience }, 'Saved. Applications use this from now on.')
          }
          saving={save.isPending}
        />
      </Section>
      <Section id="projects">
        <EntryList
          kind="projects"
          entries={draft.projects}
          onChange={(projects) => patch({ projects })}
          onCommit={(projects) =>
            saveFields({ projects }, 'Saved. Applications use this from now on.')
          }
          saving={save.isPending}
        />
      </Section>
      <Section id="skills">
        <Panel>
          <PillInput
            items={draft.skills}
            onChange={(skills) => saveFields({ skills }, 'Skills saved.')}
            label="Skills"
            addLabel="Add skill"
            placeholder="e.g. Docker"
          />
        </Panel>
      </Section>
      <Section id="custom">
        <Panel>
          <CustomFieldsEditor fields={draft.custom} onChange={(custom) => patch({ custom })} />
        </Panel>
        {saveButton({ custom: draft.custom })}
      </Section>
      <Section id="preferences">
        <PreferencesSection />
      </Section>
      <Section id="resume">
        <ResumeSection profile={profile} />
      </Section>
    </>
  );
}

function Section({ id, children }: { id: SectionKey; children: ReactNode }) {
  const [title, description] = SECTIONS[id];
  return (
    <section
      className={styles.section}
      id={`profile-${id}`}
      aria-labelledby={`profile-${id}-title`}
    >
      <div className={styles.sectionHead}>
        <h2 className="h2" id={`profile-${id}-title`}>
          {title}
        </h2>
        <p className="small ink2">{description}</p>
      </div>
      <div className={styles.sectionBody}>{children}</div>
    </section>
  );
}

function PreferencesSection() {
  const preferences = usePreferences();
  const common = useCommonAnswers();
  const savePrefs = useUpdatePreferences();
  const saveCommon = useUpdateCommonAnswers();

  if (preferences.isPending || common.isPending) return <Loading />;
  if (preferences.isError || common.isError) {
    return (
      <LoadError
        what="your preferences"
        onRetry={() => {
          void preferences.refetch();
          void common.refetch();
        }}
      />
    );
  }
  const prefs = preferences.data;

  return (
    <>
      <Panel>
        <span className="eyebrow">Role types</span>
        <PillInput
          items={prefs.roleTypes}
          onChange={(roleTypes) => savePrefs.mutate({ ...prefs, roleTypes })}
          label="Role types"
          addLabel="Add role type"
          placeholder="e.g. Data"
        />
      </Panel>
      <Panel>
        <span className="eyebrow">Job type</span>
        <Choice
          type="checkbox"
          checked={prefs.fullTime}
          onChange={() => savePrefs.mutate({ ...prefs, fullTime: !prefs.fullTime })}
        >
          Full-time, new grad
        </Choice>
        <Choice
          type="checkbox"
          checked={prefs.internship}
          onChange={() => savePrefs.mutate({ ...prefs, internship: !prefs.internship })}
        >
          Internship
        </Choice>
      </Panel>
      <Panel>
        <span className="eyebrow">Locations</span>
        <PillInput
          items={common.data.locations}
          onChange={(locations) => saveCommon.mutate({ ...common.data, locations })}
          label="Locations"
          addLabel="Add place"
          placeholder="City, State"
        />
      </Panel>
      <Panel>
        <span className="eyebrow">How new jobs are found</span>
        <p className="small ink2">
          Every morning Auto Apply reads new postings from public Greenhouse and Ashby job boards.
          Postings that meet all of your preferences land in your Inbox, newest first, with a
          one-line reason. Nothing is submitted until you review and approve it.
        </p>
      </Panel>
    </>
  );
}

function ResumeSection({ profile }: { profile: Profile }) {
  const notify = useToast();
  const replace = useReplaceResumeFile();

  const onFile = (file: File | undefined) => {
    if (!file) return;
    const problem = validateResumeFile(file);
    if (problem) {
      notify(`${problem} Your current resume is unchanged.`);
      return;
    }
    replace.mutate(file, {
      onSuccess: (resume) => notify(`Replaced. New applications attach ${resume.name}.`),
      onError: (error) => notify(`${error.message} Your current resume is unchanged.`),
    });
  };

  const picker = (
    <>
      <label className={buttonClass({ size: 'sm' })} htmlFor="resume-replace">
        {replace.isPending ? 'Uploading…' : profile.resume ? 'Replace file' : 'Upload a file'}
      </label>
      <input
        id="resume-replace"
        type="file"
        accept={RESUME_ACCEPT}
        hidden
        disabled={replace.isPending}
        onChange={(e) => {
          onFile(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
    </>
  );

  return (
    <Panel>
      {profile.resume ? (
        <ResumeFileCard bare file={profile.resume} action={picker} />
      ) : (
        <div className={styles.noResume}>
          <span className="small ink2">No resume yet.</span>
          {picker}
        </div>
      )}
      <p className="small ink2">
        Attached to every application exactly as you uploaded it, byte for byte. Replacing it
        doesn’t change applications you’ve already sent.
      </p>
    </Panel>
  );
}
