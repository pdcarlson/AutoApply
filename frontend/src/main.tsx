import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { setTokenSource } from './api/authToken';
import { App } from './app/App';
import { clerkEnabled } from './auth/config';
import './styles/global.css';

/** In development, VITE_API_MOCKING=enabled serves /api from the in-browser mock API. */
async function startMockApi() {
  if (!import.meta.env.DEV || import.meta.env.VITE_API_MOCKING !== 'enabled') return;
  const { worker } = await import('./mocks/browser');
  await worker.start({ onUnhandledRequest: 'bypass', quiet: true });
}

/** With Clerk sign-in, every API request carries Clerk's session token. */
async function startAuth() {
  if (!clerkEnabled) return;
  const { getToken } = await import('@clerk/react');
  setTokenSource(() => getToken());
}

void Promise.all([startMockApi(), startAuth()]).then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
