import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import { RouterProvider } from 'react-router';
import { createQueryClient } from './queryClient';
import { OverlayProvider } from './providers/overlays';
import { ThemeProvider } from './providers/theme';
import { ToastProvider } from './providers/toast';
import { router } from './router';

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
          <OverlayProvider>{children}</OverlayProvider>
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
