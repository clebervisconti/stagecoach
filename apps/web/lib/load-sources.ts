import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseSourcesMarkdown, type ResearchSource } from "./research-sources";

export function loadSourcesFromRepo(): ResearchSource[] {
  const markdown = readFileSync(join(process.cwd(), "../../docs/research/sources.md"), "utf8");
  return parseSourcesMarkdown(markdown);
}
