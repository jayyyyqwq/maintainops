import type { ReactNode } from "react";

/**
 * Minimal, safe markdown renderer for the LLM explanation: headings, ordered/unordered
 * lists, paragraphs and **bold**. Builds React elements only (no innerHTML).
 */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  );
}

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flush = () => {
    if (!list) return;
    const items = list.items.map((item, i) => <li key={i}>{inline(item)}</li>);
    blocks.push(list.ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>);
    list = null;
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    const ordered = line.match(/^\d+[.)]\s+(.*)$/);
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    if (heading) {
      flush();
      blocks.push(<h4 key={blocks.length}>{inline(heading[1])}</h4>);
    } else if (ordered || bullet) {
      const isOrdered = Boolean(ordered);
      if (list && list.ordered !== isOrdered) flush();
      list ??= { ordered: isOrdered, items: [] };
      list.items.push((ordered ?? bullet)![1]);
    } else if (line) {
      flush();
      blocks.push(<p key={blocks.length}>{inline(line)}</p>);
    } else {
      flush();
    }
  }
  flush();
  return <div className="markdown">{blocks}</div>;
}
