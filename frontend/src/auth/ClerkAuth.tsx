/** Sign-in through Clerk, wrapped around the app when Clerk is configured. */
import { ClerkProvider, useAuth, useClerk } from '@clerk/react';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, type ReactNode } from 'react';
import { paths } from '@/app/paths';
import { Loading } from '@/components/ui/LoadStates';
import { AuthActionsContext, type AuthActions } from './actions';
import { clerkKey } from './config';

interface ClerkAuthProps {
  children: ReactNode;
}

/** Sign-in through Clerk (Google). Loaded only when VITE_CLERK_PUBLISHABLE_KEY is set. */
export function ClerkAuth({ children }: ClerkAuthProps) {
  return (
    <ClerkProvider publishableKey={clerkKey} afterSignOutUrl={paths.signIn}>
      <ClerkBridge>{children}</ClerkBridge>
    </ClerkProvider>
  );
}

/**
 * Supplies Clerk's sign-in actions to the app. `/session` stays the app's own source of truth,
 * so the route guards work the same as with the local sign-in.
 */
function ClerkBridge({ children }: ClerkAuthProps) {
  const clerk = useClerk();
  const { isLoaded, userId } = useAuth();
  const client = useQueryClient();

  // Signed in or out somewhere else (another tab, an expired session): start over with
  // whoever is signed in now, so one person's cached data is never shown to the next.
  const lastUser = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (!isLoaded) return;
    const current = userId ?? null;
    if (lastUser.current !== undefined && lastUser.current !== current) {
      void client.resetQueries();
    }
    lastUser.current = current;
  }, [isLoaded, userId, client]);

  const actions = useMemo<AuthActions>(
    () => ({
      google: true,
      startSignIn: async (returnTo) => {
        const done = `${paths.authCallback}?returnTo=${encodeURIComponent(returnTo)}`;
        if (clerk.session) {
          // Already signed in with Clerk; only the app's own session needs loading.
          window.location.assign(done);
          return;
        }
        if (!clerk.client) throw new Error('Sign-in is not ready yet.');
        await clerk.client.signIn.authenticateWithRedirect({
          strategy: 'oauth_google',
          redirectUrl: paths.ssoCallback,
          redirectUrlComplete: done,
        });
      },
      signOut: () => clerk.signOut(),
      afterAccountDeleted: () => clerk.signOut({ redirectUrl: paths.accountDeleted }),
    }),
    [clerk],
  );

  if (!isLoaded) return <Loading />;
  return <AuthActionsContext.Provider value={actions}>{children}</AuthActionsContext.Provider>;
}
