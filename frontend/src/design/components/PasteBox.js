import React from 'react';
import { Button } from './Button.js';

// True when the text looks like an http or https link with a real host name.
// The server decides whether it is a Greenhouse, Lever or Ashby job.
function pasteBoxLooksLikeLink(text) {
  const t = String(text || '').trim();
  if (!/^https?:\/\/\S+$/i.test(t)) return false;
  try {
    const u = new URL(t);
    return (u.protocol === 'http:' || u.protocol === 'https:') && u.hostname.indexOf('.') > 0;
  } catch (e) {
    return false;
  }
}

const PASTE_BOX_TONES = { info: true, needs: true, error: true };

// Symbol in front of the message, so the tone never depends on color alone.
function pasteBoxSymbol(tone) {
  const h = React.createElement;
  const line = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.75, strokeLinecap: 'round' };
  let parts;
  if (tone === 'needs') {
    // The amber "you are needed" dot with its dark edge.
    parts = [h('circle', { key: 'a', className: 'aa-paste-box__dot', cx: 8, cy: 8, r: 4.5, strokeWidth: 1.5 })];
  } else if (tone === 'error') {
    // Circle with an x.
    parts = [
      h('circle', Object.assign({ key: 'a', cx: 8, cy: 8, r: 6.25 }, line)),
      h('path', Object.assign({ key: 'b', d: 'M5.75 5.75 L10.25 10.25 M10.25 5.75 L5.75 10.25' }, line))
    ];
  } else {
    // Circle with an i.
    parts = [
      h('circle', Object.assign({ key: 'a', cx: 8, cy: 8, r: 6.25 }, line)),
      h('path', Object.assign({ key: 'b', d: 'M8 7.5 V11' }, line)),
      h('circle', { key: 'c', cx: 8, cy: 5, r: 1, fill: 'currentColor' })
    ];
  }
  return h(
    'svg',
    { className: 'aa-paste-box__symbol', viewBox: '0 0 16 16', 'aria-hidden': 'true', focusable: 'false' },
    parts
  );
}

export function PasteBox(props) {
  const h = React.createElement;
  const onApply = props.onApply;
  const message = props.message || null;
  const disabled = !!props.disabled;
  const autoFocus = !!props.autoFocus;

  const [text, setText] = React.useState('');
  const inputRef = React.useRef(null);
  const baseId = React.useId();
  const inputId = baseId + '-paste-link';
  const messageId = baseId + '-paste-message';

  // A new message object gets a new node, so screen readers hear it even
  // when the words match the last one (the same duplicate pasted twice).
  const turn = React.useRef({ message: null, n: 0 });
  if (turn.current.message !== message) {
    turn.current = { message: message, n: turn.current.n + 1 };
  }

  const ready = !disabled && pasteBoxLooksLikeLink(text);

  function handleSubmit(event) {
    event.preventDefault();
    if (!ready) return;
    const url = text.trim();
    setText('');
    // Keep the cursor in the box so the next link can be pasted right away.
    if (inputRef.current) inputRef.current.focus();
    if (typeof onApply === 'function') onApply(url);
  }

  let messageNode = null;
  if (message && message.text) {
    const tone = PASTE_BOX_TONES[message.tone] ? message.tone : 'info';
    const link = message.href
      ? h('a', { className: 'aa-paste-box__link', href: message.href }, message.linkText || 'Open it')
      : null;
    messageNode = h(
      'p',
      { key: turn.current.n, className: 'aa-paste-box__message aa-paste-box__message--' + tone },
      pasteBoxSymbol(tone),
      h('span', { className: 'aa-paste-box__text' }, message.text, link ? ' ' : null, link)
    );
  }

  return h(
    'form',
    { className: 'aa-paste-box', onSubmit: handleSubmit, noValidate: true },
    h(
      'label',
      { className: 'aa-paste-box__label aa-body-strong', htmlFor: inputId },
      'Paste a Greenhouse, Lever or Ashby job link'
    ),
    h(
      'div',
      { className: 'aa-paste-box__row' },
      h('input', {
        ref: inputRef,
        id: inputId,
        className: 'aa-paste-box__input',
        type: 'url',
        inputMode: 'url',
        autoComplete: 'off',
        autoCapitalize: 'off',
        autoCorrect: 'off',
        spellCheck: false,
        placeholder: 'https://jobs.lever.co/…',
        value: text,
        disabled: disabled,
        autoFocus: autoFocus,
        'aria-describedby': messageId,
        onChange: function (event) { setText(event.target.value); }
      }),
      h(Button, { variant: 'primary', type: 'submit', disabled: !ready }, 'Apply')
    ),
    h(
      'div',
      { id: messageId, className: 'aa-paste-box__status', 'aria-live': 'polite', 'aria-atomic': 'true' },
      messageNode
    )
  );
}
