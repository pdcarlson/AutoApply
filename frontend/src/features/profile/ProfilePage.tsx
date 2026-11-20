/** The Profile screen: everything the agent fills forms from. */
import { useProfile } from '@/api/queries';
import { Loading, LoadError } from '@/components/ui/LoadStates';
import { Page, PageTitle } from '@/layouts/Page';
import { ProfileSections } from './ProfileSections';
import { SectionPicker } from './SectionPicker';
import styles from './ProfilePage.module.css';

/** Loads the profile and shows its sections. */
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
