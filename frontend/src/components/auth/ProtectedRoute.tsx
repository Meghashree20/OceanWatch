import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/lib/authContext';

export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return (
      <div className="container-page flex min-h-[50vh] items-center justify-center">
        <p className="text-sm font-medium text-ocean-600">Restoring your OceanWatch session…</p>
      </div>
    );
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
