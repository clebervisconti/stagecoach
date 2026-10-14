/** Observable-expression reports must not use emotion-inference words (SPEC §5, ADR-010). */
export const FORBIDDEN_EMOTION_TERMS = [
  "happy",
  "sad",
  "angry",
  "anxious",
  "fearful",
  "joyful",
  "frustrated",
  "excited",
  "nervous",
  "stress",
  "engagement",
  "authenticity",
  "feliz",
  "triste",
  "ansioso",
  "ansiosa",
  "raiva",
  "medo",
  "empolgado",
  "nervoso",
  "nervosa",
  "estresse",
  "engajamento",
  "autenticidade",
] as const;

const BOUNDARY = new RegExp(
  `\\b(${FORBIDDEN_EMOTION_TERMS.join("|")})\\b`,
  "i",
);

export function findForbiddenEmotionTerm(text: string): string | null {
  const match = BOUNDARY.exec(text);
  return match ? match[1] : null;
}

export function collectStrings(value: unknown, found: string[] = []): string[] {
  if (typeof value === "string") {
    found.push(value);
  } else if (Array.isArray(value)) {
    for (const item of value) collectStrings(item, found);
  } else if (value && typeof value === "object") {
    for (const item of Object.values(value)) collectStrings(item, found);
  }
  return found;
}
