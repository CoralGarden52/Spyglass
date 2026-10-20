import { useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, useNavigate } from 'react-router';
import { motion } from 'framer-motion';
import { ArrowRight, Compass, LoaderCircle, ShieldCheck } from 'lucide-react';
import { login, register } from '../services/auth';
import { ApiError } from '../services/client';
import { identityKey, resetPrivateState, useIdentity } from '../features/auth/session';

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const registering = mode === 'register';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const identity = useIdentity();
  const mutation = useMutation({
    mutationFn: () =>
      registering
        ? register({ email, password, display_name: name.trim() })
        : login({ email, password }),
    onSuccess: (data) => {
      resetPrivateState(queryClient);
      queryClient.clear();
      queryClient.setQueryData(identityKey, data);
      navigate('/', { replace: true });
    },
  });
  if (identity.data) return <Navigate to="/" replace />;
  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }
  return (
    <main className="auth-page">
      <Link className="auth-brand brand" to="/login">
        <Compass size={32} />
        <span>Spyglass</span>
      </Link>
      <motion.section
        className="auth-card"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        key={mode}
      >
        <span className="auth-emblem">
          <Compass size={30} />
        </span>
        <h1>{registering ? '创建你的研究工作空间' : '欢迎回到 Spyglass'}</h1>
        <p className="auth-subtitle">
          {registering
            ? '注册后，为你建立独立的个人工作空间。'
            : '登录你的工作空间，继续探索竞争格局。'}
        </p>
        <form onSubmit={submit} className="auth-form">
          {registering && (
            <label>
              姓名
              <input
                name="name"
                autoComplete="name"
                required
                maxLength={80}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="如何称呼你"
              />
            </label>
          )}
          <label>
            邮箱
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
              maxLength={320}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
            />
          </label>
          <label>
            密码
            <input
              name="password"
              type="password"
              autoComplete={registering ? 'new-password' : 'current-password'}
              required
              minLength={registering ? 15 : 1}
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-describedby={registering ? 'password-help' : undefined}
              placeholder={registering ? '至少 15 个字符，可使用长口令' : '输入你的密码'}
            />
          </label>
          {registering && (
            <small id="password-help" className="muted">
              15–128 个字符，支持空格和中文；建议使用独特的长口令。
            </small>
          )}
          {mutation.error && (
            <div className="form-error" role="alert">
              {mutation.error instanceof ApiError ? mutation.error.message : '网络连接失败，请重试'}
            </div>
          )}
          <button
            className="primary-button"
            type="submit"
            disabled={mutation.isPending || (registering && !name.trim())}
          >
            {mutation.isPending ? (
              <>
                <LoaderCircle size={17} className="animate-spin" />
                正在处理…
              </>
            ) : (
              <>
                {registering ? '注册并进入工作台' : '登录'}
                <ArrowRight size={17} />
              </>
            )}
          </button>
        </form>
        <p className="auth-switch">
          {registering ? '已有账户？' : '还没有账户？'}{' '}
          <Link to={registering ? '/login' : '/register'}>
            {registering ? '立即登录' : '创建账户'}
          </Link>
        </p>
        <div className="auth-security">
          <ShieldCheck size={15} />
          个人工作空间的数据仅对你开放
        </div>
      </motion.section>
      <p className="auth-footer">Spyglass · 真实来源，清晰判断</p>
    </main>
  );
}
