import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { db } from '@/mocks/db';
import { OverlayHost } from '@/layouts/OverlayHost';
import { renderAt } from '@/test/render';
import { JobBoardPage } from './JobBoardPage';

/** The job board plus the dialogs it can open, as AppShell renders them. */
const board = (
  <>
    <JobBoardPage />
    <OverlayHost />
  </>
);

function signIn({ confirmed = true } = {}) {
  db.signedIn = true;
  db.session.profileConfirmed = confirmed;
}

describe('JobBoardPage', () => {
  it('lists postings from both sites, best fit first, with why they fit', async () => {
    signIn();
    renderAt(board, '/jobs');

    expect(await screen.findByText(/Northwind Data · Software Engineer Intern/)).toBeVisible();
    const rows = screen.getAllByRole('listitem');
    expect(rows.map((row) => within(row).getAllByText(/^\d+$/)[0].textContent)).toEqual([
      '92',
      '74',
      '26',
      '9',
    ]);
    expect(within(rows[0]).getByText(/Asks for Python, SQL · Internship/)).toBeVisible();
    expect(within(rows[0]).getByText(/Greenhouse/)).toBeVisible();
    expect(within(rows[1]).getByText(/Ashby/)).toBeVisible();
  });

  it('filters by kind of job and by search', async () => {
    signIn();
    const user = userEvent.setup();
    renderAt(board, '/jobs');
    await screen.findByText(/Northwind Data/);

    await user.click(screen.getByRole('button', { name: /Internships/ }));
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    expect(screen.queryByText(/Brightline Robotics/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^All/ }));
    await user.type(screen.getByRole('searchbox'), 'austin');
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    expect(screen.getByText(/Harbor Freight Analytics/)).toBeVisible();
  });

  it('starts an application from a posting and then shows it as in the Inbox', async () => {
    signIn();
    const user = userEvent.setup();
    renderAt(board, '/jobs');

    await user.click(
      await screen.findByRole('button', {
        name: 'Apply to Northwind Data, Software Engineer Intern',
      }),
    );

    expect(await screen.findByText(/Filling 1 job/)).toBeInTheDocument();
    const job = db.jobs.find((j) => j.company === 'Northwind Data')!;
    expect(job.source).toBe('matched');
    expect(job.state).not.toBe('open');
    const inInbox = await screen.findByRole('link', { name: 'In your Inbox' });
    expect(inInbox.closest('li')).toHaveTextContent(/Northwind Data/);
  });

  it('applies to every checked posting at once, like the Inbox', async () => {
    signIn();
    const user = userEvent.setup();
    renderAt(board, '/jobs');

    await user.click(
      await screen.findByRole('checkbox', {
        name: 'Select Northwind Data, Software Engineer Intern',
      }),
    );
    await user.click(
      screen.getByRole('checkbox', { name: 'Select Brightline Robotics, Frontend Engineer' }),
    );
    expect(screen.getByText('2 selected')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Apply to 2' }));

    expect(await screen.findByText(/Filling 2 jobs/)).toBeInTheDocument();
    expect(await screen.findAllByRole('link', { name: 'In your Inbox' })).toHaveLength(2);
    expect(screen.getByText('0 selected')).toBeVisible();
    const queued = db.jobs.filter((j) => j.source === 'matched' && j.state !== 'open');
    expect(queued.map((j) => j.company)).toEqual(['Northwind Data', 'Brightline Robotics']);
  });

  it('asks for the profile to be confirmed before applying', async () => {
    signIn({ confirmed: false });
    const user = userEvent.setup();
    renderAt(board, '/jobs');

    await user.click(
      await screen.findByRole('button', {
        name: 'Apply to Brightline Robotics, Frontend Engineer',
      }),
    );

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(db.jobs.some((j) => j.company === 'Brightline Robotics')).toBe(false);
  });
});
