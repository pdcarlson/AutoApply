/** The second setup step: check and fix the profile pulled from the resume. */
import { useNavigate } from 'react-router';
import type { Profile, ProfileUpdate } from '@/api/types';
import { useProfile } from '@/api/queries';
import { paths } from '@/app/paths';
import { Button } from '@/components/ui/Button';
import { ErrorBox, Note } from '@/components/ui/Callouts';
import { Loading, LoadError } from '@/components/ui/LoadStates';
import { missingName } from '@/lib/profileUpdate';
import { ResumeFileCard } from '@/components/profile/ResumeFileCard';
import { SetupFooter } from '@/layouts/SetupFooter';
import { SetupIntro } from '@/layouts/SetupIntro';
import { ReviewSections } from './ReviewSections';
import { UnplacedCard } from './UnplacedCard';
import { useReviewDraft } from './useReviewDraft';
import styles from './ProfileReviewPage.module.css';

/** Loads the profile and shows the review form. */
export function ProfileReviewPage() {
  const profile = useProfile();
  if (profile.isPending) return <Loading />;
  if (profile.isError) return <LoadError what="your profile" onRetry={() => profile.refetch()} />;
  return <ReviewForm profile={profile.data} />;
}

/** Why Continue is disabled, or null when the profile has what setup needs. */
function continueBlockedReason(draft: ProfileUpdate) {
  const nameMissing = missingName(draft);
  if (nameMissing) return `Add your ${nameMissing} to continue`;
  if (!draft.email.trim()) return 'Add your email to continue';
  return null;
}

interface ReviewFormProps {
  profile: Profile;
}

function ReviewForm({ profile }: ReviewFormProps) {
  const navigate = useNavigate();
  const { draft, patch, resolveUnplaced, save, unplaced, isResolving } = useReviewDraft(profile);
  const blockedReason = continueBlockedReason(draft);
  const title = profile.resume ? 'Check what we pulled from your resume' : 'Fill in your profile';

  return (
    <>
      <SetupIntro title={title}>
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
              busy={isResolving}
              onResolve={(action) => void resolveUnplaced(section, action)}
            />
          ))}
        </div>
        <ReviewSections draft={draft} onChange={patch} />
      </div>
      {save.isError && <ErrorBox>We couldn’t save your profile. {save.error.message}</ErrorBox>}
      <SetupFooter
        onNext={() => save.mutate(draft, { onSuccess: () => navigate(paths.setupQuestions) })}
        nextLabel="Looks right, continue"
        loading={save.isPending}
        nextDisabled={blockedReason !== null}
        note={blockedReason}
      />
    </>
  );
}
