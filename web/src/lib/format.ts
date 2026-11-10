// Display formatting only. Precision matches what the Streamlit app shows for each field.

export const signed = (x: number | null | undefined, dp = 1): string =>
  x == null || Number.isNaN(x) ? "n/a" : `${x >= 0 ? "+" : ""}${x.toFixed(dp)}`;

export const fixed = (x: number | null | undefined, dp = 1): string =>
  x == null || Number.isNaN(x) ? "n/a" : x.toFixed(dp);

/** Fraction (0.44) to "44%"; one decimal when asked (true shooting, 3P%). */
export const pct = (x: number | null | undefined, dp = 0): string =>
  x == null || Number.isNaN(x) ? "n/a" : `${(x * 100).toFixed(dp)}%`;

export const height = (inches: number | null | undefined): string =>
  inches == null ? "n/a" : `${Math.floor(inches / 12)}'${Math.round(inches % 12)}"`;

export const initials = (name: string): string =>
  name
    .split(/\s+/)
    .filter((p) => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(p))
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

export const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? "" : "s"}`;
