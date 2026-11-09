import { describe, it, expect } from "vitest";
import { journalRows, currentRecommendation } from "./results";
import { fixture } from "@/test/fixtures";
describe("saved evidence across both protocols", () => {
  it("keeps actual 4B GPU/CPU measurements ahead of the tiny manual test", () => {
    const rows = journalRows(fixture());
    expect(rows).toHaveLength(3);
    expect(rows[0]).toMatchObject({
      model: "Qwen3 4B · Q4_K_M",
      device: "GPU",
      generation: 19.46,
      recommended: true,
      method: "prompt",
    });
    expect(rows[1]).toMatchObject({
      device: "CPU",
      generation: 9.8,
      recommended: false,
    });
    expect(rows[2].method).toBe("bench");
    expect(rows[0].note).toContain("deleted; evidence retained");
  });
  it("never turns failed or non-finite measurements into journal scores", () => {
    const s = fixture();
    s.scans = structuredClone(s.scans);
    s.scans[0].attempts[0].status = "failed";
    s.scans[0].attempts[1].generation_tokens_per_second = NaN;
    expect(journalRows(s)).toHaveLength(1);
  });
  it("does not mutate persisted source records", () => {
    const s = fixture();
    const before = JSON.stringify(s);
    journalRows(s);
    expect(JSON.stringify(s)).toBe(before);
  });
});

it("does not recommend copied or unidentified results for this laptop",()=>{const s=fixture();s.scans=structuredClone(s.scans);s.scans[0].device_scope="other";expect(currentRecommendation(s.scans)).toBeUndefined();expect(journalRows(s)[0]).toMatchObject({deviceScope:"other",recommended:false,generation:19.46});s.scans[0].device_scope="unverified";expect(currentRecommendation(s.scans)).toBeUndefined();s.scans[0].device_scope="current";expect(currentRecommendation(s.scans)?.recommendation?.generation_tokens_per_second).toBe(19.46);});
