import { lazy, Suspense, useRef, useState } from "react";
import { ApiError, post } from "../api";
import { youtubeIds } from "../youtube";

// Lazy so react-markdown (~45KB gzip) only loads when the chat is actually used.
const Markdown = lazy(() => import("../Markdown"));

type Msg = { role: "user" | "assistant"; content: string };

/** Floating assistant: a bottom-right button that opens a chat drawer. Mounted
 * once in the Layout so it's available (and keeps its conversation) on every screen. */
export default function Assistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const next = [...messages, { role: "user" as const, content: text }];
    setMessages(next);
    setInput("");
    setError(null);
    setBusy(true);
    try {
      const r = await post<{ reply: string; tools_used: string[] }>("/assistant/chat", {
        messages: next,
      });
      setMessages([...next, { role: "assistant", content: r.reply }]);
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 503
          ? "Assistant isn't configured yet (ANTHROPIC_API_KEY not set)."
          : "Something went wrong — try again.",
      );
    } finally {
      setBusy(false);
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Open assistant"
        className="fixed bottom-4 right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-sky-600 text-xl shadow-lg hover:bg-sky-500"
      >
        💬
      </button>
    );
  }

  return (
    <div className="fixed inset-x-4 bottom-4 z-50 flex max-h-[75vh] flex-col rounded-xl border border-slate-700 bg-slate-800 shadow-2xl sm:inset-x-auto sm:right-4 sm:w-96">
      <div className="flex items-center justify-between border-b border-slate-700 px-3 py-2">
        <span className="font-semibold">Ask the hub</span>
        <div className="flex gap-3 text-xs text-slate-400">
          {messages.length > 0 && (
            <button onClick={() => setMessages([])} className="hover:text-slate-200">
              clear
            </button>
          )}
          <button onClick={() => setOpen(false)} aria-label="Close assistant" className="hover:text-slate-200">
            ✕
          </button>
        </div>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400">
            Ask about your data — e.g. “how’s my glucose this week?”, “what’s my workout
            tomorrow?”, “log 4 sets of leg press at 45kg today”.
          </p>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="whitespace-pre-wrap rounded bg-slate-700 px-3 py-2 text-sm">
              {m.content}
            </div>
          ) : (
            <div key={i} className="rounded border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm">
              <Suspense fallback={<div className="whitespace-pre-wrap">{m.content}</div>}>
                <Markdown>{m.content}</Markdown>
              </Suspense>
              {youtubeIds(m.content).map((id) => (
                <iframe
                  key={id}
                  className="mt-2 aspect-video w-full rounded"
                  src={`https://www.youtube-nocookie.com/embed/${id}`}
                  title="YouTube video"
                  loading="lazy"
                  allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              ))}
            </div>
          ),
        )}
        {busy && <div className="px-3 py-2 text-sm text-slate-400">Thinking…</div>}
        {error && <div className="px-3 py-2 text-sm text-amber-300">{error}</div>}
        <div ref={endRef} />
      </div>

      <div className="flex gap-2 border-t border-slate-700 p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask a question…"
          disabled={busy}
          className="flex-1 rounded bg-slate-700 px-3 py-2 text-sm disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={busy || !input.trim()}
          className="rounded bg-sky-600 px-4 py-2 text-sm font-semibold disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
