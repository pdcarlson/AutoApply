/** Draws a stand-in for the screenshot the backend saves at submit time. */
import type { FilledField } from '@/api/types';

const TEXT_STYLE = 'font-family:Arial,sans-serif;font-size:13px;fill:#262626';
const ROW_HEIGHT = 44;
const MAX_ROWS = 10;

const escapeXml = (text: string) => text.replace(/[<>&"]/g, (c) => `&#${c.charCodeAt(0)};`);

/** One label and filled box per field, stacked down the page. */
function fieldRows(fields: FilledField[]): string {
  return fields
    .slice(0, MAX_ROWS)
    .map((field, index) => {
      const top = index * ROW_HEIGHT;
      return (
        `<text x="24" y="${92 + top}" style="${TEXT_STYLE};fill:#707070">${escapeXml(field.label)}</text>` +
        `<rect x="24" y="${98 + top}" width="552" height="22" rx="3" fill="#f7f7f7" stroke="#d0d0d0"/>` +
        `<text x="32" y="${114 + top}" style="${TEXT_STYLE}">${escapeXml(field.value)}</text>`
      );
    })
    .join('');
}

/** A data URL for an SVG picture of the filled form. */
export function screenshotFor(app: { company: string; role: string; fields: FilledField[] }) {
  const buttonTop = MAX_ROWS * ROW_HEIGHT;
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="560" viewBox="0 0 600 560">` +
    `<rect width="600" height="560" fill="#fff"/><rect width="600" height="28" fill="#ececec"/>` +
    `<text x="24" y="60" style="${TEXT_STYLE};font-size:20px;font-weight:bold">${escapeXml(app.role)} · ${escapeXml(app.company)}</text>` +
    fieldRows(app.fields) +
    `<rect x="24" y="${100 + buttonTop}" width="150" height="30" rx="3" fill="#333"/>` +
    `<text x="40" y="${120 + buttonTop}" style="${TEXT_STYLE};fill:#fff;font-weight:bold">Submit application</text>` +
    `</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
