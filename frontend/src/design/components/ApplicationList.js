import React from 'react';
import { StatusPill } from './StatusPill.js';

// The list of every application, on the Applications page. Read-only:
// each row's company name is the only way into that application's page,
// so rows never carry buttons. Below 768px each row stacks into a block.
export function ApplicationList(props) {
  const e = React.createElement;
  const applications = Array.isArray(props.applications) ? props.applications : [];
  const emptyText = props.emptyText == null ? 'Paste a job link above to start.' : props.emptyText;
  const caption = props.caption || 'Applications';
  const columns = ['Company', 'Role', 'Site', 'Status', 'Sent', 'Proof'];

  if (applications.length === 0) {
    return e(
      'div',
      { className: 'aa-application-list aa-application-list--empty' },
      e('p', { className: 'aa-application-list__empty aa-body' }, emptyText)
    );
  }

  // Shown only in the stacked phone layout. Hidden from screen readers,
  // which already get the real column headers.
  function cellLabel(text) {
    return e('span', { className: 'aa-application-list__cell-label aa-label', 'aria-hidden': 'true' }, text);
  }

  // An en dash on screen, a plain sentence for screen readers.
  function nothing(srText) {
    return e(
      React.Fragment,
      null,
      e('span', { className: 'aa-application-list__none', 'aria-hidden': 'true' }, '–'),
      e('span', { className: 'aa-application-list__sr-only' }, srText)
    );
  }

  function cell(name, label, content) {
    return e(
      'td',
      { className: 'aa-application-list__cell aa-application-list__cell--' + name, role: 'cell' },
      cellLabel(label),
      e('div', { className: 'aa-application-list__value' }, content)
    );
  }

  function row(app, index) {
    const company = app.company || 'Untitled application';
    return e(
      'tr',
      { key: app.id || app.href || index, className: 'aa-application-list__row', role: 'row' },
      e(
        'th',
        { scope: 'row', role: 'rowheader', className: 'aa-application-list__cell aa-application-list__cell--company' },
        app.href
          ? e('a', { className: 'aa-application-list__company aa-body-strong', href: app.href }, company)
          : e('span', { className: 'aa-application-list__company-text aa-body-strong' }, company)
      ),
      cell('role', 'Role', app.role || nothing('No role listed')),
      cell('site', 'Site', app.site || nothing('Site unknown')),
      cell(
        'status',
        'Status',
        e(
          React.Fragment,
          null,
          e(StatusPill, { status: app.status }),
          app.statusLine
            ? e('div', { className: 'aa-application-list__status-line aa-small' }, app.statusLine)
            : null
        )
      ),
      cell(
        'sent',
        'Sent',
        app.sentDate
          ? e('span', { className: 'aa-application-list__date aa-mono' }, app.sentDate)
          : nothing('Not sent yet')
      ),
      cell(
        'proof',
        'Proof',
        app.proofHref
          ? e(
              'a',
              { className: 'aa-application-list__proof', href: app.proofHref },
              'Proof',
              e('span', { className: 'aa-application-list__sr-only' }, ' for ' + company)
            )
          : nothing('No proof yet')
      )
    );
  }

  return e(
    'div',
    { className: 'aa-application-list' },
    e(
      'table',
      { className: 'aa-application-list__table', role: 'table' },
      e('caption', { className: 'aa-application-list__sr-only' }, caption),
      e(
        'thead',
        { className: 'aa-application-list__head', role: 'rowgroup' },
        e(
          'tr',
          { role: 'row' },
          columns.map(function (name) {
            return e(
              'th',
              { key: name, scope: 'col', role: 'columnheader', className: 'aa-application-list__th aa-label' },
              name
            );
          })
        )
      ),
      e('tbody', { className: 'aa-application-list__body', role: 'rowgroup' }, applications.map(row))
    )
  );
}
