// Change pages from code, e.g. go("inbox") or go("needs-you/3").
export function go(path) {
  window.location.hash = `/${path}`;
}
