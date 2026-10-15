export type ResearchSource = {
  key: string;
  anchor: string;
  section: string;
  text: string;
  urls: string[];
};

const SOURCE_RE = /^\s*-\s+\*\*\[(S\d+)\]\*\*\s+(.+)$/;
const HEADING_RE = /^###\s+(.+)$/;
const URL_RE = /https?:\/\/[^\s)]+/g;

export function parseSourcesMarkdown(markdown: string): ResearchSource[] {
  const headings: { index: number; title: string }[] = [];
  const lines = markdown.split(/\r?\n/);
  const sources: ResearchSource[] = [];
  let offset = 0;
  for (const line of lines) {
    const heading = HEADING_RE.exec(line);
    if (heading) headings.push({ index: offset, title: heading[1].trim() });
    const match = SOURCE_RE.exec(line);
    if (match) {
      let section = "";
      for (const row of headings) {
        if (row.index <= offset) section = row.title;
        else break;
      }
      sources.push({
        key: match[1],
        anchor: match[1],
        section,
        text: match[2].trim(),
        urls: match[2].match(URL_RE) ?? [],
      });
    }
    offset += line.length + 1;
  }
  return sources;
}

export function sourceAnchor(key: string): string {
  const normalized = key.replace(/[\[\]]/g, "");
  return normalized.startsWith("S") ? normalized : `S${normalized}`;
}

export function referencesHref(key: string, prefix = ""): string {
  if (!key || key === "heuristic" || key === "H") return `${prefix}/research/myths`;
  return `${prefix}/research#${sourceAnchor(key)}`;
}

export const MYTHS = [
  { id: "no-73855", source: "S20" },
  { id: "no-emotion", source: "S29" },
  { id: "no-accent", source: "S54" },
  { id: "more-not-better", sources: ["S27", "S18"] },
  { id: "heuristics", source: null },
] as const;
