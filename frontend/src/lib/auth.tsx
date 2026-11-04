import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { oceanWatchApi, type AuthUser } from '@/lib/api/client';
import { AuthContext, type AuthStatus } from '@/lib/authContext';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');

  const restoreSession = useCallback(async () => {
    try {
      const currentUser = await oceanWatchApi.getCurrentUser();
      setUser(currentUser);
      setStatus('authenticated');
    } catch {
      setUser(null);
      setStatus('unauthenticated');
    }
  }, []);

  useEffect(() => {
    let active = true;

    void oceanWatchApi.getCurrentUser()
      .then((currentUser) => {
        if (!active) return;
        setUser(currentUser);
        setStatus('authenticated');
      })
      .catch(() => {
        if (!active) return;
        setUser(null);
        setStatus('unauthenticated');
      });

    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const session = await oceanWatchApi.login({ email, password });
    const currentUser = await oceanWatchApi.getCurrentUser();
    setUser(currentUser);
    setStatus('authenticated');
    return session.user ?? currentUser;
  }, []);

  const signup = useCallback(async (
    fullName: string,
    email: string,
    password: string,
    passwordConfirmation: string,
  ) => {
    const createdUser = await oceanWatchApi.signup({
      full_name: fullName,
      email,
      password,
      password_confirmation: passwordConfirmation,
    });
    setUser(null);
    setStatus('unauthenticated');
    return createdUser;
  }, []);

  const logout = useCallback(async () => {
    try {
      await oceanWatchApi.logout();
    } finally {
      setUser(null);
      setStatus('unauthenticated');
    }
  }, []);

  const value = useMemo(
    () => ({ user, status, login, signup, logout, refreshSession: restoreSession }),
    [user, status, login, signup, logout, restoreSession],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
