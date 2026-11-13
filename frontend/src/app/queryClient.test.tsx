import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { queryKeys, useProfile } from '@/api/queries';
import { db } from '@/mocks/db';
import { server } from '@/mocks/node';
import { renderRoutes } from '@/test/render';
import { RequireSession } from './guards';
import { paths } from './paths';

function ProfileName() {
  const profile = useProfile().data;
  return <p>{profile ? `${profile.firstName} ${profile.lastName}` : 'Loading'}</p>;
}

describe('expired session', () => {
  it('sends the user to sign in when a request returns 401', async () => {
    db.signedIn = true;
    const { router, queryClient } = renderRoutes(
      [
        {
          element: <RequireSession />,
          children: [{ path: paths.profile, element: <ProfileName /> }],
        },
        { path: paths.signIn, element: <h1>Sign in</h1> },
      ],
      paths.profile,
    );
    expect(await screen.findByText('Sam Rivera')).toBeInTheDocument();

    server.use(
      http.get('*/api/profile', () =>
        HttpResponse.json({ code: 'unauthenticated', message: 'Sign in' }, { status: 401 }),
      ),
    );
    await queryClient.invalidateQueries({ queryKey: queryKeys.profile });

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(paths.signIn);
  });
});
