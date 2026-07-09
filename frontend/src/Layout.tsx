import { useEffect, useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { get } from "./api";
import { useAuth } from "./auth";
import Assistant from "./screens/Assistant";

/** App-wide banner shown when the Google Health refresh token has expired, with a
 * one-tap reconnect. Re-checks on the "gh-status-changed" event that the daily
 * note fires after each background sync, so it appears as soon as a sync fails. */
function ReconnectBanner() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const check = () =>
      get<{ needs_reconnect?: boolean }>("/settings/google-health")
        .then((s) => setShow(!!s.needs_reconnect))
        .catch(() => {});
    check();
    window.addEventListener("gh-status-changed", check);
    return () => window.removeEventListener("gh-status-changed", check);
  }, []);
  if (!show) return null;
  return (
    <div className="flex items-center justify-between gap-3 bg-amber-600 px-4 py-2 text-sm text-white">
      <span>Google Health disconnected — steps &amp; sleep aren't syncing.</span>
      <button
        onClick={() => {
          window.location.href = "/api/v1/settings/google-health/authorize";
        }}
        className="shrink-0 rounded bg-white/20 px-3 py-1 font-semibold hover:bg-white/30"
      >
        Reconnect
      </button>
    </div>
  );
}

export default function Layout() {
  const nav = useNavigate();
  const { logout, caps } = useAuth();
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* Only relevant to users with the Google Health integration enabled. */}
      {caps.hasHealthIntegrations && <ReconnectBanner />}
      <header className="flex items-center gap-2 border-b border-slate-700 p-3">
        <button
          onClick={() => nav("/")}
          className="rounded bg-slate-800 px-3 py-1 text-sm hover:bg-slate-700"
        >
          🏠 Home
        </button>
        <button
          onClick={() => nav(-1)}
          className="rounded bg-slate-800 px-3 py-1 text-sm hover:bg-slate-700"
        >
          ← Back
        </button>
        <span className="flex-1" />
        <button
          onClick={logout}
          className="rounded px-3 py-1 text-sm text-slate-400 hover:text-slate-100"
        >
          Log out
        </button>
      </header>
      <main className="mx-auto max-w-xl p-4">
        <Outlet />
      </main>
      <Assistant />
    </div>
  );
}
