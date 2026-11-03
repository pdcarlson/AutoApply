import { useState } from 'react';
import { useNavigate } from 'react-router';
import type { Profile, ProfileUpdate, UnplacedSection } from '@/api/types';
import { useProfile, useResolveUnplaced, useUpdateProfile } from '@/api/queries';
import { paths } from '@/app/paths';
import { Button } from '@/components/ui/Button';
import { ErrorBox, Note, Panel } from '@/components/ui/Callouts';
import { Loading, LoadError } from '@/components/ui/DataDisplay';
import { PillInput } from '@/components/ui/Form';
import { Icon } from '@/components/ui/Icon';
import {
  ContactFields,
  CustomFieldsEditor,
  EntryList,
  LinksEditor,
} from '@/features/profile/editors';
import { SetupFooter, SetupIntro } from '@/layouts/SetupLayout';
import { toProfileUpdate } from '@/features/profile/profileUpdate';
import { ResumeFileCard } from '@/features/profile/ResumeFileCard';
import styles from './setup.module.css';

export function ProfileReviewPage() {
  const profile = useProfile();
  if (profile.isPending) return <Loading />;
  if (profile.isError) return <LoadError what="your profile" onRetry={() => profile.refetch()} />;
  return <ReviewForm profile={profile.data} />;
}

function ReviewForm({ profile }: { profile: Profile }) {
  const navigate = useNavigate();
  const save = useUpdateProfile();
  const resolve = useResolveUnplaced();
  const [draft, setDraft] = useState<ProfileUpdate>(() => toProfileUpdate(profile));
  const patch = (changes: Partial<ProfileUpdate>) => setDraft((d) => ({ ...d, ...changes }));

  const missingName = !draft.name.trim();
  const missingEmail = !draft.email.trim();

  // Accepting moves resume text into the profile on the server, so save edits first, then
  // take the server's merged result as the new draft.
  const resolveUnplaced = async (section: UnplacedSection, action: 'accept' | 'dismiss') => {
    await save.mutateAsync(draft);
    const updated = await resolve.mutateAsync({ id: section.id, action });
    setDraft(toProfileUpdate(updated));
  };

  const unplaced = resolve.data?.unplaced ?? save.data?.unplaced ?? profile.unplaced;

  return (
    <>
      <SetupIntro
        title={profile.resume ? 'Check what we pulled from your resume' : 'Fill in your profile'}
      >
        Fix anything that’s wrong. Nothing here goes into an application until you confirm your
        profile at the end of setup.
      </SetupIntro>
      <div className={styles.review}>
        <div className={styles.reviewAside}>
          {profile.resume ? (
            <ResumeFileCard
              file={profile.resume}
              action={
                <Button size="xs" onClick={() => navigate(paths.setupResume)}>
                  Replace
                </Button>
              }
            />
          ) : (
            <Note title="No resume">
              Fill in what you can. You can upload a resume later under Profile.
            </Note>
          )}
          {unplaced.map((section) => (
            <UnplacedCard
              key={section.id}
              section={section}
              busy={resolve.isPending || save.isPending}
              onResolve={(action) => void resolveUnplaced(section, action)}
            />
          ))}
        </div>
        <div className={styles.reviewSections}>
          <Panel aria-labelledby="review-contact">
            <h2 className="eyebrow" id="review-contact">
              Contact
            </h2>
            <ContactFields value={draft} onChange={patch} />
          </Panel>
          <Panel aria-labelledby="review-links">
            <h2 className="eyebrow" id="review-links">
              Links
            </h2>
            <LinksEditor links={draft.links} onChange={(links) => patch({ links })} />
          </Panel>
          <Panel aria-labelledby="review-education">
            <h2 className="eyebrow" id="review-education">
              Education
            </h2>
            <EntryList
              kind="education"
              entries={draft.education}
              onChange={(education) => patch({ education })}
            />
          </Panel>
          <Panel aria-labelledby="review-experience">
            <h2 className="eyebrow" id="review-experience">
              Experience
            </h2>
            <EntryList
              kind="experience"
              entries={draft.experience}
              onChange={(experience) => patch({ experience })}
            />
          </Panel>
          <Panel aria-labelledby="review-projects">
            <h2 className="eyebrow" id="review-projects">
              Projects
            </h2>
            <EntryList
              kind="projects"
              entries={draft.projects}
              onChange={(projects) => patch({ projects })}
            />
          </Panel>
          <Panel aria-labelledby="review-skills">
            <h2 className="eyebrow" id="review-skills">
              Skills
            </h2>
            <PillInput
              items={draft.skills}
              onChange={(skills) => patch({ skills })}
              label="Skills"
              addLabel="Add skill"
              placeholder="e.g. Docker"
            />
          </Panel>
          <Panel aria-labelledby="review-custom">
            <h2 className="eyebrow" id="review-custom">
              Additional information
            </h2>
            <CustomFieldsEditor fields={draft.custom} onChange={(custom) => patch({ custom })} />
          </Panel>
        </div>
      </div>
      {save.isError && <ErrorBox>We couldn’t save your profile. {save.error.message}</ErrorBox>}
      <SetupFooter
        onNext={() => save.mutate(draft, { onSuccess: () => navigate(paths.setupQuestions) })}
        nextLabel="Looks right, continue"
        loading={save.isPending}
        nextDisabled={missingName || missingEmail}
        note={
          missingName
            ? 'Add your name to continue'
            : missingEmail
              ? 'Add your email to continue'
              : null
        }
      />
    </>
  );
}

function UnplacedCard({
  section,
  busy,
  onResolve,
}: {
  section: UnplacedSection;
  busy: boolean;
  onResolve: (action: 'accept' | 'dismiss') => void;
}) {
  return (
    <div className={styles.unplaced}>
      <span className={styles.unplacedTitle}>
        <Icon name="warn" size={16} />
        <b className="small">A section we couldn’t place</b>
      </span>
      <q>{section.text}</q>
      <div className={styles.row}>
        {section.suggestion && (
          <Button size="xs" disabled={busy} onClick={() => onResolve('accept')}>
            {section.suggestion}
          </Button>
        )}
        <Button size="xs" variant="ghost" disabled={busy} onClick={() => onResolve('dismiss')}>
          Leave it out
        </Button>
      </div>
      <span className="tiny muted">
        Every line of your resume ends up in a field or here, so nothing is lost.
      </span>
    </div>
  );
}
