/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, type ReactNode } from "react";
import { getToken, post, setToken } from "./api";

type AuthCtx = {
  isAuthed: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthed, setAuthed] = useState(() => !!getToken());

  const login = async (email: string, password: string) => {
    const r = await post<{ access_token: string }>("/auth/login", { email, password });
    setToken(r.access_token);
    setAuthed(true);
  };
  const logout = () => {
    setToken(null);
    setAuthed(false);
  };

  return <Ctx.Provider value={{ isAuthed, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside provider");
  return c;
}
