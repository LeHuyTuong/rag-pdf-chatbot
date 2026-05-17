import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, register } from '../api/authApi';
import { useAuth } from '../providers/AuthProvider';
import ErrorState from '../../../shared/components/ErrorState';
import LoadingSpinner from '../../../shared/components/LoadingSpinner';
import { getErrorMessage } from '../../../shared/utils/errors';

export default function LoginPage() {
  const [email, setEmail] = useState('demo@example.com');
  const [password, setPassword] = useState('password');
  const [fullName, setFullName] = useState('Demo User');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const auth = useAuth();
  const nav = useNavigate();

  async function submit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const payload = isRegister ? { email, password, fullName } : { email, password };
      const response = isRegister ? await register(payload) : await login(payload);
      auth.login(response.token, response.user || { email, fullName });
      nav('/dashboard');
    } catch (err) {
      if (!err.response) {
        setError('Backend API is not running at http://localhost:8080. Please start the backend first.');
      } else if (err.response.status === 401 || err.response.status === 403) {
        setError("Invalid email or password. If you don't have an account, click Register.");
      } else {
        setError(getErrorMessage(err, 'Login failed.'));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md animate-fade-in">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 shadow-xl shadow-blue-200 mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4" />
              <path d="M12 8h.01" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-slate-800">RAG Chatbot</h1>
          <p className="text-slate-500 mt-1">Sign in to your account to continue</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-100 p-8">
          <div className="flex bg-slate-100 rounded-xl p-1 mb-6">
            <button className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all ${!isRegister ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`} onClick={() => { setIsRegister(false); setError(''); }}>
              Sign In
            </button>
            <button className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all ${isRegister ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`} onClick={() => { setIsRegister(true); setError(''); }}>
              Register
            </button>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {isRegister && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Full Name</label>
                <input className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all placeholder:text-slate-400" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Doe" required={isRegister} />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Email</label>
              <input className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all placeholder:text-slate-400" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" type="email" required />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
              <input className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all placeholder:text-slate-400" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" type="password" required />
            </div>

            <ErrorState message={error} />

            <button type="submit" disabled={loading} className="w-full py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-medium text-sm hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-blue-200 flex items-center justify-center gap-2">
              {loading && <LoadingSpinner />}
              {loading ? 'Processing...' : isRegister ? 'Create Account' : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">Secure authentication powered by JWT</p>
      </div>
    </div>
  );
}
