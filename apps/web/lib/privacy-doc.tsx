import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { ReactNode } from "react";

export function loadPrivacyMarkdown(): string {
  return readFileSync(join(process.cwd(), "content/PRIVACY.md"), "utf8");
}

function inline(text: string, key: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let index = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > last) nodes.push(text.slice(last, start));
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push(<strong key={`${key}-${index}`}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("`")) {
      nodes.push(
        <code key={`${key}-${index}`} className="font-mono text-sm">
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      const linked = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      const label = linked?.[1] ?? token;
      const href = linked?.[2] ?? "";
      const safe = href.startsWith("https://") || href.startsWith("http://") || href.startsWith("/");
      nodes.push(
        safe ? (
          <a key={`${key}-${index}`} href={href} className="underline">
            {label}
          </a>
        ) : (
          label
        ),
      );
    }
    last = start + token.length;
    index += 1;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function PrivacyDocument({ markdown }: { markdown: string }) {
  const blocks: ReactNode[] = [];
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  let index = 0;
  let block = 0;

  function takeParagraph(start: number): [ReactNode, number] {
    const parts: string[] = [];
    let cursor = start;
    while (cursor < lines.length && lines[cursor].trim() !== "") {
      if (/^#{1,3} /.test(lines[cursor]) || lines[cursor].startsWith("|") || lines[cursor].startsWith("- ")) break;
      parts.push(lines[cursor]);
      cursor += 1;
    }
    return [
      <p key={`p-${block}`} className="mt-4 text-base leading-[26px]">
        {inline(parts.join(" "), `p-${block}`)}
      </p>,
      cursor,
    ];
  }

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith("# ")) {
      blocks.push(
        <h1 key={`h-${block}`} className="text-3xl">
          {line.slice(2)}
        </h1>,
      );
      index += 1;
    } else if (line.startsWith("## ")) {
      blocks.push(
        <h2 key={`h-${block}`} className="mt-10 text-2xl">
          {line.slice(3)}
        </h2>,
      );
      index += 1;
    } else if (line.startsWith("### ")) {
      blocks.push(
        <h3 key={`h-${block}`} className="mt-8 text-xl">
          {line.slice(4)}
        </h3>,
      );
      index += 1;
    } else if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (index < lines.length && lines[index].startsWith("|")) {
        const cells = lines[index]
          .split("|")
          .slice(1, -1)
          .map((cell) => cell.trim());
        if (!cells.every((cell) => /^:?-+:?$/.test(cell))) rows.push(cells);
        index += 1;
      }
      const [head, ...body] = rows;
      blocks.push(
        <div key={`t-${block}`} className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            {head ? (
              <thead>
                <tr>
                  {head.map((cell, cellIndex) => (
                    <th key={cellIndex} className="border-b border-[color:var(--line)] px-2 py-2 font-medium">
                      {inline(cell, `th-${block}-${cellIndex}`)}
                    </th>
                  ))}
                </tr>
              </thead>
            ) : null}
            <tbody>
              {body.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="border-b border-[color:var(--line-subtle)] px-2 py-2 align-top">
                      {inline(cell, `td-${block}-${rowIndex}-${cellIndex}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
    } else if (line.startsWith("- ")) {
      const items: string[] = [];
      while (index < lines.length && lines[index].startsWith("- ")) {
        items.push(lines[index].slice(2));
        index += 1;
      }
      blocks.push(
        <ul key={`u-${block}`} className="mt-4 list-disc space-y-2 pl-5 text-base leading-[26px]">
          {items.map((item, itemIndex) => (
            <li key={itemIndex}>{inline(item, `li-${block}-${itemIndex}`)}</li>
          ))}
        </ul>,
      );
    } else {
      const [node, next] = takeParagraph(index);
      blocks.push(node);
      index = next === index ? index + 1 : next;
    }
    block += 1;
  }

  return <article className="privacy-doc">{blocks}</article>;
}
