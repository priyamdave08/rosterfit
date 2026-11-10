import type { ReactNode } from "react";

// Renders the memo's light markdown (paragraphs, **bold**, *italic*, # headings, - bullets) as
// React elements. Text is never injected as HTML, so model output can't add markup or scripts.

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    out.push(tok.startsWith("**") ? <strong key={`${key}-${i++}`}>{tok.slice(2, -2)}</strong> : <em key={`${key}-${i++}`}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function MemoText({ text }: { text: string }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return (
    <>
      {blocks.map((b, bi) => {
        const lines = b.split("\n").filter((l) => l.trim());
        if (!lines.length) return null;
        if (lines.every((l) => /^\s*[-*]\s+/.test(l))) {
          return (
            <ul key={bi} style={{ margin: "0 0 12px", paddingLeft: 20 }}>
              {lines.map((l, li) => (
                <li key={li}>{inline(l.replace(/^\s*[-*]\s+/, ""), `${bi}-${li}`)}</li>
              ))}
            </ul>
          );
        }
        const h = /^(#{1,3})\s+(.*)$/.exec(lines[0]);
        if (h && lines.length === 1) {
          return (
            <h3 key={bi} style={{ margin: "4px 0 8px" }}>
              {inline(h[2], `${bi}`)}
            </h3>
          );
        }
        return (
          <p key={bi} style={{ margin: "0 0 12px" }}>
            {lines.map((l, li) => (
              <span key={li}>
                {li > 0 && <br />}
                {inline(l, `${bi}-${li}`)}
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}
