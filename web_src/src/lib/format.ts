// SPDX-License-Identifier: Apache-2.0

export function fmtNum(n: number | null | undefined, digits = 0): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function fmtCost(usd: number | null | undefined): string {
  if (usd == null) return "—";
  if (usd === 0) return "$0.0000";
  // Sub-cent values get 4 decimals so the user can read fractional tokens;
  // anything ≥ $1 is fine with 2 decimals.
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

/**
 * Returns a short descriptor for the cost cap. When the cap is null or
 * "effectively no cap" ( ≥ $100 — the slider's normal upper end is $50 ),
 * we suppress the dollar amount and tell the UI to render "no cap" so a
 * `$9999.00 cap` doesn't dominate the display.
 */
export function fmtCap(
  cap: number | null | undefined,
  noCapLabel = "no cap",
): { label: string; effectivelyNoCap: boolean } {
  if (cap == null) return { label: noCapLabel, effectivelyNoCap: true };
  if (cap >= 100) return { label: noCapLabel, effectivelyNoCap: true };
  return { label: `${fmtCost(cap)} cap`, effectivelyNoCap: false };
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms == null || ms === 0) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
}

/**
 * Elapsed / ETA formatter. Returns mm:ss for under an hour, hh:mm:ss above.
 * The previous "5s" / "4m 15s" mixed format made elapsed times ambiguous
 * on small numbers ("12s" looks like a quantity, not a clock).
 */
export function fmtElapsed(ms: number | null | undefined): string {
  if (ms == null) return "—";
  const total = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function fmtAcc(acc: number | null | undefined): string {
  if (acc == null) return "—";
  return acc.toFixed(3);
}

/**
 * Accuracy formatter for in-progress runs. Shows "—" until at least one
 * scored response is in. Once we have data, returns a 3-digit fraction
 * (`0.667`) — same as `fmtAcc`. Keeping the two functions separate lets
 * us experiment with phasing in (e.g. dot string before first sample).
 */
export function fmtAccLive(
  acc: number | null | undefined,
  current: number,
): string {
  if (acc == null) return "—";
  if (current === 0) return "—";
  return acc.toFixed(3);
}
