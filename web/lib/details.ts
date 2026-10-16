// The technical "How this was found" panel is hidden for ordinary visitors. It shows only when the
// page address has ?details=1 (read in the browser after the page has loaded).

/** True only for a query string that holds details=1 (with or without the leading "?"). */
export function showDetails(search: string): boolean {
  return new URLSearchParams(search).get("details") === "1";
}
