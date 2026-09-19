import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, TOKEN_KEY } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anonymous

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) { setUser(false); return; }
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => { localStorage.removeItem(TOKEN_KEY); setUser(false); });
  }, []);

  const applyAuth = useCallback((data) => {
    localStorage.setItem(TOKEN_KEY, data.token);
    setUser(data.user);
  }, []);

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    applyAuth(data);
  }, [applyAuth]);

  const register = useCallback(async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    applyAuth(data);
  }, [applyAuth]);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem(TOKEN_KEY);
    setUser(false);
  }, []);

  return <AuthContext.Provider value={{ user, login, register, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
