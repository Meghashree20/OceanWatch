import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useState, type FormEvent } from 'react';
import { AuthInput, AuthLayout, PasswordInput, SubmitButton } from '@/components/auth/AuthForm';
import { ApiClientError } from '@/lib/api/client';
import { useAuth } from '@/lib/authContext';

export function SignupPage() {
  const { signup, status } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (status === 'authenticated') {
    return <Navigate to="/intelligence" replace />;
  }

  if (status === 'loading') {
    return (
      <AuthLayout
        title="Create your account"
        description="Checking your OceanWatch session…"
        footer={<>Already have an account? <Link className="font-semibold text-cyan-700 hover:text-cyan-600" to="/login">Sign in</Link></>}
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
    if (!fullName.trim() || !email.trim() || !password || !confirmation) {
      setError('Complete all fields to create your account.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirmation) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await signup(fullName.trim(), email.trim(), password, confirmation);
      navigate('/login', { replace: true });
    } catch (requestError) {
      const message = requestError instanceof ApiClientError ? requestError.message : 'Unable to create your account. Please try again.';
      setError(message.toLowerCase().includes('409') || message.toLowerCase().includes('already') || message.toLowerCase().includes('exists')
        ? 'An account with this email already exists.'
        : message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      description="Join OceanWatch to explore marine pollution intelligence and evidence-led action."
      footer={<>Already have an account? <Link className="font-semibold text-cyan-700 hover:text-cyan-600" to="/login">Sign in</Link></>}
    >
      <form className="space-y-5" onSubmit={handleSubmit} noValidate>
        {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        <AuthInput label="Full name" autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} />
        <AuthInput label="Email address" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        <PasswordInput label="Password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} />
        <PasswordInput label="Confirm password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
        <SubmitButton loading={loading}>Create account</SubmitButton>
      </form>
    </AuthLayout>
  );
}
