import React from 'react';

// The nine application statuses, in the order an application usually moves
// through them. Every screen uses these exact words.
export const STATUSES = {
  'queued': { label: 'Queued' },
  'filling': { label: 'Filling' },
  'needs-you': { label: 'Needs you' },
  'submitted': { label: 'Submitted' },
  'submitted-by-you': { label: 'Submitted by you' },
  'skipped': { label: 'Skipped' },
  'stopped': { label: 'Stopped' },
  'failed': { label: 'Failed' },
  'check-before-retrying': { label: 'Check before retrying' }
};

// One small symbol per status, drawn on a 16 by 16 grid in currentColor,
// so the status never depends on color alone.
function statusPillSymbol(status) {
  const h = React.createElement;
  const line = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' };
  switch (status) {
    case 'queued':
      // Hollow circle: waiting its turn.
      return [h('circle', { key: 'a', cx: 8, cy: 8, r: 5.5, fill: 'none', stroke: 'currentColor', strokeWidth: 2 })];
    case 'filling':
      // Half circle: under way.
      return [
        h('circle', { key: 'a', cx: 8, cy: 8, r: 5.5, fill: 'none', stroke: 'currentColor', strokeWidth: 2 }),
        h('path', { key: 'b', d: 'M8 2.5 A5.5 5.5 0 0 0 8 13.5 Z', fill: 'currentColor' })
      ];
    case 'needs-you':
      // Solid dot: the same dot that marks a waiting card.
      return [h('circle', { key: 'a', cx: 8, cy: 8, r: 4, fill: 'currentColor' })];
    case 'submitted':
      // Check in a circle: sent and confirmed.
      return [
        h('circle', { key: 'a', cx: 8, cy: 8, r: 6, fill: 'none', stroke: 'currentColor', strokeWidth: 1.75 }),
        h('path', Object.assign({ key: 'b', d: 'M5.25 8.25 L7.25 10.25 L10.75 6.25' }, line))
      ];
    case 'submitted-by-you':
      // Plain check: sent by the student, no confirmation screenshot.
      return [h('path', Object.assign({ key: 'a', d: 'M3.5 8.5 L6.5 11.5 L12.5 4.5' }, line))];
    case 'skipped':
      // Dash: left out on purpose.
      return [h('path', Object.assign({ key: 'a', d: 'M3.5 8 H12.5' }, line))];
    case 'stopped':
      // Square: stopped before it was sent.
      return [h('rect', { key: 'a', x: 3.5, y: 3.5, width: 9, height: 9, rx: 1.5, fill: 'currentColor' })];
    case 'failed':
      // X: never got to submit.
      return [h('path', Object.assign({ key: 'a', d: 'M4.5 4.5 L11.5 11.5 M11.5 4.5 L4.5 11.5' }, line))];
    case 'check-before-retrying':
      // Exclamation mark: look before you retry.
      return [
        h('path', Object.assign({ key: 'a', d: 'M8 3 V9.25' }, line)),
        h('circle', { key: 'b', cx: 8, cy: 12.75, r: 1.25, fill: 'currentColor' })
      ];
    default:
      return [h('circle', { key: 'a', cx: 8, cy: 8, r: 5.5, fill: 'none', stroke: 'currentColor', strokeWidth: 2 })];
  }
}

export function StatusPill(props) {
  const h = React.createElement;
  const status = props.status;
  const size = props.size === 'sm' ? 'sm' : 'md';
  const known = Object.prototype.hasOwnProperty.call(STATUSES, status);
  const label = known ? STATUSES[status].label : String(status || '');
  const modifier = known ? status : 'unknown';

  return h(
    'span',
    {
      className: 'aa-status-pill aa-status-pill--' + modifier + ' aa-status-pill--' + size,
      'data-status': known ? status : undefined
    },
    h(
      'svg',
      {
        className: 'aa-status-pill__symbol',
        viewBox: '0 0 16 16',
        width: 16,
        height: 16,
        'aria-hidden': 'true',
        focusable: 'false'
      },
      statusPillSymbol(status)
    ),
    h('span', { className: 'aa-status-pill__label' }, label)
  );
}
