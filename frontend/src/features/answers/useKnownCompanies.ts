/** The companies an answer can be limited to. */
import { useApplications, useJobs } from '@/api/queries';

/** Companies the user has applied to or has in their Inbox, sorted by name. */
export function useKnownCompanies() {
  const applications = useApplications().data ?? [];
  const jobs = useJobs().data ?? [];
  const names = [...applications, ...jobs].map((item) => item.company);
  return [...new Set(names)].sort();
}
