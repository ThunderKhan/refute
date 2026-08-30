import ReactMarkdown from "react-markdown";

export default function MarkdownBlock({ children }: { children: string }) {
  return <div className="markdown-block"><ReactMarkdown>{children}</ReactMarkdown></div>;
}
