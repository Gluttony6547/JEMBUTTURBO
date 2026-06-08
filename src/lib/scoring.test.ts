import { describe, expect, it } from "vitest";
import { computeMetrics, rankPlayers } from "./scoring";

describe("scoring", () => {
  it("computes completed typing metrics", () => {
    const metrics = computeMetrics("hello world", "hello world", 12);
    expect(metrics.finished).toBe(true);
    expect(metrics.progress).toBe(1);
    expect(metrics.accuracy).toBe(100);
    expect(metrics.wpm).toBeGreaterThan(0);
    expect(metrics.score).toBeGreaterThanOrEqual(25);
  });

  it("keeps finished players ranked above unfinished players", () => {
    const ranked = rankPlayers([
      { finished: false, finish_time: null, wpm: 90, accuracy: 100, score: 90 },
      { finished: true, finish_time: 20, wpm: 50, accuracy: 95, score: 70 },
    ]);
    expect(ranked[0].finished).toBe(true);
  });
});
