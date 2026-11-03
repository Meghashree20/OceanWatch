import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { oceanWatchApi, type AuthUser } from '@/lib/api/client';
import { AuthContext, type AuthStatus } from '@/lib/authContext';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');

  useEffect(() => {
    let active = true;
    oceanWatchApi.getCurrentUser()
      .then((currentUser) => {
        if (active) {
          setUser(currentUser);
          setStatus('authenticated');
        }
      })
      .catch(() => {
        if (active) {
          setUser(null);
          setStatus('unauthenticated');
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const session = await oceanWatchApi.login({ email, password });
    setUser(session.user);
    setStatus('authenticated');
    return session.user;
  }, []);

  const signup = useCallback(async (
    fullName: string,
    email: string,
    password: string,
    passwordConfirmation: string,
  ) => {
    await oceanWatchApi.signup({
      full_name: fullName,
      email,
      password,
      password_confirmation: passwordConfirmation,
    });
    const session = await oceanWatchApi.login({ email, password });
    setUser(session.user);
    setStatus('authenticated');
    return session.user;
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
    () => ({ user, status, login, signup, logout }),
    [user, status, login, signup, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
