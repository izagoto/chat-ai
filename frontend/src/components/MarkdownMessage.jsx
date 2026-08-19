import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function ExternalLink({ href, children }) {
  const safe = typeof href === "string" && /^(https?:|mailto:)/i.test(href);
  if (!safe) return <span>{children}</span>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

export function MarkdownMessage({ content }) {
  if (!content) return null;
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ExternalLink,
        table: ({ children }) => (
          <div className="md-table-wrap">
            <table>{children}</table>
          </div>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
