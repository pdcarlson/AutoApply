import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect } from 'react';
import { describe, expect, it } from 'vitest';
import { paths } from '@/app/paths';
import { useOverlays } from '@/app/providers/overlays';
import { OverlayHost } from '@/layouts/OverlayHost';
import { db } from '@/mocks/db';
import { renderRoutes } from '@/test/render';

function OpenDeleteModal() {
  const { open } = useOverlays();
  useEffect(() => open({ type: 'deleteAccount' }), [open]);
  return <OverlayHost />;
}

describe('DeleteAccountModal', () => {
  it('only deletes after DELETE is typed', async () => {
    db.signedIn = true;
    const user = userEvent.setup();
    const { router } = renderRoutes(
      [
        { path: paths.settings, element: <OpenDeleteModal /> },
        { path: paths.accountDeleted, element: <h1>Deleted</h1> },
      ],
      paths.settings,
    );

    const button = await screen.findByRole('button', { name: 'Delete everything' });
    expect(button).toBeDisabled();
    expect(await screen.findByText(/7 saved answers/)).toBeInTheDocument();

    await user.type(screen.getByLabelText('Type DELETE to confirm'), 'delete');
    await user.click(button);

    expect(await screen.findByRole('heading', { name: 'Deleted' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(paths.accountDeleted);
    expect(db.signedIn).toBe(false);
  });
});
