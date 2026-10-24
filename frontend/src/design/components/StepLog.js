import React from 'react';

// StepLog: the receipt of what the agent did on one application.
// One mono line per step: time, what happened, where the value came from.
// steps arrive oldest first. When live, the newest step goes on top with a
// large screenshot, and a hidden polite live region reads only that line.

function stepLogPad(n) {
  return n < 10 ? '0' + n : String(n);
}

// Returns { text, dateTime } for a step time. Accepts "HH:MM:SS",
// a Date, a number (ms) or an ISO date-time string.
function stepLogTime(time) {
  if (time === null || time === undefined || time === '') {
    return { text: '', dateTime: undefined };
  }
  let date = null;
  if (time instanceof Date) {
    date = time;
  } else if (typeof time === 'number') {
    date = new Date(time);
  } else {
    const s = String(time).trim();
    if (/^\d{2}:\d{2}(:\d{2})?$/.test(s)) {
      return { text: s, dateTime: s };
    }
    if (/^\d{4}-\d{2}-\d{2}T/.test(s)) {
      date = new Date(s);
    } else {
      return { text: s, dateTime: undefined };
    }
  }
  if (!date || isNaN(date.getTime())) {
    return { text: '', dateTime: undefined };
  }
  return {
    text: stepLogPad(date.getHours()) + ':' + stepLogPad(date.getMinutes()) + ':' + stepLogPad(date.getSeconds()),
    dateTime: date.toISOString(),
  };
}

// "Profile", "<- Profile" or "← Profile" all become "Profile".
function stepLogSource(source) {
  if (source === null || source === undefined) return '';
  return String(source).replace(/^\s*(←|<-)\s*/, '').trim();
}

// The line a screen reader hears for the newest step.
function stepLogSpoken(step) {
  if (!step) return '';
  const time = stepLogTime(step.time).text;
  const source = stepLogSource(step.source);
  let line = (time ? time + ' ' : '') + String(step.text || '');
  if (source) line += ', from ' + source;
  return line;
}

export function StepLog(props) {
  const e = React.createElement;
  const steps = Array.isArray(props.steps) ? props.steps : [];
  const live = props.live === true;
  const onOpenScreenshot = typeof props.onOpenScreenshot === 'function' ? props.onOpenScreenshot : null;

  // Oldest first when finished; newest first while live.
  const ordered = live ? steps.slice().reverse() : steps;
  const newest = steps.length ? steps[steps.length - 1] : null;

  // The live region speaks only once this log has been live, so a finished
  // log opened later doesn't repeat its last line, but the final step of a
  // run you were watching is still announced.
  const wasLive = React.useRef(false);
  if (live) wasLive.current = true;
  const spoken = live || wasLive.current ? stepLogSpoken(newest) : '';

  function renderShot(step, isCurrent) {
    const shot = step.screenshot;
    const text = String(step.text || '');

    if (!shot) {
      if (!isCurrent) return null;
      // Newest step, screenshot not saved yet. Visual only.
      return e(
        'span',
        { className: 'aa-step-log__shot aa-step-log__shot--empty', 'aria-hidden': 'true' },
        'No screenshot yet'
      );
    }

    // The wrapper (button or role="img") carries the accessible name.
    const inner = shot.src
      ? e('img', {
          className: 'aa-step-log__img',
          src: shot.src,
          alt: '',
          loading: isCurrent ? undefined : 'lazy',
          decoding: 'async',
        })
      : e('span', { className: 'aa-step-log__placeholder', 'aria-hidden': 'true' });

    if (onOpenScreenshot) {
      return e(
        'button',
        {
          type: 'button',
          className: 'aa-step-log__shot aa-step-log__shot--button',
          'aria-label': 'Open screenshot for step: ' + text,
          onClick: function () {
            onOpenScreenshot(step);
          },
        },
        inner
      );
    }

    return e(
      'span',
      {
        className: 'aa-step-log__shot',
        role: 'img',
        'aria-label': shot.alt || 'Screenshot for step: ' + text,
      },
      inner
    );
  }

  const items = ordered.map(function (step, index) {
    const isCurrent = live && index === 0;
    const time = stepLogTime(step.time);
    const source = stepLogSource(step.source);
    const key = step.id !== null && step.id !== undefined ? step.id : 'step-' + index;

    return e(
      'li',
      {
        key: key,
        className: 'aa-step-log__item' + (isCurrent ? ' aa-step-log__item--current' : ''),
      },
      e('time', { className: 'aa-step-log__time', dateTime: time.dateTime }, time.text),
      e(
        'span',
        { className: 'aa-step-log__what' },
        e('span', { className: 'aa-step-log__text' }, String(step.text || '')),
        source
          ? e(
              'span',
              { className: 'aa-step-log__source' },
              e('span', { className: 'aa-step-log__sr' }, 'from '),
              e('span', { 'aria-hidden': 'true' }, '← '),
              source
            )
          : null
      ),
      renderShot(step, isCurrent)
    );
  });

  return e(
    'div',
    { className: 'aa-step-log' + (live ? ' aa-step-log--live' : '') },
    live
      ? e(
          'div',
          { className: 'aa-step-log__head' },
          e(
            'span',
            { className: 'aa-step-log__live' },
            e(
              'svg',
              {
                className: 'aa-step-log__live-icon',
                viewBox: '0 0 12 12',
                'aria-hidden': 'true',
                focusable: 'false',
              },
              e('circle', { cx: 6, cy: 6, r: 5, fill: 'none', stroke: 'currentColor', strokeWidth: 1.5 }),
              e('circle', { className: 'aa-step-log__live-dot', cx: 6, cy: 6, r: 2.5, fill: 'currentColor' })
            ),
            e('span', null, 'Live')
          ),
          e('span', { className: 'aa-step-log__order' }, 'Newest first')
        )
      : null,
    items.length
      ? e(
          'ol',
          {
            className: 'aa-step-log__list',
            role: 'list',
            reversed: live || undefined,
            'aria-label': live ? 'Steps, newest first' : 'Steps',
          },
          items
        )
      : e('p', { className: 'aa-step-log__empty' }, 'No steps yet'),
    // Polite live region: holds only the newest line, so screen readers hear
    // each new step once and are never interrupted.
    e('p', { className: 'aa-step-log__sr', 'aria-live': 'polite', 'aria-atomic': 'true' }, spoken)
  );
}
