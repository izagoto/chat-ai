import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, clearSession, getStoredToken, getStoredUser, setUnauthorizedHandler, storeSession } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    setToken("");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setToken("");
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      const savedToken = getStoredToken();
      if (!savedToken) {
        if (!cancelled) setLoading(false);
        return;
      }

      try {
        const data = await api("/v1/auth/me");
        if (!cancelled) {
          setToken(savedToken);
          setUser(data.user || getStoredUser());
        }
      } catch {
        clearSession();
        if (!cancelled) {
          setToken("");
          setUser(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await api("/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    storeSession(data.token, data.user);
    setToken(data.token);
    setUser(data.user);
    return data.user;
  }, []);

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      isAuthenticated: Boolean(token && user),
      login,
      logout,
    }),
    [user, token, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
