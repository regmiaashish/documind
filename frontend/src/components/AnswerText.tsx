/** Render readable paragraphs and lists without interpreting HTML from documents. */
export default function AnswerText({ text }: { text: string }) {
  return <div className="answer-text">{text.split(/\n\s*\n/).filter(Boolean).map((block, index) => {
    const lines = block.split('\n');
    const bullets = lines.every(line => /^\s*[-*•]\s+/.test(line));
    const numbered = lines.every(line => /^\s*\d+[.)]\s+/.test(line));
    if (bullets || numbered) {
      const items = lines.map((line, item) => <li key={item}>{line.replace(/^\s*(?:[-*•]|\d+[.)])\s+/, '')}</li>);
      return numbered ? <ol key={index}>{items}</ol> : <ul key={index}>{items}</ul>;
    }
    return <p key={index}>{block}</p>;
  })}</div>;
}
