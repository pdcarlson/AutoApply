/** The browser entry point: connects API requests to Clerk's token, then starts the app. */
import { getToken } from '@clerk/react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { setTokenSource } from '@/api/authToken';
import { App } from '@/app/App';
import { clerkKey } from '@/auth/config';
import '@/styles/global.css';

const root = createRoot(document.getElementById('root')!);

if (!clerkKey) {
  root.render(<p>VITE_CLERK_PUBLISHABLE_KEY is not set, so the app can’t sign anyone in.</p>);
} else {
  setTokenSource(() => getToken());
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
