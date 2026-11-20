/** The page Google returns to when signing in through Clerk. */
import { AuthenticateWithRedirectCallback } from '@clerk/react';
import { paths } from '@/app/paths';
import { Loading } from '@/components/ui/LoadStates';

/** Where Google sends the browser back; Clerk finishes signing in, then goes to the callback. */
export function SsoCallbackPage() {
  return (
    <>
      <Loading label="Signing you in…" />
      <AuthenticateWithRedirectCallback
        signInFallbackRedirectUrl={paths.authCallback}
        signUpFallbackRedirectUrl={paths.authCallback}
      />
    </>
  );
}
