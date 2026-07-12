/**
 * Smooth text-reveal pacing for streamed responses.
 *
 * Fast models (and cached replays) can deliver a whole response within one or
 * two network chunks, so rendering raw chunks looks like the text popped in
 * all at once. This buffer sits between the network stream and the UI: chunks
 * update a target, and a ~30fps timer reveals progressively longer prefixes.
 *
 * The reveal rate is adaptive — a fixed fraction of the remaining backlog per
 * frame — so it types steadily when keeping up with a live stream but clears
 * a large cached payload in about a second instead of crawling through it.
 */

export interface SmoothStream {
  /** Feed the accumulated text received so far. */
  push(textSoFar: string): void;
  /** Signal the network stream ended; resolves once the reveal catches up. */
  finish(finalText: string): Promise<string>;
  /** Stop immediately (error or unmount). Safe to call more than once. */
  cancel(): void;
}

const FRAME_MS = 33;
const CATCH_UP_FRACTION = 0.12;
const MIN_CHARS_PER_FRAME = 2;

export function createSmoothStream(
  onUpdate: (textSoFar: string) => void,
): SmoothStream {
  let target = '';
  let shown = 0;
  let finished = false;
  let cancelled = false;
  let timer: ReturnType<typeof setInterval> | null = null;
  let resolveDone: ((text: string) => void) | null = null;

  const stop = () => {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  };

  const tick = () => {
    if (shown < target.length) {
      const remaining = target.length - shown;
      const step = Math.max(MIN_CHARS_PER_FRAME, Math.ceil(remaining * CATCH_UP_FRACTION));
      shown = Math.min(target.length, shown + step);
      onUpdate(target.slice(0, shown));
    }
    if (finished && shown >= target.length) {
      stop();
      resolveDone?.(target);
      resolveDone = null;
    }
  };

  const start = () => {
    if (timer === null && !cancelled) timer = setInterval(tick, FRAME_MS);
  };

  return {
    push(textSoFar) {
      if (cancelled) return;
      target = textSoFar;
      start();
    },
    finish(finalText) {
      target = finalText;
      finished = true;
      if (cancelled || shown >= target.length) {
        stop();
        return Promise.resolve(target);
      }
      start();
      return new Promise((resolve) => {
        resolveDone = resolve;
      });
    },
    cancel() {
      cancelled = true;
      stop();
      resolveDone?.(target);
      resolveDone = null;
    },
  };
}
