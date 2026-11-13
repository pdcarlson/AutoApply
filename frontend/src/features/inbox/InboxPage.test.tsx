import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { db } from '@/mocks/db';
import { OverlayHost } from '@/layouts/OverlayHost';
import { renderAt } from '@/test/render';
import { InboxPage } from './InboxPage';

/** The Inbox plus the dialogs it can open, as AppShell renders them. */
const inbox = (
  <>
    <InboxPage />
    <OverlayHost />
  </>
);

function signIn({ confirmed = true } = {}) {
  db.signedIn = true;
  db.session.profileConfirmed = confirmed;
}

describe('InboxPage', () => {
  it('lists jobs from the API with their status', async () => {
    signIn();
    renderAt(inbox, '/inbox');

    expect(await screen.findByRole('button', { name: /^Acme Robotics ·/ })).toBeInTheDocument();
    const initechRow = screen.getByRole('button', { name: /^Initech ·/ }).closest('li')!;
    expect(within(initechRow).getByText('Needs you')).toBeInTheDocument();
  });

  it('starts added jobs checked, and applies to the selection', async () => {
    signIn();
    const user = userEvent.setup();
    renderAt(inbox, '/inbox');

    const acme = await screen.findByRole('checkbox', { name: 'Select Acme Robotics' });
    expect(acme).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Select Globex' })).not.toBeChecked();
    // Skip-suggested jobs start unchecked even when the user added them.
    expect(screen.getByRole('checkbox', { name: 'Select Stark Analytics' })).not.toBeChecked();

    await user.click(screen.getByRole('button', { name: 'Apply to 1' }));

    expect(await screen.findByText(/Filling 1 job/)).toBeInTheDocument();
    await waitFor(() => expect(db.jobs.find((j) => j.id === 'job-101')?.state).not.toBe('open'));
  });

  it('applies to one job from its row, even when it isn’t checked', async () => {
    signIn();
    const user = userEvent.setup();
    renderAt(inbox, '/inbox');

    await user.click(await screen.findByRole('button', { name: 'Apply to Globex' }));

    expect(await screen.findByText(/Filling 1 job/)).toBeInTheDocument();
    await waitFor(() =>
      expect(db.jobs.find((j) => j.company === 'Globex')?.state).not.toBe('open'),
    );
    // The checked job is left alone.
    expect(db.jobs.find((j) => j.id === 'job-101')?.state).toBe('open');
  });

  it('asks to confirm the profile before applying', async () => {
    signIn({ confirmed: false });
    const user = userEvent.setup();
    renderAt(inbox, '/inbox');

    await user.click(await screen.findByRole('button', { name: 'Apply to 1' }));

    expect(
      await screen.findByRole('dialog', { name: 'Confirm your profile first' }),
    ).toBeInTheDocument();
    expect(db.jobs.find((j) => j.id === 'job-101')?.state).toBe('open');
  });

  it('filters to jobs that need the user', async () => {
    signIn();
    const user = userEvent.setup();
    renderAt(inbox, '/inbox');
    await screen.findByRole('button', { name: /^Acme Robotics ·/ });

    await user.click(screen.getByRole('button', { name: /Needs you/ }));

    expect(screen.queryByRole('button', { name: /^Acme Robotics ·/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Initech ·/ })).toBeInTheDocument();
  });

  it('rejects unsupported links before calling the API', async () => {
    signIn();
    const user = userEvent.setup();
    renderAt(inbox, '/inbox');

    await user.type(
      await screen.findByLabelText('Add a job by pasting its link'),
      'https://jobs.lever.co/acme/1',
    );
    await user.click(screen.getByRole('button', { name: 'Add job' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('This site isn’t supported');
  });

  it('adds a job from a supported link', async () => {
    signIn();
    const user = userEvent.setup();
    renderAt(inbox, '/inbox');

    await user.type(
      await screen.findByLabelText('Add a job by pasting its link'),
      'https://boards.greenhouse.io/contoso/jobs/42',
    );
    await user.click(screen.getByRole('button', { name: 'Add job' }));

    expect(await screen.findByRole('button', { name: /^Contoso ·/ })).toBeInTheDocument();
  });

  it('answers an options question by picking one, with no reply box', async () => {
    signIn();
    const user = userEvent.setup();
    renderAt(inbox, '/inbox?job=job-103');

    await user.click(await screen.findByRole('button', { name: 'Yes' }));
    expect(screen.queryByLabelText('Your reply')).not.toBeInTheDocument();
    expect(await screen.findByText('I’ll enter')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Use this answer' }));

    expect(await screen.findByText(/Saved to your Answer bank/)).toBeInTheDocument();
    expect(db.answers[0]).toMatchObject({ answer: 'Yes', company: 'Initech' });
  });

  it('sends the code the site emailed, and takes another after a wrong one', async () => {
    signIn();
    const acme = db.jobs.find((j) => j.id === 'job-101')!;
    Object.assign(acme, { state: 'handoff', asksForCode: true });
    const user = userEvent.setup();
    renderAt(inbox, '/inbox?job=job-101');

    const box = await screen.findByLabelText(/Check your email for a message from Greenhouse/);
    await user.type(box, '00000000');
    await user.click(screen.getByRole('button', { name: 'Submit code' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/didn’t take that code/);
    expect(db.jobs).toContain(acme);

    await user.clear(box);
    await user.type(box, 'AB12CD34');
    await user.click(screen.getByRole('button', { name: 'Submit code' }));

    await waitFor(() => expect(db.jobs).not.toContain(acme));
    expect(db.applications[0]).toMatchObject({ jobId: 'job-101', submittedBy: 'agent' });
  });
});
