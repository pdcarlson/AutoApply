import React from 'react';
import { Button } from './Button.js';

// StepBar: the Setup header. "Step 2 of 3 · Profile", the step names with
// done, current and next shown by symbol and weight, then the email and Sign out.
export function StepBar(props) {
  const h = React.createElement;
  const steps =
    Array.isArray(props.steps) && props.steps.length > 0
      ? props.steps
      : ['Resume', 'Profile', 'Questions'];
  const total = steps.length;
  let current = Number(props.current);
  if (!isFinite(current)) current = 0;
  current = Math.floor(current);
  if (current < 0) current = 0;
  if (current > total - 1) current = total - 1;
  const user = props.user || {};

  function stepIcon(state) {
    const common = {
      className: 'aa-step-bar__icon',
      width: 16,
      height: 16,
      viewBox: '0 0 16 16',
      'aria-hidden': 'true',
      focusable: 'false',
    };
    if (state === 'done') {
      // Solid circle with a check.
      return h(
        'svg',
        common,
        h('circle', { cx: 8, cy: 8, r: 7, fill: 'currentColor' }),
        h('path', {
          className: 'aa-step-bar__icon-check',
          d: 'M4.75 8.25l2.25 2.25 4.25-4.5',
          fill: 'none',
          strokeWidth: 1.75,
          strokeLinecap: 'round',
          strokeLinejoin: 'round',
        })
      );
    }
    if (state === 'current') {
      // Ring with a dot.
      return h(
        'svg',
        common,
        h('circle', { cx: 8, cy: 8, r: 6.25, fill: 'none', stroke: 'currentColor', strokeWidth: 1.5 }),
        h('circle', { cx: 8, cy: 8, r: 3, fill: 'currentColor' })
      );
    }
    // Next: hollow ring.
    return h(
      'svg',
      common,
      h('circle', { cx: 8, cy: 8, r: 6.25, fill: 'none', stroke: 'currentColor', strokeWidth: 1.5 })
    );
  }

  const stateWords = { done: ', done', current: '', next: ', not started' };

  return h(
    'header',
    { className: 'aa-step-bar' },
    h(
      'div',
      { className: 'aa-step-bar__progress' },
      h(
        'p',
        { className: 'aa-step-bar__count' },
        'Step ' + (current + 1) + ' of ' + total + ' · ' + steps[current]
      ),
      h(
        'ol',
        { className: 'aa-step-bar__steps', 'aria-label': 'Setup steps' },
        steps.map(function (name, index) {
          const state = index < current ? 'done' : index === current ? 'current' : 'next';
          return h(
            'li',
            {
              key: name + '-' + index,
              className: 'aa-step-bar__step aa-step-bar__step--' + state,
              'aria-current': state === 'current' ? 'step' : undefined,
            },
            stepIcon(state),
            h('span', { className: 'aa-step-bar__name' }, name),
            stateWords[state] ? h('span', { className: 'aa-step-bar__sr' }, stateWords[state]) : null
          );
        })
      )
    ),
    h(
      'div',
      { className: 'aa-step-bar__account' },
      user.email ? h('span', { className: 'aa-step-bar__email' }, user.email) : null,
      h(Button, { variant: 'quiet', size: 'sm', onClick: props.onSignOut }, 'Sign out')
    )
  );
}
