import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { LogOut, ShieldCheck } from 'lucide-react';
import { resetPrivateState, useIdentity } from '../features/auth/session';
import { logout } from '../services/auth';
import { ApiError } from '../services/client';

export function AccountSettings() {
  const { data } = useIdentity();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  async function signOut() {
    setPending(true);
    setError('');
    try {
      await logout();
    } catch (failure) {
      if (!(failure instanceof ApiError && failure.status === 401)) {
        setError('登出未完成，请检查网络后重试');
        setPending(false);
        return;
      }
    }
    resetPrivateState(queryClient);
    queryClient.clear();
    navigate('/login', { replace: true });
  }
  return (
    <main className="business-page">
      <div className="page-heading">
        <h1>账户与工作空间</h1>
        <p>管理当前账户与默认个人工作空间。</p>
      </div>
      <section className="account-panel">
        <ShieldCheck size={30} />
        <h2>个人账户</h2>
        <dl>
          <dt>姓名</dt>
          <dd>{data?.user.display_name}</dd>
          <dt>邮箱</dt>
          <dd>{data?.user.email}</dd>
          <dt>工作空间</dt>
          <dd>{data?.tenant.name}</dd>
          <dt>角色</dt>
          <dd>所有者</dd>
        </dl>
        <p className="muted">团队邀请、密码重置和邮箱验证尚未开放。</p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button
          className="outline-button logout-button"
          disabled={pending}
          onClick={() => void signOut()}
        >
          <LogOut size={17} />
          {pending ? '正在登出…' : '退出登录'}
        </button>
      </section>
    </main>
  );
}
