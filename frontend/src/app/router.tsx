import { createBrowserRouter, Navigate } from 'react-router';
import { AppShell } from '@/layouts/AppShell';
import { SetupLayout } from '@/layouts/SetupLayout';
import { AccountDeletedPage } from '@/features/auth/AccountDeletedPage';
import { AuthCallbackPage } from '@/features/auth/AuthCallbackPage';
import { SignInPage } from '@/features/auth/SignInPage';
import { ApplicationsPage } from '@/features/applications/ApplicationsPage';
import { AnswerBankPage } from '@/features/answers/AnswerBankPage';
import { InboxPage } from '@/features/inbox/InboxPage';
import { ProfilePage } from '@/features/profile/ProfilePage';
import { SettingsPage } from '@/features/settings/SettingsPage';
import { CommonQuestionsPage } from '@/features/setup/CommonQuestionsPage';
import { ProfileReviewPage } from '@/features/setup/ProfileReviewPage';
import { ResumeUploadPage } from '@/features/setup/ResumeUploadPage';
import { RedirectIfSignedIn, RequireSession } from './guards';
import { paths } from './paths';

export const router = createBrowserRouter([
  {
    element: <RedirectIfSignedIn />,
    children: [{ path: paths.signIn, element: <SignInPage /> }],
  },
  { path: paths.authCallback, element: <AuthCallbackPage /> },
  { path: paths.accountDeleted, element: <AccountDeletedPage /> },
  {
    element: <RequireSession />,
    children: [
      {
        element: <SetupLayout />,
        children: [
          { path: paths.setupResume, element: <ResumeUploadPage /> },
          { path: paths.setupProfile, element: <ProfileReviewPage /> },
          { path: paths.setupQuestions, element: <CommonQuestionsPage /> },
        ],
      },
      {
        element: <AppShell />,
        children: [
          { index: true, element: <Navigate to={paths.inbox} replace /> },
          { path: paths.inbox, element: <InboxPage /> },
          { path: paths.applications, element: <ApplicationsPage /> },
          { path: paths.answers, element: <AnswerBankPage /> },
          { path: paths.profile, element: <ProfilePage /> },
          { path: paths.settings, element: <SettingsPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);
