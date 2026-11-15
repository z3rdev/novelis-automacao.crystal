import { expect,it } from "vitest";
import { fmtDate } from "./format";

it("mantém o dia civil de emissão e vigência sem deslocamento UTC",()=>{
  expect(fmtDate("2026-11-14")).toBe("14/11/2026");
  expect(fmtDate("2026-12-31")).toBe("31/12/2026");
  expect(fmtDate("2027-01-01")).toBe("01/01/2027");
  expect(fmtDate(null)).toBe("—");
});
