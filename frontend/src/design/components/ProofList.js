import React from 'react';
import { Notice } from './Notice.js';

// The Proof section of an application's page, styled like a receipt:
// the confirmation screenshot (or the reason there isn't one), every value
// that was sent with where it came from, and the resume that went with it.
export function ProofList(props) {
  const e = React.createElement;
  const confirmation = props.confirmation || null;
  const fields = Array.isArray(props.fields) ? props.fields : [];
  const resume = props.resume || null;
  const noProofReason = props.noProofReason || 'There is no confirmation screenshot for this application.';
  const requested = Number(props.headingLevel) || 2;
  const level = Math.min(Math.max(requested, 1), 5);
  const headingTag = 'h' + level;
  const subTag = 'h' + (level + 1);
  const headingId = React.useId();

  function srOnly(text) {
    return e('span', { className: 'aa-proof-list__sr-only' }, text);
  }

  function sourceNode(source) {
    if (!source || !source.text) return null;
    return e(
      'dd',
      { className: 'aa-proof-list__source aa-mono' },
      srOnly('Source: '),
      e('span', { className: 'aa-proof-list__arrow', 'aria-hidden': 'true' }, '← '),
      source.href
        ? e('a', { className: 'aa-proof-list__link', href: source.href }, source.text)
        : e('span', { className: 'aa-proof-list__source-text' }, source.text)
    );
  }

  function fieldRow(field, index) {
    const hasValue = field.value !== undefined && field.value !== null && String(field.value) !== '';
    return e(
      'div',
      { key: field.label + '-' + index, className: 'aa-proof-list__row' },
      e('dt', { className: 'aa-proof-list__label aa-small' }, field.label),
      e(
        'dd',
        { className: 'aa-proof-list__value aa-mono' },
        hasValue
          ? String(field.value)
          : e(React.Fragment, null, e('span', { 'aria-hidden': 'true' }, '–'), srOnly('Left blank'))
      ),
      sourceNode(field.source)
    );
  }

  let confirmationNode;
  if (confirmation) {
    const alt = confirmation.alt || 'Confirmation page';
    confirmationNode = e(
      'figure',
      { className: 'aa-proof-list__shot' },
      e(
        'div',
        { className: 'aa-proof-list__frame' },
        confirmation.src
          ? e('img', { className: 'aa-proof-list__img', src: confirmation.src, alt: alt })
          : e('div', { className: 'aa-proof-list__placeholder', role: 'img', 'aria-label': alt })
      ),
      e(
        'figcaption',
        { className: 'aa-proof-list__caption aa-mono' },
        e(
          'span',
          null,
          'Confirmation page' + (confirmation.time ? ' · ' + confirmation.time : '')
        ),
        confirmation.src
          ? e('a', { className: 'aa-proof-list__link', href: confirmation.src }, 'Open full size')
          : null
      )
    );
  } else {
    confirmationNode = e(Notice, { tone: 'info' }, noProofReason);
  }

  return e(
    'section',
    { className: 'aa-proof-list', 'aria-labelledby': headingId },
    e(headingTag, { id: headingId, className: 'aa-proof-list__heading aa-title' }, 'Proof'),
    confirmationNode,
    e(
      'div',
      { className: 'aa-proof-list__receipt' },
      e(subTag, { className: 'aa-proof-list__subheading aa-label' }, 'What was sent'),
      fields.length > 0
        ? e('dl', { className: 'aa-proof-list__fields' }, fields.map(fieldRow))
        : e('p', { className: 'aa-proof-list__empty aa-small' }, 'Nothing has been sent yet.'),
      resume && resume.name
        ? e(
            'p',
            { className: 'aa-proof-list__resume' },
            e('span', { className: 'aa-proof-list__label aa-small' }, 'Resume sent', srOnly(':')),
            e(
              'span',
              { className: 'aa-proof-list__value aa-mono' },
              resume.href
                ? e('a', { className: 'aa-proof-list__link aa-proof-list__link--file', href: resume.href }, resume.name)
                : resume.name
            )
          )
        : null
    )
  );
}
