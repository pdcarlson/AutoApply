import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { authApi } from '@/api/endpoints';
import { queryKeys } from '@/api/queries';
import { paths } from '@/app/paths';
import { Loading } from '@/components/ui/DataDisplay';

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
  const client = useQueryClient();

  useEffect(() => {
    const error = params.get('error');
    if (error) {
      navigate(paths.signIn, {
        replace: true,
        state: { signInError: error === 'access_denied' ? 'cancelled' : 'failed' },
      });
      return;
    }

    let cancelled = false;
    client
      .fetchQuery({ queryKey: queryKeys.session, queryFn: authApi.getSession, staleTime: 0 })
      .then((session) => {
        if (cancelled) return;
        const next = session.profileConfirmed
          ? (safeReturnTo(params.get('returnTo')) ?? paths.inbox)
          : paths.setupResume;
        navigate(next, { replace: true });
      })
      .catch(() => {
        if (!cancelled) navigate(paths.signIn, { replace: true, state: { signInError: 'failed' } });
      });
    return () => {
      cancelled = true;
    };
  }, [params, navigate, client]);

  return <Loading label="Signing you in…" />;
}
