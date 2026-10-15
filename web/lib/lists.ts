// Long bullet lists in an answer: the first VISIBLE items show, the rest sit behind a toggle. Pure
// helpers (no React); the text of the items is never changed.

export const VISIBLE_ITEMS = 5;

/** A list collapses only when it has more than VISIBLE_ITEMS items. */
export const shouldCollapse = (count: number): boolean => count > VISIBLE_ITEMS;

/** How many items are hidden while the list is collapsed. */
export const hiddenCount = (count: number): number => Math.max(0, count - VISIBLE_ITEMS);

/** The toggle's words: "Show all 10 items" while collapsed, "Show fewer" while open. */
export const toggleLabel = (count: number, open: boolean): string => (open ? "Show fewer" : `Show all ${count} items`);
