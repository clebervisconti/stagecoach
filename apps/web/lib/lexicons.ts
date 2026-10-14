/** Appendix A filler/hedge/vague lists used only to label existing transcript words. */

export const LEXICONS = {
  en: {
    filler_sounds: ["um", "umm", "uh", "uhh", "er", "erm", "ah", "hmm", "mm"],
    filler_words: ["like", "basically", "actually", "literally", "so"],
    hedges: ["maybe", "probably", "just", "sorry"],
    vague: ["stuff", "things", "various"],
  },
  "pt-BR": {
    filler_sounds: ["éé", "ééé", "eh", "ehh", "ahn", "ãh", "hum", "hã", "uhm", "hmm"],
    filler_words: ["né", "tipo", "então", "aí", "assim", "basicamente"],
    hedges: ["talvez", "desculpa"],
    vague: ["coisas", "tal"],
  },
} as const;

export type HighlightKind =
  | "filler_sound"
  | "filler_word"
  | "hedge"
  | "vague"
  | "clt"
  | "core_message"
  | "pause";

export function normalizeToken(word: string): string {
  return word
    .trim()
    .replace(/^["'“”]+|["'“”.,!?;:]+$/g, "")
    .toLocaleLowerCase();
}

export function lexiconFor(language: string | null | undefined) {
  return language && language.toLowerCase().startsWith("pt") ? LEXICONS["pt-BR"] : LEXICONS.en;
}
