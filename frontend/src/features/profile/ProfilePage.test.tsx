import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { paths } from '@/app/paths';
import { db } from '@/mocks/db';
import { renderAt } from '@/test/render';
import { ProfilePage } from './ProfilePage';

describe('Profile page name fields', () => {
  it('edits first, middle, and last name separately and requires first and last', async () => {
    db.signedIn = true;
    const user = userEvent.setup();
    renderAt(<ProfilePage />, paths.profile);

    const contact = within(await screen.findByRole('region', { name: 'Contact' }));
    const first = contact.getByLabelText('First name');
    const middle = contact.getByLabelText('Middle name (optional)');
    expect(first).toHaveValue('Sam');
    expect(contact.getByLabelText('Last name')).toHaveValue('Rivera');

    await user.clear(first);
    expect(contact.getByRole('button', { name: 'Save changes' })).toBeDisabled();
    expect(contact.getByText('Add your first name to save')).toBeInTheDocument();

    await user.type(first, 'Samantha');
    await user.type(middle, 'Ann');
    await user.click(contact.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Saved. The next application uses these.')).toBeInTheDocument();
    expect([db.profile.firstName, db.profile.middleName, db.profile.lastName]).toEqual([
      'Samantha',
      'Ann',
      'Rivera',
    ]);
  });
});
