import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { AgentQuestion, Job } from '@/api/types';
import { db } from '@/mocks/db';
import { renderAt } from '@/test/render';
import { QuestionPanel } from './QuestionPanel';

const job = { id: 'job-103', company: 'Initech' } as Job;

const question = (extra: Partial<AgentQuestion>): AgentQuestion => ({
  id: 'q-test',
  type: 'confirm',
  field: 'A question the form asks',
  confidence: 0,
  draft: null,
  messages: [{ from: 'agent', text: 'Nothing in your profile answers this.' }],
  placeholder: 'e.g. the right answer',
  pickOptions: null,
  proposedAnswer: null,
  defaultScope: 'all',
  ...extra,
});

describe('QuestionPanel', () => {
  it('shows a reply box for a free-text field', async () => {
    db.signedIn = true;
    renderAt(<QuestionPanel job={job} question={question({ field: 'City?' })} />);

    expect(await screen.findByLabelText('Your reply')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument();
  });

  it('shows only the option buttons for a field with a few options', async () => {
    db.signedIn = true;
    renderAt(
      <QuestionPanel job={job} question={question({ pickOptions: ['She', 'He', 'They'] })} />,
    );

    for (const option of ['She', 'He', 'They']) {
      expect(await screen.findByRole('button', { name: option })).toBeInTheDocument();
    }
    expect(screen.queryByLabelText('Your reply')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Filter options')).not.toBeInTheDocument();
  });

  it('filters a long option list instead of offering a reply box', async () => {
    db.signedIn = true;
    const user = userEvent.setup();
    const disciplines = [
      ...Array.from({ length: 40 }, (_, i) => `Discipline ${i + 1}`),
      'Computer Science',
      'Computer Engineering',
    ];
    renderAt(<QuestionPanel job={job} question={question({ pickOptions: disciplines })} />);

    expect(screen.queryByLabelText('Your reply')).not.toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(12);
    expect(screen.getByText(/30 more options match/)).toBeInTheDocument();

    await user.type(screen.getByLabelText('Filter options'), 'computer');

    expect(screen.getByRole('button', { name: 'Computer Science' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Computer Engineering' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Discipline 1' })).not.toBeInTheDocument();
  });
});
