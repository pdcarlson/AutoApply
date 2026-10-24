import type { MouseEvent, ReactNode } from 'react';

export interface ButtonProps {
  /** Look: 'primary' (ink fill, one per area), 'secondary' (outlined), 'quiet' (text only) or 'danger' (red text, for actions that remove or risk something). Default 'primary'. */
  variant?: 'primary' | 'secondary' | 'quiet' | 'danger';
  /** 'md' for most buttons; 'sm' for table rows and notices (smaller text, same minimum height). Default 'md'. */
  size?: 'md' | 'sm';
  /** Greys the button and blocks clicks. With href, the link is removed and it leaves the tab order. */
  disabled?: boolean;
  /** HTML button type. Ignored when href is set. Default 'button'. */
  type?: 'button' | 'submit' | 'reset';
  /** Called on click. Never called while disabled. */
  onClick?: (event: MouseEvent<HTMLButtonElement | HTMLAnchorElement>) => void;
  /** When set, renders a real <a> link that looks like a button. Use it for going to a page. */
  href?: string;
  /** The label: a short verb phrase in sentence case, such as 'Apply' or 'Open the posting'. */
  children?: ReactNode;
  /** Accessible name when the visible label isn't enough, such as an icon-only button. */
  ariaLabel?: string;
}

export declare function Button(props: ButtonProps): JSX.Element;

import type { ChangeEvent, ReactNode } from 'react';

export interface TextFieldProps {
  /** id for the input. Generated when left out; pass one when another element needs to point at the field. */
  id?: string;
  /** Visible label above the field, written in sentence case (CSS uppercases it). Always give one. */
  label: string;
  /** Help text under the field, such as 'Filled from your profile'. Read by screen readers with the field. */
  hint?: ReactNode;
  /** Error message under the field. When set, the field is marked invalid and gets a danger edge and symbol. */
  error?: ReactNode;
  /** Current text. Pass it with onChange to keep the field controlled. */
  value?: string;
  /** Called on every change with the input or textarea change event; read event.target.value. */
  onChange?: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  /** Example text shown while empty. Never the only instructions: put those in hint. */
  placeholder?: string;
  /** Input type for one-line fields. Ignored when multiline. Default 'text'. */
  type?: 'text' | 'email' | 'url' | 'tel' | 'date' | 'number' | 'search';
  /** Renders a textarea for written answers. Default false. */
  multiline?: boolean;
  /** Visible lines when multiline. Default 4. */
  rows?: number;
  /** Marks the field required: shows 'Required' next to the label and sets the required attribute. */
  required?: boolean;
  /** Which on-screen keyboard phones show, such as 'url', 'email' or 'numeric'. */
  inputMode?: 'text' | 'url' | 'email' | 'tel' | 'numeric' | 'decimal' | 'search' | 'none';
  /** Puts the cursor in this field when it first renders. Use for one field per page at most. */
  autoFocus?: boolean;
  /** Greys the field and blocks typing. */
  disabled?: boolean;
}

export declare function TextField(props: TextFieldProps): JSX.Element;

import type { ReactNode } from 'react';

export interface NoticeProps {
  /** 'info' (plain note), 'needs' (the student is needed), 'error' (something went wrong) or 'success' (done, often with Undo). Default 'info'. */
  tone?: 'info' | 'needs' | 'error' | 'success';
  /** Short first line in bold that says what happened, such as '2 questions waiting'. */
  title?: ReactNode;
  /** The detail: one or two plain sentences with facts, such as which application and what happens next. */
  children?: ReactNode;
  /** One next step, usually a Button with size 'sm'. Sits at the right on a laptop and below the text on a phone. */
  action?: ReactNode;
}

export declare function Notice(props: NoticeProps): JSX.Element;

import type { ReactNode } from 'react';

export interface BetaLabelProps {
  /** The label text in sentence case, naming the feature when it helps, such as 'Filters and CSV export coming in beta'. Default 'Coming in beta'. */
  children?: ReactNode;
}

export declare function BetaLabel(props: BetaLabelProps): JSX.Element;

/** The nine application statuses. Every screen uses the same word for each. */
export type StatusPillStatus =
  | 'queued'
  | 'filling'
  | 'needs-you'
  | 'submitted'
  | 'submitted-by-you'
  | 'skipped'
  | 'stopped'
  | 'failed'
  | 'check-before-retrying';

export interface StatusPillProps {
  /** Which of the nine statuses to show; the pill picks the word, symbol and shape. */
  status: StatusPillStatus;
  /** 'md' (default) for Applications rows and the application page; 'sm' for the sidebar agent line and tight spots. */
  size?: 'md' | 'sm';
}

/** The word for each status, e.g. STATUSES['needs-you'].label === 'Needs you'. */
export declare const STATUSES: Record<StatusPillStatus, { label: string }>;

export declare function StatusPill(props: StatusPillProps): JSX.Element;

/** What happened to the last pasted link, shown under the box. */
export interface PasteBoxMessage {
  /** 'info' for added, 'needs' for already in your list, 'error' for a link AutoApply can't use. */
  tone: 'info' | 'needs' | 'error';
  /** The sentence, e.g. "Added Platform Intern at Harbor Freight. 3rd in line." */
  text: string;
  /** Optional link to the application's page, e.g. "/applications/42". */
  href?: string;
  /** Words for that link. Defaults to "Open it". */
  linkText?: string;
}

export interface PasteBoxProps {
  /** Called with the trimmed link on Apply or Enter; the box has already cleared and kept focus. */
  onApply: (url: string) => void;
  /** Message for the last link, read out politely by screen readers; null shows nothing. */
  message?: PasteBoxMessage | null;
  /** Turns off the input and Apply, for example while the agent can't take new links. */
  disabled?: boolean;
  /** Puts the cursor in the box on first render. Set it when Setup finishes and opens Applications. Default false. */
  autoFocus?: boolean;
}

export declare function PasteBox(props: PasteBoxProps): JSX.Element;

/** One page link in the sidebar. */
export interface SidebarItem {
  /** Link text in sentence case: "Needs you", "Applications", "Answer bank", "Profile", "Settings". */
  label: string;
  /** Address of the page, such as "/needs-you". */
  href: string;
  /** Number waiting on the student; the badge shows only when it is above 0 (use it on Needs you only). */
  count?: number;
  /** True for the page being shown; adds aria-current="page", a heavier weight and an ink bar. */
  current?: boolean;
}

/** The one read-only line about what the agent is doing. */
export interface SidebarAgentLine {
  /** What the agent is doing, in status words: "Filling Harbor Freight · page 2 of 3 · 3 in line". */
  text: string;
  /** Address of that application's page, such as "/applications/412". */
  href: string;
}

/** The signed-in student. */
export interface SidebarUser {
  /** Full name: "Joe Miller". */
  name: string;
  /** Email: "joe.miller@rpi.edu". */
  email: string;
}

export interface SidebarProps {
  /** The page links in order: Needs you, Applications, Answer bank, Profile, Settings. */
  items: SidebarItem[];
  /** What the agent is doing now, or null to show "Nothing in line" as muted text. */
  agentLine: SidebarAgentLine | null;
  /** Name and email shown above Sign out. */
  user: SidebarUser;
  /** Called when the student clicks Sign out. */
  onSignOut: () => void;
  /** The app name, shown as plain type with no logo. Defaults to "AutoApply". */
  appName?: string;
  /** Leave as "auto" (column on a laptop, top bar below 768px); "laptop" or "phone" force one layout for previews and tests. */
  layout?: 'auto' | 'laptop' | 'phone';
}

export declare function Sidebar(props: SidebarProps): JSX.Element;

export interface StepBarProps {
  /** Step names in order, sentence case. Defaults to ["Resume", "Profile", "Questions"]. */
  steps?: string[];
  /** The step being shown, 0-based. Steps before it show as done, steps after it as not started. */
  current: number;
  /** The signed-in student; only the email is shown. */
  user: { email: string };
  /** Called when the student clicks Sign out. */
  onSignOut: () => void;
}

export declare function StepBar(props: StepBarProps): JSX.Element;

export interface QuestionCardProps {
  // The question exactly as the application form words it, e.g. "Are you willing to relocate to Austin, TX?"
  question: string;
  // Optional custom why-line text. Leave it out to use the words for whyKind.
  why?: string;
  // Why the agent asked: "no-saved-answer" (No saved answer), "not-sure" (Less than 90% sure), "unsure-field" (Unsure field from your resume), "written" (Written answer). Default "no-saved-answer".
  whyKind?: 'no-saved-answer' | 'not-sure' | 'unsure-field' | 'written';
  // The applications waiting on this question; each name links to that application's page.
  askedBy?: Array<{ name: string; href?: string }>;
  // The answer control: "choice" (radio group), "text" (one line), "date" (date field), "written" (multi-line). Default "text".
  kind?: 'choice' | 'text' | 'date' | 'written';
  // The answer choices for kind "choice", in the form's order and wording.
  options?: string[];
  // The current answer. Pass it with onChange to control the card; leave it out and the card keeps its own value. A date is "YYYY-MM-DD".
  value?: string | null;
  // Called with the new answer string (not the event) whenever it changes.
  onChange?: (value: string) => void;
  // Called when the student presses Save. Receives the current answer. The button stays disabled until there is one.
  onSave?: (value: string) => void;
  // Text of the save button. Default "Save answer" ("Check in Profile" when profileHref is used).
  saveLabel?: string;
  // Line right above the button saying what saving does, e.g. "Saving sends this in 2 applications and saves it to your Answer bank".
  note?: string;
  // Text for a Coming in beta label under the answer, e.g. "AI drafts coming in beta".
  betaNote?: string;
  // Disables the answer control and the button, e.g. while the save is in flight.
  disabled?: boolean;
  // For whyKind "unsure-field" only: link to that field on Profile. The card then shows the read value and links there instead of showing a field.
  profileHref?: string;
}

export declare function QuestionCard(props: QuestionCardProps): JSX.Element;

// The why-line words for each whyKind.
export declare const QUESTION_WHY: Record<'no-saved-answer' | 'not-sure' | 'unsure-field' | 'written', string>;

export interface ApplicationListProps {
  /** Every application, newest first. Each row: id, company, role, site ("Greenhouse", "Lever", "Ashby"), status (one of the nine StatusPill statuses), statusLine (one read-only line, e.g. "Page 2 of 3 · filled Graduation date"), sentDate (e.g. "Oct 23", omit until sent), href (the application's page), proofHref (omit until there is proof). */
  applications: Array<{ id: string; company: string; role: string; site: string; status: 'queued' | 'filling' | 'needs-you' | 'submitted' | 'submitted-by-you' | 'skipped' | 'stopped' | 'failed' | 'check-before-retrying'; statusLine?: string; sentDate?: string; href: string; proofHref?: string }>;
  /** Text shown instead of the table when there are no applications. Defaults to "Paste a job link above to start." */
  emptyText?: string;
  /** Visually hidden table caption for screen readers. Defaults to "Applications". */
  caption?: string;
}

export declare function ApplicationList(props: ApplicationListProps): JSX.Element;

export interface ProofListProps {
  /** The confirmation screenshot: src (image URL; omit to show a gray placeholder), alt (what the page says, e.g. "Northwind Data confirmation page: Thanks for applying, Joe"), time (e.g. "Oct 23, 2:14 pm"). Pass null when there is none. */
  confirmation: { src?: string; alt: string; time?: string } | null;
  /** Why there is no screenshot, shown in an info Notice when confirmation is null, e.g. "You sent this one yourself, so there's no confirmation screenshot." */
  noProofReason?: string;
  /** Everything that was sent, in form order: label (the field), value (exactly what was sent), source.text ("Profile: Graduation date", "Answer bank: Will you relocate?", "Written by you") and source.href (that thing's one home; omit for plain text). */
  fields: Array<{ label: string; value: string; source?: { text: string; href?: string } }>;
  /** The resume that was attached: file name and a link to open it. */
  resume?: { name: string; href?: string } | null;
  /** Heading level for the "Proof" heading; "What was sent" uses the next level down. Defaults to 2. */
  headingLevel?: 2 | 3 | 4 | 5;
}

export declare function ProofList(props: ProofListProps): JSX.Element;

/** The screenshot saved for one step. */
export interface StepLogScreenshot {
  /** Image URL. An empty string shows a gray placeholder box instead. */
  src: string;
  /** What the screenshot shows, e.g. "Kestrel Health form, Education section". */
  alt: string;
}

/** One line of the receipt. */
export interface StepLogStep {
  /** Stable id for the step, used as the React key. */
  id: string | number;
  /** When it happened: "HH:MM:SS" (24-hour) as given, or a Date / ms number / ISO string, shown as HH:MM:SS. */
  time: string | number | Date;
  /** What the agent did, as a plain past-tense fact: "Filled Graduation date", "Clicked Submit". */
  text: string;
  /** Where the value came from: "Profile", "Answer bank" or "You". The arrow is added for you. null when nothing was sent. */
  source: string | null;
  /** The screenshot for this step, or null if it isn't saved yet. */
  screenshot: StepLogScreenshot | null;
}

export interface StepLogProps {
  /** Every step so far, oldest first. While live, the log shows them newest first on its own. */
  steps: StepLogStep[];
  /** True while the application is Filling: newest step on top with a large 16:10 screenshot and a Live marker. Default false. */
  live?: boolean;
  /** Called with the step when someone opens its screenshot. Leave it out and screenshots show without being buttons. */
  onOpenScreenshot?: (step: StepLogStep) => void;
}

export declare function StepLog(props: StepLogProps): JSX.Element;
