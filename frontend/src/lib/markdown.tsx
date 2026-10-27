import { Fragment, type ReactNode } from "react";
import { normalizeLang } from "./code";

export interface CodeBlockInfo {
  code: string;
  lang: string;
  complete: boolean;
}

type Block =
  | { type: "code"; info: CodeBlockInfo }
  | { type: "heading"; level: number; text: string }
  | { type: "list"; ordered: boolean; start: number; items: string[] }
  | { type: "options"; items: { letter: string; text: string }[] }
  | { type: "quote"; text: string }
  | { type: "rule" }
  | { type: "table"; header: string[]; rows: string[][] }
  | { type: "paragraph"; text: string };

function splitRow(line: string): string[] {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

const OPTION_LINE = /^\s*(?:(?:[-*]|\d+\.)\s+)?[\[(][A-Da-d][\])]/;

function parseBlocks(src: string): Block[] {
  const blocks: Block[] = [];
  const lines = src.split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const fence = line.match(/^\s*```([\w+#.-]*)/);
    if (fence) {
      const body: string[] = [];
      i++;
      let complete = false;
      while (i < lines.length) {
        if (/^\s*```\s*$/.test(lines[i])) {
          complete = true;
          i++;
          break;
        }
        body.push(lines[i]);
        i++;
      }
      blocks.push({ type: "code", info: { code: body.join("\n"), lang: normalizeLang(fence[1]), complete } });
      continue;
    }
    if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      blocks.push({ type: "rule" });
      i++;
      continue;
    }
    if (line.includes("|") && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(lines[i + 1])) {
      const header = splitRow(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        rows.push(splitRow(lines[i]));
        i++;
      }
      blocks.push({ type: "table", header, rows });
      continue;
    }
    if (/^\s*>/.test(line)) {
      const q: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) {
        q.push(lines[i].replace(/^\s*>\s?/, ""));
        i++;
      }
      blocks.push({ type: "quote", text: q.join("\n") });
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)/);
    if (heading) {
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2] });
      i++;
      continue;
    }
    const OPTION = /^\s*(?:(?:[-*]|\d+\.)\s+)?[\[(]([A-Da-d])[\])]\s*(.*)/;
    if (OPTION.test(line)) {
      const items: { letter: string; text: string }[] = [];
      while (i < lines.length) {
        const m = lines[i].match(OPTION);
        if (!m) break;
        items.push({ letter: m[1].toUpperCase(), text: m[2] });
        i++;
      }
      blocks.push({ type: "options", items });
      continue;
    }
    const list = line.match(/^\s*([-*]|\d+\.)\s+/);
    if (list) {
      const ordered = /\d/.test(list[1]);
      const start = ordered ? parseInt(list[1], 10) : 1;
      const items: string[] = [];
      while (i < lines.length) {
        const m = lines[i].match(/^\s*([-*]|\d+\.)\s+(.*)/);
        if (!m || OPTION.test(lines[i])) break;
        items.push(m[2]);
        i++;
      }
      blocks.push({ type: "list", ordered, start, items });
      continue;
    }
    if (!line.trim()) {
      i++;
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^\s*(```|#{1,4}\s|>|([-*]|\d+\.)\s)/.test(lines[i]) && !/^\s*(-{3,}|\*{3,})\s*$/.test(lines[i]) && !OPTION_LINE.test(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    blocks.push({ type: "paragraph", text: para.join("\n") });
  }
  return blocks;
}

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*|\[[^\]\n]+\]\([^)\s]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) out.push(<code key={k++}>{tok.slice(1, -1)}</code>);
    else if (tok.startsWith("[")) {
      const lm = tok.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      out.push(lm ? <a key={k++} href={lm[2]} target="_blank" rel="noreferrer">{lm[1]}</a> : tok);
    } else if (tok.startsWith("**")) out.push(<strong key={k++}>{tok.slice(2, -2)}</strong>);
    else out.push(<em key={k++}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Markdown({
  text,
  renderCode = (info) => (
    <pre className="md-code">
      <code>{info.code}</code>
    </pre>
  ),
}: {
  text: string;
  renderCode?: (info: CodeBlockInfo, index: number) => ReactNode;
}) {
  let codeIndex = 0;
  return (
    <div className="md">
      {parseBlocks(text).map((b, idx) => {
        switch (b.type) {
          case "code":
            return <Fragment key={idx}>{renderCode(b.info, codeIndex++)}</Fragment>;
          case "options":
            return (
              <div key={idx} className="md-options">
                {b.items.map((o, j) => (
                  <div key={j} className="md-option">
                    <span className="md-option-letter">{o.letter}</span>
                    <span>{inline(o.text)}</span>
                  </div>
                ))}
              </div>
            );
          case "rule":
            return <hr key={idx} />;
          case "quote":
            return <blockquote key={idx}>{inline(b.text)}</blockquote>;
          case "table":
            return (
              <div key={idx} className="md-table">
                <table>
                  <thead>
                    <tr>{b.header.map((h, j) => <th key={j}>{inline(h)}</th>)}</tr>
                  </thead>
                  <tbody>
                    {b.rows.map((row, j) => (
                      <tr key={j}>{row.map((c, k) => <td key={k}>{inline(c)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case "heading":
            return <p key={idx} className={`md-h md-h${b.level}`}>{inline(b.text)}</p>;
          case "list": {
            const Tag = b.ordered ? "ol" : "ul";
            return (
              <Tag key={idx} {...(b.ordered ? { start: b.start } : {})}>
                {b.items.map((it, j) => (
                  <li key={j}>{inline(it)}</li>
                ))}
              </Tag>
            );
          }
          default:
            return <p key={idx}>{inline(b.text)}</p>;
        }
      })}
    </div>
  );
}
