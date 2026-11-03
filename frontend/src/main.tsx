import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import './styles/global.css';

/** In development, VITE_API_MOCKING=enabled serves /api from the in-browser mock API. */
async function startMockApi() {
  if (!import.meta.env.DEV || import.meta.env.VITE_API_MOCKING !== 'enabled') return;
  const { worker } = await import('./mocks/browser');
  await worker.start({ onUnhandledRequest: 'bypass', quiet: true });
}

void startMockApi().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
