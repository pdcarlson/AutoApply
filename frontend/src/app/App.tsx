/** The root component and the providers every screen runs inside. */
import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { lazy, Suspense, useState, type ReactNode } from 'react';
import { RouterProvider } from 'react-router';
import { OverlayProvider } from '@/app/providers/overlays';
import { ThemeProvider } from '@/app/providers/theme';
import { ToastProvider } from '@/app/providers/toast';
import { clerkEnabled } from '@/auth/config';
import { Loading } from '@/components/ui/LoadStates';
import { createQueryClient } from './queryClient';
import { router } from './router';

// Clerk's code is only downloaded by builds that sign in with it.
const ClerkAuth = lazy(() =>
  import('@/auth/ClerkAuth').then((module) => ({ default: module.ClerkAuth })),
);

interface AuthProviderProps {
  children: ReactNode;
}

/** Sign-in: Clerk when it is configured, otherwise the local backend's own (the default). */
function AuthProvider({ children }: AuthProviderProps) {
  if (!clerkEnabled) return children;
  return (
    <Suspense fallback={<Loading />}>
      <ClerkAuth>{children}</ClerkAuth>
    </Suspense>
  );
}

interface AppProvidersProps {
  children: ReactNode;
  /** A client to use instead of a new one, e.g. one a test configured. */
  queryClient?: QueryClient;
}

/** Everything the app needs around its routes. Tests render pages inside this too. */
export function AppProviders({ children, queryClient }: AppProvidersProps) {
  const [client] = useState(() => queryClient ?? createQueryClient());
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <OverlayProvider>{children}</OverlayProvider>
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

/** The whole app: providers around the router. */
export function App() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
