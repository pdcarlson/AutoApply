import React from 'react';

// BetaLabel: plain text that marks where an unbuilt feature will live. Never clickable.
export function BetaLabel(props) {
  const { children = 'Coming in beta' } = props;
  return React.createElement('span', { className: 'aa-beta-label' }, children);
}
