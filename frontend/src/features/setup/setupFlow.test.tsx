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
    const phone = screen.getByLabelText('Phone');
    expect(phone).toHaveValue('(555) 010-2233');
    await user.clear(phone);
    await user.type(phone, '(555) 000-1111');
    await user.click(screen.getByRole('button', { name: /Looks right, continue/ }));

    expect(await screen.findByRole('heading', { name: 'Answer these once' })).toBeInTheDocument();
    expect(db.profile.phone).toBe('(555) 000-1111');
    const authorized = screen.getByRole('radiogroup', { name: /legally authorized/ });
    await user.click(within(authorized).getByRole('radio', { name: 'Yes' }));
    await user.click(screen.getByRole('button', { name: /Confirm profile and finish/ }));

    expect(await screen.findByRole('heading', { name: 'Inbox page' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(paths.inbox);
    expect(db.session.profileConfirmed).toBe(true);
    expect(db.commonAnswers.workAuthorized).toBe('Yes');
    // Resume parsing is polled once a second, so this walk-through takes a few seconds.
  }, 15_000);

  it('rejects a file that is not a PDF or DOCX', async () => {
    db.signedIn = true;
    const user = userEvent.setup({ applyAccept: false });
    renderRoutes(routes, paths.setupResume);

    await user.upload(await screen.findByLabelText('Choose a file'), new File(['x'], 'photo.png'));

    expect(await screen.findByRole('alert')).toHaveTextContent('photo.png is a .png file');
  });
});
