import { describe, expect, it } from "vitest";
import { GAME_MODES, countWords, generateTargetText } from "./texts";
import type { ModeId } from "../types";

describe("texts", () => {
  it.each(Object.keys(GAME_MODES) as ModeId[])("generates text within mode word range for %s", (mode) => {
    for (let run = 0; run < 20; run += 1) {
      const text = generateTargetText(mode);
      const words = countWords(text);
      expect(words).toBeGreaterThanOrEqual(GAME_MODES[mode].minWords);
      expect(words).toBeLessThanOrEqual(GAME_MODES[mode].maxWords);
    }
  });
});
