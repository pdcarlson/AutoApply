/** The page the backend returns the browser to after Google sign-in. */
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useFetchFreshSession } from '@/api/queries';
import { paths } from '@/app/paths';
import { Loading } from '@/components/ui/LoadStates';

/** Only same-site paths, so the callback can't be used to redirect somewhere else. */
const safeReturnTo = (value: string | null) =>
  value && value.startsWith('/') && !value.startsWith('//') && value !== '/' ? value : null;

/**
 * Where the backend sends the browser after Google sign-in. By now the session cookie is set
 * (or `?error=` says why not), so load the session and go to the right screen.
 */
export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const fetchFreshSession = useFetchFreshSession();

  useEffect(() => {
    const error = params.get('error');
    if (error) {
      navigate(paths.signIn, {
        replace: true,
        state: { signInError: error === 'access_denied' ? 'cancelled' : 'failed' },
      });
      return;
    }

    let isCancelled = false;
    fetchFreshSession()
      .then((session) => {
        if (isCancelled) return;
        const destination = session.profileConfirmed
          ? (safeReturnTo(params.get('returnTo')) ?? paths.inbox)
          : paths.setupResume;
        navigate(destination, { replace: true });
      })
      .catch(() => {
        if (!isCancelled)
          navigate(paths.signIn, { replace: true, state: { signInError: 'failed' } });
      });
    return () => {
      isCancelled = true;
    };
  }, [params, navigate, fetchFreshSession]);

  return <Loading label="Signing you in…" />;
}
