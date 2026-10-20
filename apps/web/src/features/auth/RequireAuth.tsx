import { Navigate, Outlet } from 'react-router';
import { useIdentity } from './session';

export function RequireAuth() {
  const { data, isPending, error, refetch } = useIdentity();
  if (isPending)
    return (
      <main className="route-state" role="status">
        正在恢复登录状态…
      </main>
    );
  if (error)
    return (
      <main className="route-state" role="alert">
        <h1>暂时无法连接账户服务</h1>
        <p>请检查网络或稍后重试。</p>
        <button className="outline-button" onClick={() => void refetch()}>
          重新连接
        </button>
      </main>
    );
  if (!data) return <Navigate to="/login" replace />;
  return <Outlet />;
}
