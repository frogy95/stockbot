"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost, apiGet, setToken, removeToken } from "@/lib/api";

interface User {
  username: string;
  trading_env: "paper" | "live";
}

interface AuthContextValue {
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
  login: (password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function parseJwtUser(token: string): User | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return { username: payload.sub ?? "admin", trading_env: payload.trading_env ?? "paper" };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    apiGet<User>("/api/v1/auth/me")
      .then((u) => { if (mounted) setUser(u); })
      .catch(() => { if (mounted) setUser(null); })
      .finally(() => { if (mounted) setIsLoading(false); });
    return () => { mounted = false; };
  }, []);

  async function login(password: string): Promise<boolean> {
    try {
      const { access_token } = await apiPost<{ access_token: string }>(
        "/api/v1/auth/login",
        { password }
      );
      setToken(access_token);
      setUser(parseJwtUser(access_token));
      return true;
    } catch {
      return false;
    }
  }

  function logout() {
    removeToken();
    setUser(null);
    router.push("/login");
  }

  return (
    <AuthContext.Provider
      value={{ isAuthenticated: !!user, user, isLoading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
