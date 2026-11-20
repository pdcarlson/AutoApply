/** Search and category filtering for the Answer bank. */
import { ANSWER_CATEGORIES, type Answer, type AnswerCategory } from '@/api/types';

/** A category filter, or every category. */
export type CategoryFilter = 'All' | AnswerCategory;

/** True if the lowercase `term` appears in the question, answer or another matched wording. */
export const matchesSearch = (answer: Answer, term: string) =>
  !term ||
  [answer.question, answer.answer, ...answer.alsoMatches.map((match) => match.wording)]
    .join(' ')
    .toLowerCase()
    .includes(term);

/** The answers that pass both the category filter and the search. */
export function filterAnswers(answers: Answer[], category: CategoryFilter, search: string) {
  const term = search.trim().toLowerCase();
  return answers.filter(
    (answer) => (category === 'All' || answer.category === category) && matchesSearch(answer, term),
  );
}

/** One filter chip per category, with how many answers each holds. */
export function categoryOptions(answers: Answer[]) {
  const keys: CategoryFilter[] = ['All', ...ANSWER_CATEGORIES];
  return keys.map((key) => ({
    key,
    label: key,
    count:
      key === 'All' ? answers.length : answers.filter((answer) => answer.category === key).length,
  }));
}
