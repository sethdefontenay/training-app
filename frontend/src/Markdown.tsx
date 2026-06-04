import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type CodeProps = ComponentPropsWithoutRef<"code"> & { className?: string };

/** Markdown → dark-themed React. Lists, tables, links, code all render properly. */
export default function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: (p) => <p className="my-1 leading-relaxed" {...p} />,
        ul: (p) => <ul className="my-1 list-disc space-y-0.5 pl-5" {...p} />,
        ol: (p) => <ol className="my-1 list-decimal space-y-0.5 pl-5" {...p} />,
        h1: (p) => <h1 className="mt-2 mb-1 text-base font-semibold" {...p} />,
        h2: (p) => <h2 className="mt-2 mb-1 text-base font-semibold" {...p} />,
        h3: (p) => <h3 className="mt-2 mb-1 font-semibold" {...p} />,
        strong: (p) => <strong className="font-semibold text-slate-100" {...p} />,
        a: ({ href, ...p }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sky-400 underline underline-offset-2 hover:text-sky-300"
            {...p}
          />
        ),
        blockquote: (p) => (
          <blockquote className="my-1 border-l-2 border-slate-600 pl-3 text-slate-300" {...p} />
        ),
        table: (p) => (
          <div className="my-2 overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs" {...p} />
          </div>
        ),
        th: (p) => (
          <th className="border border-slate-600 bg-slate-800 px-2 py-1 font-semibold" {...p} />
        ),
        td: (p) => <td className="border border-slate-700 px-2 py-1" {...p} />,
        pre: (p) => (
          <pre className="my-2 overflow-x-auto rounded bg-slate-950 p-2 text-xs" {...p} />
        ),
        code: ({ className, ...p }: CodeProps) =>
          className?.startsWith("language-") ? (
            <code className={className} {...p} />
          ) : (
            <code className="rounded bg-slate-700 px-1 py-0.5 text-xs" {...p} />
          ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
