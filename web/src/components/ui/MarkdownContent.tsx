import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';

export interface MarkdownContentProps {
  source?: string | null;
  className?: string;
  onOpenLink?: (url: string) => void;
}

const EXTERNAL_URL_PATTERN = /^https?:\/\//i;

export default function MarkdownContent({
  source,
  className = '',
  onOpenLink,
}: MarkdownContentProps) {
  const content = source?.trim();

  if (!content) {
    return <p className={`markdown-content-empty ${className}`.trim()}>此版本沒有提供更新說明。</p>;
  }

  return (
    <div className={`markdown-content ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          // Release notes should have one compact heading hierarchy inside the About page.
          h1: ({ children }) => <h3>{children}</h3>,
          h2: ({ children }) => <h3>{children}</h3>,
          h3: ({ children }) => <h4>{children}</h4>,
          h4: ({ children }) => <h4>{children}</h4>,
          h5: ({ children }) => <h5>{children}</h5>,
          h6: ({ children }) => <h5>{children}</h5>,
          a: ({ href, children }) => {
            const safeHref = href || '#';
            const isExternal = EXTERNAL_URL_PATTERN.test(safeHref);

            const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
              if (!isExternal || !onOpenLink) return;
              event.preventDefault();
              onOpenLink(safeHref);
            };

            return (
              <a
                href={safeHref}
                target={isExternal ? '_blank' : undefined}
                rel={isExternal ? 'noreferrer' : undefined}
                onClick={handleClick}
              >
                {children}
              </a>
            );
          },
          // Remote images are intentionally omitted from release notes to prevent visual hijacking.
          img: () => null,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
