import { useEffect, useState } from "react";
import { CHANGELOG, CURRENT_VERSION } from "./changelog";

const KEY = "seen_changelog_version";

/** Shows the latest release notes once, the first time a *returning* user opens the app
 * after the version advances. Brand-new users (no stored version) are seeded silently so
 * they never see a "what's new" for changes that predate them. */
export default function ChangelogModal() {
  // Decide at mount (lazy initializer, not a setState-in-effect): show only when a version
  // was previously stored and it differs from the current one.
  const [show, setShow] = useState(() => {
    const seen = localStorage.getItem(KEY);
    return seen !== null && seen !== CURRENT_VERSION;
  });

  // Seed a first-time user silently so the modal is reserved for genuine updates.
  useEffect(() => {
    if (localStorage.getItem(KEY) === null) localStorage.setItem(KEY, CURRENT_VERSION);
  }, []);

  if (!show) return null;
  const latest = CHANGELOG[0];

  const dismiss = () => {
    localStorage.setItem(KEY, CURRENT_VERSION);
    setShow(false);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-700 bg-slate-800 p-5 shadow-2xl">
        <h2 className="text-lg font-bold">What&rsquo;s new</h2>
        <p className="mb-3 text-xs text-slate-400">
          v{latest.version} &middot; {latest.date}
        </p>
        <ul className="space-y-2 text-sm">
          {latest.changes.map((c, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-emerald-400">•</span>
              <span>{c}</span>
            </li>
          ))}
        </ul>
        <button
          onClick={dismiss}
          className="mt-5 w-full rounded bg-emerald-600 py-2 font-semibold hover:bg-emerald-500"
        >
          Got it
        </button>
      </div>
    </div>
  );
}
