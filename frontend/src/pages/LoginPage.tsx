import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useState, type FormEvent } from 'react';
import { AuthInput, AuthLayout, PasswordInput, SubmitButton } from '@/components/auth/AuthForm';
import { ApiClientError } from '@/lib/api/client';
import { useAuth } from '@/lib/authContext';

export function LoginPage() {
  const { login, status } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (status === 'authenticated') {
    return <RedirectToDestination />;
  }

  if (status === 'loading') {
    return (
      <AuthLayout
        title="Welcome back"
        description="Checking your OceanWatch session…"
        footer={<>New to OceanWatch? <Link className="font-semibold text-cyan-700 hover:text-cyan-600" to="/signup">Create an account</Link></>}
      >
        <div className="rounded-xl border border-ocean-200 bg-ocean-50 px-4 py-3 text-sm text-ocean-700">
          Restoring your secure session…
        </div>
      </AuthLayout>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    if (!email.trim() || !password) {
      setError('Enter your email and password to continue.');
      return;
    }
    setLoading(true);
    try {
      await login(email.trim(), password);
      navigate('/intelligence', { replace: true });
    } catch (requestError) {
      const message = requestError instanceof ApiClientError ? requestError.message : 'Unable to sign in. Please try again.';
      setError(message.includes('401') || message.toLowerCase().includes('invalid') || message.toLowerCase().includes('password')
        ? 'Invalid email or password.'
        : message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      description="Sign in to continue to your OceanWatch intelligence workspace."
      footer={<>New to OceanWatch? <Link className="font-semibold text-cyan-700 hover:text-cyan-600" to="/signup">Create an account</Link></>}
    >
      <form className="space-y-5" onSubmit={handleSubmit} noValidate>
        {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        <AuthInput label="Email address" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        <PasswordInput label="Password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
        <SubmitButton loading={loading}>Sign in</SubmitButton>
      </form>
    </AuthLayout>
  );
}

function RedirectToDestination() {
  return <Navigate to="/intelligence" replace />;
}
