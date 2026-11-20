/** The mock agent's rough reading of the user's replies to its questions. */
import type { AgentQuestion } from '@/api/types';

const UNSURE = /\b(maybe|depends|not sure|unsure|idk|possibly|might|perhaps|probably)\b/;
const NO = /\b(no|nope|nah|not|never|can't|cannot|won't|wouldn't|don't)\b/;
const YES =
  /\b(yes|yeah|yep|sure|ok|okay|definitely|absolutely|happy|willing|fine|i can|i would|i'd|i will|of course)\b/;
const AGREE = /^\s*(yes|yeah|yep|correct|right|looks good|sure|ok|okay)\b/i;

/** After this many agent messages it stops asking and offers Yes / No buttons. */
const FOLLOW_UPS_BEFORE_BUTTONS = 2;

/** "Yes", "No", or null when the reply is unsure or doesn't say. */
function readYesNo(text: string): 'Yes' | 'No' | null {
  const words = ` ${text.toLowerCase()} `;
  if (UNSURE.test(words)) return null;
  if (NO.test(words)) return 'No';
  if (YES.test(words)) return 'Yes';
  return null;
}

/** A yes/no reply becomes the answer, or the agent asks again (and later offers buttons). */
function replyToYesNo(question: AgentQuestion, text: string) {
  const value = readYesNo(text);
  if (value) {
    question.proposedAnswer = { value, confidence: 96 };
    return;
  }
  const followUps = question.messages.filter((message) => message.from === 'agent').length;
  const offerButtons = followUps >= FOLLOW_UPS_BEFORE_BUTTONS;
  question.messages.push({
    from: 'agent',
    text: offerButtons
      ? 'I still can’t tell which one you mean. Pick Yes or No below, or reply again.'
      : 'This field only takes Yes or No. Tell me which one fits.',
  });
  if (offerButtons) question.pickOptions = ['Yes', 'No'];
}

/** The reply, as a sentence, goes into the draft's gap. */
function replyToDraft(question: AgentQuestion, draft: { text: string; gap: string }, text: string) {
  const sentence = text
    .trim()
    .replace(/^./, (c) => c.toUpperCase())
    .replace(/([^.!?])$/, '$1.');
  question.proposedAnswer = { value: draft.text.replace(draft.gap, sentence), confidence: 94 };
}

/** Agreeing takes the value the agent suggested in quotes; anything else is the answer itself. */
function replyToConfirm(question: AgentQuestion, text: string) {
  const suggested = question.messages[0]?.text.match(/“(.+?)”/)?.[1];
  question.proposedAnswer =
    AGREE.test(text) && suggested
      ? { value: suggested, confidence: 97 }
      : { value: text.replace(/\.$/, ''), confidence: 95 };
}

/** Records the reply and updates the question, enough to exercise every branch of the UI. */
export function interpretReply(question: AgentQuestion, text: string) {
  question.messages.push({ from: 'you', text });
  if (question.type === 'yesno') replyToYesNo(question, text);
  else if (question.type === 'draft' && question.draft)
    replyToDraft(question, question.draft, text);
  else replyToConfirm(question, text);
}
