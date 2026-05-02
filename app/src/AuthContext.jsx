import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { api } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("astraios_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api.me()
      .then((u) => setUser(u))
      .catch(() => localStorage.removeItem("astraios_token"))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await api.login({ email, password });
    localStorage.setItem("astraios_token", data.access_token);
    const u = await api.me();
    setUser(u);
  }, []);

  const register = useCallback(async (email, password, name) => {
    const data = await api.register({ email, password, name });
    localStorage.setItem("astraios_token", data.access_token);
    const u = await api.me();
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("astraios_token");
    setUser(null);
  }, []);

  if (loading) return null;

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
