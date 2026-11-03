import { Navigate, Outlet, useLocation } from 'react-router';
import { useSession } from '@/api/queries';
import { Loading, LoadError } from '@/components/ui/DataDisplay';
import { paths } from './paths';

/** Sends signed-out visitors to sign in, remembering where they were headed. */
export function RequireSession() {
  const session = useSession();
  const location = useLocation();

  if (session.isPending) return <Loading />;
  if (session.isError) return <LoadError what="your account" onRetry={() => session.refetch()} />;
  if (!session.data) {
    return (
      <Navigate to={paths.signIn} replace state={{ from: location.pathname + location.search }} />
    );
  }
  return <Outlet />;
}

/** Signed-in visitors skip the sign-in page. */
export function RedirectIfSignedIn() {
  const session = useSession();
  if (session.isPending) return <Loading />;
  if (session.data) {
    return (
      <Navigate to={session.data.profileConfirmed ? paths.inbox : paths.setupResume} replace />
    );
  }
  return <Outlet />;
}
