/** What signing in and out do, provided through context so either sign-in can supply it. */
import { createContext, useContext } from 'react';
import { authApi } from '@/api/endpoints';

/** What signing in and out mean for the sign-in the app was built with. */
export interface AuthActions {
  /** True when sign-in really goes to Google (Clerk). */
  google: boolean;
  /** Starts sign-in; the browser ends up on `/auth/callback?returnTo=…`. */
  startSignIn: (returnTo: string) => Promise<void>;
  /** Ends the session. */
  signOut: () => Promise<void>;
  /** After DELETE /account: drop whatever sign-in state is left in this browser. */
  afterAccountDeleted: () => Promise<void>;
}

/** The local backend and the mock API: the backend "signs in" and says where to go next. */
export const localAuthActions: AuthActions = {
  google: false,
  startSignIn: async (returnTo) => {
    const { authorizationUrl } = await authApi.startGoogleSignIn(returnTo);
    window.location.assign(authorizationUrl);
  },
  signOut: () => authApi.signOut(),
  afterAccountDeleted: async () => {},
};

/** Holds the sign-in actions; the local ones unless Clerk provides its own. */
export const AuthActionsContext = createContext<AuthActions>(localAuthActions);

/** The sign-in actions for the current sign-in. */
export const useAuthActions = () => useContext(AuthActionsContext);
