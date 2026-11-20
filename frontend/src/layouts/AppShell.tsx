/** The frame around every signed-in screen: navigation, the screen, and open overlays. */
import { useEffect } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import { useJobs, useSession, useSignOut } from '@/api/queries';
import { paths } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { useTheme } from '@/app/providers/theme';
import { Count } from '@/components/ui/Badges';
import { IconButton, LinkButton } from '@/components/ui/Button';
import { Brand } from '@/components/ui/Brand';
import { Icon, type IconName } from '@/components/ui/Icon';
import { ApplyingNow } from '@/features/inbox/ApplyingNow';
import { isWaitingOnUser } from '@/lib/jobStatus';
import { cx } from '@/lib/cx';
import { OverlayHost } from './OverlayHost';
import { useJobEventToasts } from './useJobEventToasts';
import styles from './AppShell.module.css';

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
}

const NAV: NavItem[] = [
  { to: paths.inbox, label: 'Inbox', icon: 'inbox' },
  { to: paths.jobs, label: 'Jobs', icon: 'search' },
  { to: paths.applications, label: 'Applications', icon: 'briefcase' },
  { to: paths.profile, label: 'Profile', icon: 'user' },
  { to: paths.answers, label: 'Answer bank', icon: 'list' },
  { to: paths.settings, label: 'Settings', icon: 'sliders' },
];

interface NavCount {
  value: number;
  /** Read after the number, e.g. "3 waiting". */
  label: string;
  /** Dashed badge, and left off the phone tabs. */
  warn?: boolean;
}

/** Badge counts for the nav: jobs waiting on the user, ready to submit, and open questions. */
function useNavCounts(): Partial<Record<string, NavCount>> {
  const { data: jobs = [] } = useJobs();
  return {
    [paths.inbox]: { value: jobs.filter(isWaitingOnUser).length, label: 'waiting' },
    [paths.applications]: {
      value: jobs.filter((job) => job.state === 'ready').length,
      label: 'ready to submit',
    },
    [paths.answers]: {
      value: jobs.filter((job) => job.state === 'needs_input').length,
      label: 'waiting for an answer',
      warn: true,
    },
  };
}

/** Signed-in frame: sidebar on wide screens, bottom tabs on phones. */
export function AppShell() {
  const { pathname } = useLocation();
  useJobEventToasts();

  // Each screen starts at the top unless it scrolls itself to something (e.g. ?job=).
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className={styles.shell}>
      <SideNav />
      <div className={styles.main}>
        <Outlet />
      </div>
      <BottomNav />
      <OverlayHost />
    </div>
  );
}

/** The sidebar on wide screens: links, the agent's progress, the account, and the theme. */
function SideNav() {
  const counts = useNavCounts();
  const session = useSession();
  const user = session.data?.user;
  const signOut = useSignOut();
  const navigate = useNavigate();
  const { open } = useOverlays();
  const handleSignOut = () =>
    signOut.mutate(undefined, { onSettled: () => navigate(paths.signIn) });

  return (
    <aside className={styles.nav}>
      <Link className={styles.brandLink} to={paths.inbox} aria-label="Auto Apply, go to Inbox">
        <Brand />
      </Link>
      <nav className={styles.navLinks} aria-label="Main">
        {NAV.map((item) => {
          const count = counts[item.to];
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => cx(styles.navLink, isActive && styles.on)}
            >
              <span>{item.label}</span>
              {count && count.value > 0 && (
                <Count
                  value={count.value}
                  label={`${count.value} ${count.label}`}
                  warn={count.warn}
                />
              )}
            </NavLink>
          );
        })}
      </nav>
      <div className={styles.run}>
        <ApplyingNow variant="sidebar" />
      </div>
      <div className={styles.foot}>
        <div className={styles.user}>
          <span>{user?.name}</span>
          <span>{user?.email}</span>
          <LinkButton onClick={handleSignOut}>Sign out</LinkButton>
          <LinkButton className={styles.danger} onClick={() => open({ type: 'deleteAccount' })}>
            Delete account
          </LinkButton>
        </div>
        <ThemeToggle />
      </div>
    </aside>
  );
}

/** Switches between light and dark colors. */
function ThemeToggle() {
  const { isDark, setChoice } = useTheme();
  const label = isDark ? 'Switch to light mode' : 'Switch to dark mode';
  return (
    <IconButton label={label} size="sm" onClick={() => setChoice(isDark ? 'light' : 'dark')}>
      <Icon name={isDark ? 'sun' : 'moon'} />
    </IconButton>
  );
}

/** The tab bar on phones. */
function BottomNav() {
  const counts = useNavCounts();
  return (
    <nav className={styles.bottomNav} aria-label="Main">
      {NAV.map((item) => {
        const count = counts[item.to];
        return (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => cx(isActive && styles.on)}
          >
            <Icon name={item.icon} size={22} />
            <span>{item.label}</span>
            {count && count.value > 0 && !count.warn && (
              <span className={styles.badge}>
                <Count value={count.value} label={`${count.value} ${count.label}`} />
              </span>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}
