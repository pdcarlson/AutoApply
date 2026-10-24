import React from 'react';

// Button: one action, or one link styled as a button when href is set.
// Variants: primary (ink fill), secondary (outlined), quiet (text), danger (red text and edge).
export function Button(props) {
  const {
    variant = 'primary',
    size = 'md',
    disabled = false,
    type = 'button',
    onClick,
    href,
    children,
    ariaLabel,
  } = props;

  const knownVariants = ['primary', 'secondary', 'quiet', 'danger'];
  const v = knownVariants.indexOf(variant) === -1 ? 'primary' : variant;
  const s = size === 'sm' ? 'sm' : 'md';
  const className =
    'aa-button aa-button--' + v + ' aa-button--' + s + (disabled ? ' aa-button--disabled' : '');

  if (href) {
    if (disabled) {
      // A disabled link has no href, so it leaves the tab order and can't be followed.
      return React.createElement(
        'a',
        { className: className, role: 'link', 'aria-disabled': 'true', 'aria-label': ariaLabel },
        children
      );
    }
    return React.createElement(
      'a',
      { className: className, href: href, onClick: onClick, 'aria-label': ariaLabel },
      children
    );
  }

  return React.createElement(
    'button',
    {
      className: className,
      type: type,
      disabled: !!disabled,
      onClick: onClick,
      'aria-label': ariaLabel,
    },
    children
  );
}
