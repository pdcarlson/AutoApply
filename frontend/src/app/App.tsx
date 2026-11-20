/** The root component and the providers every screen runs inside. */
import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import { RouterProvider } from 'react-router';
import { OverlayProvider } from '@/app/providers/overlays';
import { ThemeProvider } from '@/app/providers/theme';
import { ToastProvider } from '@/app/providers/toast';
import { ClerkAuth } from '@/auth/ClerkAuth';
import { createQueryClient } from './queryClient';
import { router } from './router';

interface AppProvidersProps {
  children: ReactNode;
  /** A client to use instead of a new one, e.g. one a test configured. */
  queryClient?: QueryClient;
}

/** Everything around the routes except sign-in. Tests render pages inside this too. */
export function AppProviders({ children, queryClient }: AppProvidersProps) {
  const [client] = useState(() => queryClient ?? createQueryClient());
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <ToastProvider>
          <OverlayProvider>{children}</OverlayProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

/** The whole app: providers and Clerk sign-in around the router. */
export function App() {
  return (
    <AppProviders>
      <ClerkAuth>
        <RouterProvider router={router} />
      </ClerkAuth>
    </AppProviders>
  );
}
