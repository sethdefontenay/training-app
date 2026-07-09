/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { get, getToken, post, setToken } from "./api";

export type Capabilities = {
  isAdmin: boolean;
  hasDiabetes: boolean;
  hasHealthIntegrations: boolean;
  hasCheckins: boolean;
};

// Fail-closed default: no capabilities until /auth/me confirms them, so gated screens
// (T1D, health integrations, check-ins) never flash for a user who shouldn't see them.
const NO_CAPS: Capabilities = {
  isAdmin: false,
  hasDiabetes: false,
  hasHealthIntegrations: false,
  hasCheckins: false,
};

type MeResponse = {
  is_admin: boolean;
  has_diabetes: boolean;
  has_health_integrations: boolean;
  has_checkins: boolean;
};

type AuthCtx = {
  isAuthed: boolean;
  ready: boolean; // /auth/me resolved (capabilities known)
  caps: Capabilities;
  readOnly: boolean; // retained for screens; always false since the trainer role was retired
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, code: string) => Promise<void>;
  logout: () => void;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthed, setAuthed] = useState(() => !!getToken());
  const [ready, setReady] = useState(false);
  const [caps, setCaps] = useState<Capabilities>(NO_CAPS);

  // Resolve capabilities whenever we become authed. Fail CLOSED: if /auth/me can't be
  // read, keep NO_CAPS so no gated surface is shown. The backend is the real boundary;
  // this only drives which screens the UI offers.
  useEffect(() => {
    if (!isAuthed) return; // logout() already resets ready/caps; nothing to fetch
    get<MeResponse>("/auth/me")
      .then((m) =>
        setCaps({
          isAdmin: !!m.is_admin,
          hasDiabetes: !!m.has_diabetes,
          hasHealthIntegrations: !!m.has_health_integrations,
          hasCheckins: !!m.has_checkins,
        }),
      )
      .catch(() => setCaps(NO_CAPS))
      .finally(() => setReady(true));
  }, [isAuthed]);

  const login = async (email: string, password: string) => {
    const r = await post<{ access_token: string }>("/auth/login", { email, password });
    setToken(r.access_token);
    setAuthed(true);
  };
  const register = async (email: string, password: string, code: string) => {
    const r = await post<{ access_token: string }>("/auth/register", { email, password, code });
    setToken(r.access_token);
    setAuthed(true);
  };
  const logout = () => {
    setToken(null);
    setAuthed(false);
    setCaps(NO_CAPS);
    setReady(false);
  };

  return (
    <Ctx.Provider
      value={{ isAuthed, ready, caps, readOnly: false, login, register, logout }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside provider");
  return c;
}
