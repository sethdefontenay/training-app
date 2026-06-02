import { Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "./auth";

export default function Layout() {
  const nav = useNavigate();
  const { logout } = useAuth();
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
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
    </div>
  );
}
