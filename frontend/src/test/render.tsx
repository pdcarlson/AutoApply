/** Helpers that render routes inside the app's providers for tests. */
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router';
import { AppProviders } from '@/app/App';
import { createQueryClient } from '@/app/queryClient';
import { AuthActionsContext, type AuthActions } from '@/auth/actions';
import { db } from '@/mocks/db';

/** Stands in for Clerk: signing in or out flips the mock backend's session. */
const testAuthActions: AuthActions = {
  startSignIn: async () => {
    db.signedIn = true;
  },
  signOut: async () => {
    db.signedIn = false;
  },
  afterAccountDeleted: async () => {},
};

/** Renders routes inside the app's providers, starting at `path`. */
export function renderRoutes(routes: RouteObject[], path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = createQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false, staleTime: 0 } });
  const view = render(
    <AppProviders queryClient={queryClient}>
      <AuthActionsContext.Provider value={testAuthActions}>
        <RouterProvider router={router} />
      </AuthActionsContext.Provider>
    </AppProviders>,
  );
  return { ...view, router, queryClient };
}

/** Renders one element at a path. */
export const renderAt = (element: ReactElement, path = '/') =>
  renderRoutes([{ path: '*', element }], path);
