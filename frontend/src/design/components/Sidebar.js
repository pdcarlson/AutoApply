import React from 'react';
import { Button } from './Button.js';

// Sidebar: the app frame's navigation.
// Laptop: a left column with the app name, the page links, the agent line and Sign out.
// Below 768px: a top bar with the app name, the Needs you count and a Menu button
// that opens the same links in a floating panel.
export function Sidebar(props) {
  const h = React.createElement;
  const items = Array.isArray(props.items) ? props.items : [];
  const agentLine = props.agentLine || null;
  const user = props.user || {};
  const onSignOut = props.onSignOut;
  const appName = props.appName || 'AutoApply';
  const layout = props.layout === 'laptop' || props.layout === 'phone' ? props.layout : 'auto';

  const [open, setOpen] = React.useState(false);
  const panelId = React.useId();
  const barRef = React.useRef(null);
  const menuButtonRef = React.useRef(null);

  // While the phone menu is open, Escape or a tap outside the bar closes it.
  React.useEffect(
    function () {
      if (!open) return undefined;
      function handlePointer(event) {
        if (barRef.current && !barRef.current.contains(event.target)) setOpen(false);
      }
      function handleKey(event) {
        if (event.key === 'Escape') {
          setOpen(false);
          if (menuButtonRef.current) menuButtonRef.current.focus();
        }
      }
      document.addEventListener('mousedown', handlePointer);
      document.addEventListener('touchstart', handlePointer);
      document.addEventListener('keydown', handleKey);
      return function () {
        document.removeEventListener('mousedown', handlePointer);
        document.removeEventListener('touchstart', handlePointer);
        document.removeEventListener('keydown', handleKey);
      };
    },
    [open]
  );

  function countOf(item) {
    const n = Number(item && item.count);
    return isFinite(n) && n > 0 ? Math.floor(n) : 0;
  }

  // The number is for sighted users; screen readers hear "3 waiting".
  function countBadge(count) {
    return h(
      'span',
      { className: 'aa-sidebar__count' },
      h('span', { 'aria-hidden': 'true' }, String(count)),
      h('span', { className: 'aa-sidebar__sr' }, ', ' + count + ' waiting')
    );
  }

  function navLinks(where) {
    return h(
      'nav',
      { className: 'aa-sidebar__nav', 'aria-label': 'Main' },
      h(
        'ul',
        { className: 'aa-sidebar__list' },
        items.map(function (item, index) {
          const count = countOf(item);
          return h(
            'li',
            { key: (item.href || item.label || '') + '-' + index, className: 'aa-sidebar__item' },
            h(
              'a',
              {
                className: 'aa-sidebar__link' + (item.current ? ' aa-sidebar__link--current' : ''),
                href: item.href,
                'aria-current': item.current ? 'page' : undefined,
                onClick:
                  where === 'panel'
                    ? function () {
                        setOpen(false);
                      }
                    : undefined,
              },
              h('span', { className: 'aa-sidebar__link-label' }, item.label),
              count > 0 ? countBadge(count) : null
            )
          );
        })
      )
    );
  }

  // One read-only line about what the agent is doing. It links to that application.
  function agentBlock() {
    let line;
    if (agentLine && agentLine.text) {
      line = agentLine.href
        ? h('a', { className: 'aa-sidebar__agent-link', href: agentLine.href }, agentLine.text)
        : h('span', { className: 'aa-sidebar__agent-text' }, agentLine.text);
    } else {
      line = h('span', { className: 'aa-sidebar__agent-idle' }, 'Nothing in line');
    }
    return h(
      'div',
      { className: 'aa-sidebar__agent', role: 'status' },
      h('span', { className: 'aa-sidebar__agent-label' }, 'Agent'),
      line
    );
  }

  function accountBlock() {
    return h(
      'div',
      { className: 'aa-sidebar__account' },
      h(
        'div',
        { className: 'aa-sidebar__who' },
        user.name ? h('span', { className: 'aa-sidebar__user-name' }, user.name) : null,
        user.email ? h('span', { className: 'aa-sidebar__user-email' }, user.email) : null
      ),
      h(Button, { variant: 'quiet', size: 'sm', onClick: onSignOut }, 'Sign out')
    );
  }

  function menuIcon() {
    return h(
      'svg',
      {
        className: 'aa-sidebar__menu-icon',
        width: 16,
        height: 16,
        viewBox: '0 0 16 16',
        fill: 'none',
        stroke: 'currentColor',
        strokeWidth: 1.5,
        strokeLinecap: 'round',
        'aria-hidden': 'true',
        focusable: 'false',
      },
      open
        ? h('path', { d: 'M4 4l8 8M12 4l-8 8' })
        : h('path', { d: 'M2.5 4h11M2.5 8h11M2.5 12h11' })
    );
  }

  const rail =
    layout === 'phone'
      ? null
      : h(
          'div',
          { className: 'aa-sidebar__rail' },
          h('div', { className: 'aa-sidebar__app-name' }, appName),
          navLinks('rail'),
          agentBlock(),
          accountBlock()
        );

  const waitingItems = items.filter(function (item) {
    return countOf(item) > 0;
  });

  const bar =
    layout === 'laptop'
      ? null
      : h(
          'div',
          { className: 'aa-sidebar__bar', ref: barRef },
          h(
            'div',
            { className: 'aa-sidebar__bar-row' },
            h('span', { className: 'aa-sidebar__app-name aa-sidebar__app-name--bar' }, appName),
            waitingItems.map(function (item, index) {
              return h(
                'a',
                {
                  key: (item.href || item.label || '') + '-' + index,
                  className: 'aa-sidebar__bar-count',
                  href: item.href,
                  'aria-current': item.current ? 'page' : undefined,
                },
                h('span', { className: 'aa-sidebar__bar-count-label' }, item.label),
                countBadge(countOf(item))
              );
            }),
            h(
              'button',
              {
                type: 'button',
                ref: menuButtonRef,
                className: 'aa-sidebar__menu-button',
                'aria-expanded': open ? 'true' : 'false',
                'aria-controls': panelId,
                onClick: function () {
                  setOpen(!open);
                },
              },
              menuIcon(),
              h('span', null, 'Menu')
            )
          ),
          h(
            'div',
            { id: panelId, className: 'aa-sidebar__panel', hidden: !open },
            navLinks('panel'),
            agentBlock(),
            accountBlock()
          )
        );

  return h('div', { className: 'aa-sidebar aa-sidebar--' + layout }, rail, bar);
}
