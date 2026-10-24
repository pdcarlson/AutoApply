import React from 'react';

// TextField: a labeled text input or textarea with an optional hint and error below it.
export function TextField(props) {
  const {
    id,
    label,
    hint,
    error,
    value,
    onChange,
    placeholder,
    type = 'text',
    multiline = false,
    rows = 4,
    required = false,
    inputMode,
    autoFocus = false,
    disabled = false,
  } = props;
  const e = React.createElement;

  const generatedId = React.useId();
  const fieldId = id || 'aa-text-field-' + generatedId.replace(/[^A-Za-z0-9_-]/g, '');
  const hintId = fieldId + '-hint';
  const errorId = fieldId + '-error';
  const hasHint = hint !== undefined && hint !== null && hint !== false && hint !== '';
  const hasError = error !== undefined && error !== null && error !== false && error !== '';
  const describedBy = [hasHint ? hintId : '', hasError ? errorId : '']
    .filter(Boolean)
    .join(' ');

  const controlProps = {
    id: fieldId,
    className: 'aa-text-field__input' + (multiline ? ' aa-text-field__input--multiline' : ''),
    value: value,
    onChange: onChange,
    placeholder: placeholder,
    required: !!required,
    disabled: !!disabled,
    autoFocus: !!autoFocus,
    inputMode: inputMode,
    'aria-invalid': hasError ? 'true' : undefined,
    'aria-describedby': describedBy || undefined,
  };

  const control = multiline
    ? e('textarea', Object.assign({}, controlProps, { rows: rows }))
    : e('input', Object.assign({}, controlProps, { type: type }));

  const labelEl = label
    ? e(
        'label',
        { className: 'aa-text-field__label', htmlFor: fieldId },
        e('span', null, label),
        required
          ? e('span', { className: 'aa-text-field__required', 'aria-hidden': 'true' }, 'Required')
          : null
      )
    : null;

  const hintEl = hasHint ? e('p', { id: hintId, className: 'aa-text-field__hint' }, hint) : null;

  const errorEl = hasError
    ? e(
        'p',
        { id: errorId, className: 'aa-text-field__error' },
        e(
          'span',
          { className: 'aa-text-field__error-icon', 'aria-hidden': 'true' },
          e(
            'svg',
            { width: 14, height: 14, viewBox: '0 0 16 16', focusable: 'false' },
            e('circle', { cx: 8, cy: 8, r: 6.75, fill: 'none', stroke: 'currentColor', strokeWidth: 1.5 }),
            e('path', { d: 'M8 4.5v4.25', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round' }),
            e('circle', { cx: 8, cy: 11.25, r: 0.9, fill: 'currentColor' })
          )
        ),
        e('span', null, error)
      )
    : null;

  return e(
    'div',
    {
      className:
        'aa-text-field' +
        (hasError ? ' aa-text-field--error' : '') +
        (disabled ? ' aa-text-field--disabled' : ''),
    },
    labelEl,
    control,
    hintEl,
    errorEl
  );
}
