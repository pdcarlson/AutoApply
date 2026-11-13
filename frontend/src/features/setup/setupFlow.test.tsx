import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { paths } from '@/app/paths';
import { SetupLayout } from '@/layouts/SetupLayout';
import { db } from '@/mocks/db';
import { renderRoutes } from '@/test/render';
import { CommonQuestionsPage } from './CommonQuestionsPage';
import { ProfileReviewPage } from './ProfileReviewPage';
import { ResumeUploadPage } from './ResumeUploadPage';

const routes = [
  {
    element: <SetupLayout />,
    children: [
      { path: paths.setupResume, element: <ResumeUploadPage /> },
      { path: paths.setupProfile, element: <ProfileReviewPage /> },
      { path: paths.setupQuestions, element: <CommonQuestionsPage /> },
    ],
  },
  { path: paths.inbox, element: <h1>Inbox page</h1> },
];

describe('setup flow', () => {
  it('uploads a resume, reviews the profile, answers questions, and confirms', async () => {
    db.signedIn = true;
    const user = userEvent.setup();
    const { router } = renderRoutes(routes, paths.setupResume);

    await user.upload(
      await screen.findByLabelText('Choose a file'),
      new File(['%PDF'], 'My_Resume.pdf', { type: 'application/pdf' }),
    );
    expect(
      await screen.findByText('Read My_Resume.pdf', {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Check what we pulled/ }));

    expect(
      await screen.findByRole('heading', { name: 'Check what we pulled from your resume' }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('First name')).toHaveValue('Sam');
    expect(screen.getByLabelText('Middle name (optional)')).toHaveValue('');
    const lastName = screen.getByLabelText('Last name');
    expect(lastName).toHaveValue('Rivera');
    await user.clear(lastName);
    expect(screen.getByRole('button', { name: /Looks right, continue/ })).toBeDisabled();
    expect(screen.getByText('Add your last name to continue')).toBeInTheDocument();
    await user.type(lastName, 'Rivera-Cruz');
    await user.type(screen.getByLabelText('Middle name (optional)'), 'Lee');
    const phone = screen.getByLabelText('Phone');
    expect(phone).toHaveValue('(555) 010-2233');
    await user.clear(phone);
    await user.type(phone, '(555) 000-1111');
    await user.click(screen.getByRole('button', { name: /Looks right, continue/ }));

    expect(await screen.findByRole('heading', { name: 'Answer these once' })).toBeInTheDocument();
    expect(db.profile.phone).toBe('(555) 000-1111');
    expect([db.profile.firstName, db.profile.middleName, db.profile.lastName]).toEqual([
      'Sam',
      'Lee',
      'Rivera-Cruz',
    ]);
    const authorized = screen.getByRole('radiogroup', { name: /legally authorized/ });
    await user.click(within(authorized).getByRole('radio', { name: 'Yes' }));

    // Each self-ID question takes an answer or "I don't wish to answer"
    const gender = screen.getByRole('radiogroup', { name: 'Gender' });
    await user.click(within(gender).getByRole('radio', { name: 'I don’t wish to answer' }));
    expect(screen.queryByLabelText('Please identify your race')).not.toBeInTheDocument();
    const hispanic = screen.getByRole('radiogroup', { name: /Hispanic or Latino/ });
    await user.click(within(hispanic).getByRole('radio', { name: 'No' }));
    await user.selectOptions(screen.getByLabelText('Please identify your race'), 'Asian');
    const veteran = screen.getByRole('radiogroup', { name: /^Veteran status/ });
    await user.click(within(veteran).getByRole('radio', { name: 'I am not a protected veteran' }));
    const disability = screen.getByRole('radiogroup', { name: 'Disability status' });
    await user.click(within(disability).getByRole('radio', { name: 'I don’t wish to answer' }));

    await user.click(screen.getByRole('button', { name: /Confirm profile and finish/ }));

    expect(await screen.findByRole('heading', { name: 'Inbox page' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(paths.inbox);
    expect(db.session.profileConfirmed).toBe(true);
    expect(db.commonAnswers.workAuthorized).toBe('Yes');
    expect(db.commonAnswers).toMatchObject({
      gender: 'decline',
      hispanicLatino: 'No',
      race: 'Asian',
      veteran: 'No',
      disability: 'decline',
    });
    // Resume parsing is polled once a second, so this walk-through takes a few seconds.
  }, 15_000);

  it('only asks race after "No" to Hispanic or Latino, and clears it otherwise', async () => {
    db.signedIn = true;
    const user = userEvent.setup();
    renderRoutes(routes, paths.setupQuestions);

    const hispanic = await screen.findByRole('radiogroup', { name: /Hispanic or Latino/ });
    await user.click(within(hispanic).getByRole('radio', { name: 'No' }));
    await user.selectOptions(screen.getByLabelText('Please identify your race'), 'White');
    await user.click(within(hispanic).getByRole('radio', { name: 'Yes' }));
    expect(screen.queryByLabelText('Please identify your race')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Confirm profile and finish/ }));

    await screen.findByRole('heading', { name: 'Inbox page' });
    expect(db.commonAnswers).toMatchObject({ hispanicLatino: 'Yes', race: null });
  });

  it('rejects a file that is not a PDF or DOCX', async () => {
    db.signedIn = true;
    const user = userEvent.setup({ applyAccept: false });
    renderRoutes(routes, paths.setupResume);

    await user.upload(await screen.findByLabelText('Choose a file'), new File(['x'], 'photo.png'));

    expect(await screen.findByRole('alert')).toHaveTextContent('photo.png is a .png file');
  });
});
