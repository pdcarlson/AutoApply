import React from 'react';

// Notice: an inline message box with a symbol, an optional title, a body and an optional action.
// Tones: info, needs (the student is needed), error, success.
export function Notice(props) {
  const { tone = 'info', title, children, action } = props;
  const e = React.createElement;

  const toneWords = { info: 'Note', needs: 'Needs you', error: 'Error', success: 'Done' };
  const t = Object.prototype.hasOwnProperty.call(toneWords, tone) ? tone : 'info';

  const svgProps = { width: 16, height: 16, viewBox: '0 0 16 16', focusable: 'false' };
  const ring = e('circle', {
    key: 'ring',
    cx: 8,
    cy: 8,
    r: 6.75,
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.5,
  });
  let symbol;
  if (t === 'needs') {
    // The needs dot: needs fill with a needs-ink edge, same as the dot on a waiting card.
    symbol = e('svg', svgProps, e('circle', { className: 'aa-notice__dot', cx: 8, cy: 8, r: 5.5, strokeWidth: 1.5 }));
  } else if (t === 'error') {
    symbol = e(
      'svg',
      svgProps,
      ring,
      e('path', { key: 'bar', d: 'M8 4.5v4.25', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round' }),
      e('circle', { key: 'point', cx: 8, cy: 11.25, r: 0.9, fill: 'currentColor' })
    );
  } else if (t === 'success') {
    symbol = e(
      'svg',
      svgProps,
      ring,
      e('path', {
        key: 'check',
        d: 'M5.25 8.25l1.9 1.9 3.6-3.9',
        fill: 'none',
        stroke: 'currentColor',
        strokeWidth: 1.5,
        strokeLinecap: 'round',
        strokeLinejoin: 'round',
      })
    );
  } else {
    symbol = e(
      'svg',
      svgProps,
      ring,
      e('circle', { key: 'point', cx: 8, cy: 4.9, r: 0.9, fill: 'currentColor' }),
      e('path', { key: 'bar', d: 'M8 7.25v4.25', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round' })
    );
  }

  const hasBody = children !== undefined && children !== null && children !== false && children !== '';
  // Screen readers hear the tone word first, since the symbol is hidden from them.
  const toneWord = e('span', { className: 'aa-notice__sr' }, toneWords[t] + ': ');

  const titleEl = title ? e('p', { className: 'aa-notice__title' }, toneWord, title) : null;
  const bodyEl = hasBody
    ? e('div', { className: 'aa-notice__body' }, title ? null : toneWord, children)
    : null;

  return e(
    'div',
    { className: 'aa-notice aa-notice--' + t, role: 'status' },
    e(
      'div',
      { className: 'aa-notice__main' },
      e('span', { className: 'aa-notice__icon', 'aria-hidden': 'true' }, symbol),
      e('div', { className: 'aa-notice__content' }, titleEl, bodyEl)
    ),
    action ? e('div', { className: 'aa-notice__action' }, action) : null
  );
}
