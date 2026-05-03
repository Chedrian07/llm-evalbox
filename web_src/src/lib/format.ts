// SPDX-License-Identifier: Apache-2.0

export function fmtNum(n: number | null | undefined, digits = 0): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function fmtCost(usd: number | null | undefined): string {
  if (usd == null) return "—";
  if (usd === 0) return "$0.0000";
  return `$${usd.toFixed(4)}`;
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms == null || ms === 0) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
}

export function fmtAcc(acc: number | null | undefined): string {
  if (acc == null) return "—";
  return acc.toFixed(3);
}
