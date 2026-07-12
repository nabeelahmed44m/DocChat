/**
 * Progressive parsers for the raw text streamed by the backend's
 * /summary/stream and /keypoints/stream endpoints. They mirror the backend's
 * parse logic (SUMMARY:/BULLET POINTS: and KEY POINTS:/IMPORTANT TERMS:
 * sections) but are safe to call on partial text, so panels can render
 * content while chunks are still arriving.
 */

export type ParsedSummary = { summary: string; bulletPoints: string[] };
export type ParsedKeypoints = { points: string[]; keyphrases: string[] };

const BULLET_PREFIX = /^[•\-\*]\s*/;
const POINT_PREFIX = /^[•\-\*\d\.:\)]+\s*/;

export function parseSummaryText(text: string): ParsedSummary {
  let summary = '';
  const bulletPoints: string[] = [];

  if (text.includes('SUMMARY:')) {
    const after = text.split('SUMMARY:', 2)[1] ?? '';
    summary = (after.includes('BULLET POINTS:')
      ? after.split('BULLET POINTS:')[0]
      : after
    ).trim();
  } else {
    // Model hasn't emitted the SUMMARY: header yet — show what we have.
    summary = text.trim();
  }

  if (text.includes('BULLET POINTS:')) {
    const section = text.split('BULLET POINTS:', 2)[1] ?? '';
    for (const raw of section.split('\n')) {
      const line = raw.trim();
      if (line && '•-*'.includes(line[0])) {
        const pt = line.replace(BULLET_PREFIX, '').trim();
        if (pt) bulletPoints.push(pt);
      }
    }
  }

  return { summary, bulletPoints };
}

export function parseKeypointsText(text: string): ParsedKeypoints {
  const points: string[] = [];
  let keyphrases: string[] = [];

  if (text.includes('KEY POINTS:')) {
    let section = text.split('KEY POINTS:', 2)[1] ?? '';
    if (section.includes('IMPORTANT TERMS:')) {
      section = section.split('IMPORTANT TERMS:')[0];
    }
    for (const raw of section.split('\n')) {
      const line = raw.trim();
      if (!line) continue;
      const numbered = /^\d/.test(line) && line.length > 2 && '.)'.includes(line[1]);
      if ('•-*'.includes(line[0]) || numbered) {
        const pt = line.replace(POINT_PREFIX, '').trim();
        if (pt) points.push(pt);
      }
    }
  }

  if (text.includes('IMPORTANT TERMS:')) {
    const section = (text.split('IMPORTANT TERMS:', 2)[1] ?? '').trim();
    const firstLine = section.split('\n').find((l) => l.trim());
    if (firstLine) {
      keyphrases = firstLine
        .split(',')
        .map((t) => t.trim().replace(/^\[|\]$/g, ''))
        .filter(Boolean);
    }
  }

  return { points, keyphrases };
}
