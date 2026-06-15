/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { get, getToken, post, setToken } from "./api";

type Role = "owner" | "trainer";

type AuthCtx = {
  isAuthed: boolean;
  role: Role | null; // null while /auth/me is still resolving
  readOnly: boolean; // trainer logins are read-only everywhere except the assistant chat
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthed, setAuthed] = useState(() => !!getToken());
  const [role, setRole] = useState<Role | null>(null);

  // Resolve the role whenever we become authed. Fail CLOSED: if /auth/me can't be read
  // we assume the least-privileged (read-only) role rather than handing out the owner UI
  // on an unknown state. (The backend guard is the real boundary regardless; this only
  // drives UI gating.) logout() clears role; we don't reset it synchronously here to
  // avoid a cascading render.
  useEffect(() => {
    if (!isAuthed) return;
    get<{ role: Role }>("/auth/me")
      .then((m) => setRole(m.role === "owner" ? "owner" : "trainer"))
      .catch(() => setRole("trainer"));
  }, [isAuthed]);

  const login = async (email: string, password: string) => {
    const r = await post<{ access_token: string }>("/auth/login", { email, password });
    setToken(r.access_token);
    setAuthed(true);
  };
  const logout = () => {
    setToken(null);
    setAuthed(false);
    setRole(null);
  };

  return (
    <Ctx.Provider value={{ isAuthed, role, readOnly: role === "trainer", login, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside provider");
  return c;
}
