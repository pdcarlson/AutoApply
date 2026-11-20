import { AuthenticateWithRedirectCallback } from '@clerk/react';
import { paths } from '@/app/paths';
import { Loading } from '@/components/ui/DataDisplay';

/**
 * Where Google sends the browser back. Clerk finishes the sign-in here (creating the account
 * on a first visit) and then goes on to `/auth/callback`.
 */
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
