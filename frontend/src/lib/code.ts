export interface ParsedReply {
  /** Reply text with every fenced code block removed. */
  prose: string;
  /** Contents of the last fenced block (the program), if any. */
  code: string;
  /** Language tag of that block, normalised to an editor language. */
  lang: string | null;
  /** False while the closing fence has not streamed in yet. */
  complete: boolean;
  blocks: number;
}

const ALIASES: Record<string, string> = {
  py: "python", python3: "python", js: "javascript", node: "javascript", jsx: "react",
  ts: "typescript", tsx: "typescript", "c++": "cpp", cc: "cpp", sh: "bash", shell: "bash",
  ps1: "powershell", pwsh: "powershell",
};

export function normalizeLang(tag: string): string {
  const t = tag.trim().toLowerCase();
  return ALIASES[t] ?? t;
}

/** Splits a (possibly still streaming) markdown reply into prose and code. */
export function parseReply(raw: string): ParsedReply {
  const re = /```([\w+#.-]*)[^\n]*\n([\s\S]*?)(```|$)/g;
  let code = "";
  let lang: string | null = null;
  let complete = true;
  let blocks = 0;
  const prose = raw
    .replace(re, (_m, tag: string, body: string, close: string) => {
      blocks++;
      code = body.replace(/\n$/, "");
      lang = tag ? normalizeLang(tag) : lang;
      complete = close === "```";
      return "";
    })
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return { prose, code, lang, complete, blocks };
}
