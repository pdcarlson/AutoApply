import React from 'react';
import { Button } from './Button.js';
import { TextField } from './TextField.js';
import { BetaLabel } from './BetaLabel.js';

// The words for each reason a question is waiting. The dot before them is decoration;
// the words carry the meaning.
export const QUESTION_WHY = {
  'no-saved-answer': 'No saved answer',
  'not-sure': 'Less than 90% sure',
  'unsure-field': 'Unsure field from your resume',
  'written': 'Written answer'
};

// One question the agent is waiting on, as a card on the Needs you page.
export function QuestionCard(props) {
  const h = React.createElement;
  const {
    question,
    why,
    whyKind = 'no-saved-answer',
    askedBy = [],
    kind = 'text',
    options = [],
    value,
    onChange,
    onSave,
    saveLabel,
    note,
    betaNote,
    disabled = false,
    profileHref
  } = props;

  const uid = React.useId();
  const questionId = uid + '-question';
  const fieldId = uid + '-answer';
  const groupName = uid + '-choice';

  // Works controlled (pass value and onChange) or on its own (leave value out).
  const [ownValue, setOwnValue] = React.useState('');
  const isControlled = value !== undefined;
  const current = isControlled ? (value == null ? '' : String(value)) : ownValue;
  const hasValue = current.trim() !== '';

  function setValue(next) {
    if (!isControlled) setOwnValue(next);
    if (onChange) onChange(next);
  }

  function handleSave() {
    if (disabled || !hasValue) return;
    if (onSave) onSave(current);
  }

  const whyText = why || QUESTION_WHY[whyKind] || '';
  const opensProfile = whyKind === 'unsure-field' && Boolean(profileHref);
  const buttonLabel = saveLabel || (opensProfile ? 'Check in Profile' : 'Save answer');

  // "Asked by Northwind Data, Kestrel Health and Brightline Robotics", each name a link.
  const apps = Array.isArray(askedBy) ? askedBy.filter(function (app) { return app && app.name; }) : [];
  const askedParts = [];
  apps.forEach(function (app, i) {
    if (i > 0) askedParts.push(i === apps.length - 1 ? ' and ' : ', ');
    askedParts.push(
      app.href
        ? h('a', { key: 'app-' + i, href: app.href, className: 'aa-question-card__app-link' }, app.name)
        : h('span', { key: 'app-' + i, className: 'aa-question-card__app-name' }, app.name)
    );
  });

  let answer = null;
  if (opensProfile) {
    // A profile field has one home: Profile. The card shows what was read and links there.
    answer = current
      ? h('p', { className: 'aa-question-card__read aa-small' },
          'Read from your resume: ',
          h('span', { className: 'aa-question-card__read-value aa-mono' }, current))
      : null;
  } else if (kind === 'choice') {
    answer = h('fieldset', { className: 'aa-question-card__fieldset', disabled: disabled },
      h('legend', { className: 'aa-question-card__legend aa-label' },
        'Your answer',
        h('span', { className: 'aa-question-card__sr-only' }, ': ' + (question || ''))),
      h('div', { className: 'aa-question-card__options' },
        options.map(function (opt) {
          const checked = current === opt;
          let cls = 'aa-question-card__option';
          if (checked) cls += ' aa-question-card__option--checked';
          if (disabled) cls += ' aa-question-card__option--disabled';
          return h('label', { key: opt, className: cls },
            h('input', {
              type: 'radio',
              className: 'aa-question-card__radio',
              name: groupName,
              value: opt,
              checked: checked,
              disabled: disabled,
              onChange: function () { setValue(opt); }
            }),
            h('span', { className: 'aa-question-card__option-text aa-body' }, opt));
        })));
  } else {
    const fieldKind = kind === 'date' || kind === 'written' ? kind : 'text';
    answer = h('div', {
      role: 'group',
      'aria-labelledby': questionId,
      className: 'aa-question-card__answer aa-question-card__answer--' + fieldKind
    },
      h(TextField, {
        id: fieldId,
        label: 'Your answer',
        value: current,
        onChange: function (e) { setValue(e.target.value); },
        type: fieldKind === 'date' ? 'date' : 'text',
        multiline: fieldKind === 'written',
        rows: fieldKind === 'written' ? 5 : undefined,
        disabled: disabled
      }));
  }

  let cardClass = 'aa-question-card';
  if (disabled) cardClass += ' aa-question-card--disabled';

  return h('article', { className: cardClass, 'aria-labelledby': questionId },
    h('h3', { id: questionId, className: 'aa-question-card__question aa-body-strong' }, question),
    whyText
      ? h('p', { className: 'aa-question-card__why aa-small' },
          h('span', { className: 'aa-question-card__dot', 'aria-hidden': 'true' }),
          h('span', null, whyText))
      : null,
    askedParts.length
      ? h('p', { className: 'aa-question-card__asked aa-small' }, 'Asked by ', askedParts)
      : null,
    answer,
    betaNote
      ? h('div', { className: 'aa-question-card__beta' }, h(BetaLabel, null, betaNote))
      : null,
    note ? h('p', { className: 'aa-question-card__note aa-small' }, note) : null,
    h('div', { className: 'aa-question-card__actions' },
      opensProfile
        ? h(Button, { variant: 'primary', href: profileHref }, buttonLabel)
        : h(Button, {
            variant: 'primary',
            disabled: disabled || !hasValue,
            onClick: handleSave
          }, buttonLabel)));
}
