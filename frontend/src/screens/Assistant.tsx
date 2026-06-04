import { useRef, useState } from "react";
import { ApiError, post } from "../api";

type Msg = { role: "user" | "assistant"; content: string };

export default function Assistant() {
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

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-semibold">Ask the hub</span>
        {messages.length > 0 && (
          <button onClick={() => setMessages([])} className="text-xs text-slate-400 hover:text-slate-200">
            clear
          </button>
        )}
      </div>

      {messages.length === 0 && (
        <p className="mb-2 text-sm text-slate-400">
          Ask about your data — e.g. “how’s my glucose this week?”, “what’s my leg-press progress?”,
          “log 4 sets of leg press at 45kg today”.
        </p>
      )}

      <div className="max-h-80 space-y-2 overflow-y-auto">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`whitespace-pre-wrap rounded px-3 py-2 text-sm ${
              m.role === "user" ? "bg-slate-700" : "bg-slate-900/70 border border-slate-700"
            }`}
          >
            {m.content}
          </div>
        ))}
        {busy && <div className="px-3 py-2 text-sm text-slate-400">Thinking…</div>}
        {error && <div className="px-3 py-2 text-sm text-amber-300">{error}</div>}
        <div ref={endRef} />
      </div>

      <div className="mt-2 flex gap-2">
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
