/** What signing in and out do, provided through context so tests can supply their own. */
import { createContext, useContext } from 'react';

/** Signing in and out through Clerk. */
export interface AuthActions {
  /** Starts Google sign-in; the browser ends up on `/auth/callback?returnTo=…`. */
  startSignIn: (returnTo: string) => Promise<void>;
  /** Ends the session. */
  signOut: () => Promise<void>;
  /** After DELETE /account: signs out and goes to the account-deleted page. */
  afterAccountDeleted: () => Promise<void>;
}

/** Holds the sign-in actions; `ClerkAuth` provides them in the app. */
export const AuthActionsContext = createContext<AuthActions | null>(null);

/** The sign-in actions. */
export function useAuthActions() {
  const actions = useContext(AuthActionsContext);
  if (!actions) throw new Error('useAuthActions needs an AuthActionsContext provider.');
  return actions;
}
