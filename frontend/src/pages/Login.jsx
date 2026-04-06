import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api from '../services/api';

const Login = () => {
  const isDev = import.meta.env.MODE === 'development';
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [remember, setRemember] = useState(false);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    if (searchParams.get('logout') === 'success') {
      setMsg('Logged out successfully');
    }
  }, [searchParams]);

  useEffect(() => {
    document.title = 'Login — LeadStream AI';
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const loginData = {
        username: username,
        password: password,
        remember: remember ? 'on' : ''
      };

      const response = await api.post('/api/auth/login', loginData);

      if (response.status === 200) {
        const { access_token, user } = response.data;
        if (access_token) {
          localStorage.setItem('token', access_token);
        }
        if (user) {
          localStorage.setItem('user', JSON.stringify(user));
        }

        setMsg('Login Successful! Redirecting to dashboard...');
        setTimeout(() => {
          navigate('/dashboard');
        }, 1500);
      }
    } catch (err) {
      if (err.response && err.response.status === 401) {
        setError('Invalid username or password');
      } else {
        setError(err?.response?.data?.detail || 'Login failed. Please check your credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-5 relative z-10">
      <div className="w-full max-w-[420px] bg-[#111a2e]/85 backdrop-blur-[24px] border border-white/10 rounded-2xl py-10 px-9 shadow-[0_25px_60px_rgba(0,0,0,0.5),inset_0_0_0_1px_rgba(255,255,255,0.04)] animate-[cardSlideIn_0.6s_cubic-bezier(0.16,1,0.3,1)]">

        {/* Brand */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-500 inline-flex items-center justify-center text-[26px] mb-4 shadow-[0_8px_24px_rgba(59,130,246,0.3)] animate-[iconGlow_3s_ease-in-out_infinite]">
            📊
          </div>
          <h1 className="text-[22px] font-bold text-[#f0f2f7] tracking-tight mb-1">LeadStream AI</h1>
          <p className="text-[13px] text-[#7a8194]">Sign in to your dashboard</p>
        </div>

        {/* Alerts */}
        {error && (
          <div className="p-2.5 px-3.5 rounded-lg text-xs font-medium mb-5 flex items-center gap-2 bg-red-500/10 text-red-400 border border-red-500/20 animate-[alertSlide_0.3s_ease]">
            <span>⚠️</span> {error}
          </div>
        )}
        {msg && (
          <div className="p-2.5 px-3.5 rounded-lg text-xs font-medium mb-5 flex items-center gap-2 bg-green-500/10 text-green-400 border border-green-500/20 animate-[alertSlide_0.3s_ease]">
            <span>✓</span> {msg}
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleLogin}>
          <div className="mb-5 group">
            <label htmlFor="username" className="block text-xs font-semibold text-[#9ca3b4] mb-2 tracking-[0.3px]">
              Username
            </label>
            <div className="relative focus-within:text-blue-500 transition-transform duration-200 group-focus-within:translate-x-[2px]">
              <input
                type="text"
                id="username"
                className="w-full py-3 pr-3.5 pl-11 bg-[#0c1528]/80 border border-white/10 rounded-xl text-[#f0f2f7] text-sm transition-all focus:border-blue-500 focus:ring-[3px] focus:ring-blue-500/15 focus:bg-[#0c1528] outline-none placeholder:text-[#3a4058]"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                autoFocus
              />
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-base text-[#4a5068] pointer-events-none transition-colors">
                👤
              </span>
            </div>
          </div>

          <div className="mb-5 group">
            <label htmlFor="password" className="block text-xs font-semibold text-[#9ca3b4] mb-2 tracking-[0.3px]">
              Password
            </label>
            <div className="relative focus-within:text-blue-500 transition-transform duration-200 group-focus-within:translate-x-[2px]">
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                className="w-full py-3 pr-3.5 pl-11 bg-[#0c1528]/80 border border-white/10 rounded-xl text-[#f0f2f7] text-sm transition-all focus:border-blue-500 focus:ring-[3px] focus:ring-blue-500/15 focus:bg-[#0c1528] outline-none placeholder:text-[#3a4058]"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-base text-[#4a5068] pointer-events-none transition-colors">
                🔒
              </span>
              <button
                type="button"
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#4a5068] hover:text-[#7a8194] text-base p-1 transition-colors"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between mb-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <div className="relative flex items-center">
                <input
                  type="checkbox"
                  className="peer appearance-none w-4 h-4 border-[1.5px] border-white/15 rounded bg-[#0c1528]/80 cursor-pointer transition-all checked:bg-blue-500 checked:border-blue-500 focus:outline-none"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-white text-[11px] font-bold opacity-0 peer-checked:opacity-100 pointer-events-none">
                  ✓
                </span>
              </div>
              <span className="text-xs text-[#7a8194] select-none">Remember me</span>
            </label>
            <button
              type="button"
              className="text-xs text-blue-500 hover:text-blue-400 font-medium transition-colors"
              onClick={() => alert('Contact admin')}
            >
              Forgot password?
            </button>
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`w-full relative py-[13px] px-5 bg-gradient-to-br from-blue-500 to-indigo-500 text-white rounded-xl text-sm font-semibold tracking-[0.3px] transition-all overflow-hidden ${loading ? 'opacity-90' : 'hover:-translate-y-[1px] hover:shadow-[0_8px_24px_rgba(59,130,246,0.35)] active:translate-y-0'
              }`}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-blue-400 to-indigo-400 opacity-0 hover:opacity-100 transition-opacity"></div>
            <span className={`relative z-10 flex items-center justify-center gap-2 ${loading ? 'opacity-50' : ''}`}>
              {loading ? 'Signing In...' : 'Sign In →'}
            </span>
          </button>

          <div className="text-center mt-6">
            <button 
              type="button"
              onClick={() => navigate('/admin')}
              className="text-[10px] font-black text-slate-600 uppercase tracking-[2px] transition-all hover:text-blue-500 hover:tracking-[3px]"
            >
              🔒 Staff Entry Portal
            </button>
          </div>
        </form>

        <div className="text-center mt-6 pt-5 border-t border-white/5">
          <p className="text-xs text-[#4a5068]">Secured with enterprise-grade encryption</p>
        </div>

        <div className="flex items-center justify-center gap-1.5 mt-6 pt-4">
          <span>🔐</span>
          <span className="text-[11px] text-[#3a4058]">256-bit SSL Protected</span>
        </div>
      </div>
    </div>
  );
};

export default Login;