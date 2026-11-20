/** The order the drawer lists an application's filled fields in. */
import type { FilledField } from '@/api/types';

/** Fields the user supplied or the agent drafted, which are worth checking first. */
const isPersonal = (field: FilledField) =>
  field.sourceKind === 'you' || field.sourceKind === 'answer_bank' || field.sourceKind === 'draft';

/** The first three basics, then the personal fields, then the rest. */
export function orderFields(fields: FilledField[]) {
  const [basics, rest] = [fields.slice(0, 3), fields.slice(3)];
  return [...basics, ...rest.filter(isPersonal), ...rest.filter((field) => !isPersonal(field))];
}
