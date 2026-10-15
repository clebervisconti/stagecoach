import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { parseSourcesMarkdown, referencesHref, sourceAnchor } from "./research-sources.ts";

const SAMPLE = `### Evaluation (S1–S2)
- **[S1]** Toastmasters International. https://example.com/s1
- **[S20]** Mehrabian 7-38-55 misuse. https://example.com/s20
`;

describe("research sources", () => {
  it("parses keys, anchors, and URLs", () => {
    const rows = parseSourcesMarkdown(SAMPLE);
    assert.deepEqual(
      rows.map((row) => row.key),
      ["S1", "S20"],
    );
    assert.equal(rows[1]?.anchor, "S20");
    assert.equal(rows[1]?.urls[0], "https://example.com/s20");
  });

  it("links category source keys to the References page", () => {
    assert.equal(sourceAnchor("[S20]"), "S20");
    assert.equal(referencesHref("S20"), "/research#S20");
    assert.equal(referencesHref("S20", "/pt-BR"), "/pt-BR/research#S20");
    assert.equal(referencesHref("heuristic"), "/research/myths");
  });
});
