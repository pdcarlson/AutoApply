import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { lazy, Suspense, useState, type ReactNode } from 'react';
import { RouterProvider } from 'react-router';
import { clerkEnabled } from '@/auth/config';
import { Loading } from '@/components/ui/DataDisplay';
import { createQueryClient } from './queryClient';
import { OverlayProvider } from './providers/overlays';
import { ThemeProvider } from './providers/theme';
import { ToastProvider } from './providers/toast';
import { router } from './router';

// Clerk's code is only downloaded by builds that sign in with it.
const ClerkAuth = lazy(() => import('@/auth/ClerkAuth'));

/** Sign-in: Clerk when it is configured, otherwise the local backend's own (the default). */
function AuthProvider({ children }: { children: ReactNode }) {
  if (!clerkEnabled) return children;
  return (
    <Suspense fallback={<Loading />}>
      <ClerkAuth>{children}</ClerkAuth>
    </Suspense>
  );
}

/** Everything the app needs around its routes. Tests render pages inside this too. */
export function AppProviders({
  children,
  queryClient,
}: {
  children: ReactNode;
  queryClient?: QueryClient;
}) {
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

export function App() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
