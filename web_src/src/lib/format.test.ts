import { describe, expect, it } from "vitest";

import { fmtAcc, fmtCost, fmtMs, fmtNum } from "./format";

describe("format helpers", () => {
  it("formats nullable values consistently", () => {
    expect(fmtNum(null)).toBe("—");
    expect(fmtCost(undefined)).toBe("—");
    expect(fmtMs(0)).toBe("—");
  });

  it("formats dashboard numbers", () => {
    expect(fmtNum(1234)).toBe("1,234");
    expect(fmtCost(0.001234)).toBe("$0.0012");
    expect(fmtCost(0.123456)).toBe("$0.123");
    expect(fmtMs(1234)).toBe("1.23s");
    expect(fmtAcc(0.98765)).toBe("0.988");
  });
});
