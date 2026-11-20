/** The DOM id of a job's reply box, which other panels use to name related inputs. */

/** Returns `reply-<jobId>`. */
export const replyInputId = (jobId: string) => `reply-${jobId}`;
