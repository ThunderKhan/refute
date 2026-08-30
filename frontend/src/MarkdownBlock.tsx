import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownBlock({ children }: { children: string }) {
  return (
    <div className="markdown-block">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
