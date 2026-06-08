export type Metrics = {
  typed_chars: number;
  correct_chars: number;
  progress: number;
  accuracy: number;
  wpm: number;
  score: number;
  finished: boolean;
};

export function countCorrectChars(targetText: string, typedText: string): number {
  let correct = 0;
  const limit = Math.min(targetText.length, typedText.length);
  for (let index = 0; index < limit; index += 1) {
    if (targetText[index] === typedText[index]) {
      correct += 1;
    }
  }
  return correct;
}

export function computeMetrics(
  targetText: string,
  typedText: string,
  elapsedSeconds: number,
  completionBonus = 25,
): Metrics {
  const cappedText = typedText.slice(0, targetText.length);
  const typedChars = cappedText.length;
  const correctChars = countCorrectChars(targetText, cappedText);
  const totalChars = Math.max(targetText.length, 1);
  const elapsedMinutes = Math.max(elapsedSeconds, 0.1) / 60;
  const progress = correctChars / totalChars;
  const accuracy = (correctChars / Math.max(typedChars, 1)) * 100;
  const wpm = correctChars / 5 / elapsedMinutes;
  const finished = cappedText === targetText;
  const score = Math.round(wpm * (accuracy / 100)) + (finished ? completionBonus : 0);

  return {
    typed_chars: typedChars,
    correct_chars: correctChars,
    progress: Number(progress.toFixed(4)),
    accuracy: Number(accuracy.toFixed(2)),
    wpm: Number(wpm.toFixed(2)),
    score,
    finished,
  };
}

export function rankPlayers<T extends { finished: boolean; finish_time: number | null; wpm: number; accuracy: number; score: number }>(
  players: T[],
): T[] {
  return [...players].sort((a, b) => {
    if (a.finished !== b.finished) return a.finished ? -1 : 1;
    if (a.finished && b.finished && a.finish_time !== b.finish_time) {
      return (a.finish_time ?? 999999) - (b.finish_time ?? 999999);
    }
    if (a.wpm !== b.wpm) return b.wpm - a.wpm;
    if (a.accuracy !== b.accuracy) return b.accuracy - a.accuracy;
    return b.score - a.score;
  });
}
