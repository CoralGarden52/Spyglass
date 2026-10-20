import { useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router';
import { useIdentity } from '../features/auth/session';
import {
  Activity,
  Bell,
  BookOpen,
  CircleUserRound,
  Compass,
  FileChartColumn,
  Files,
  Home,
  Menu,
  Plus,
  Radar,
  Settings,
  Shapes,
  Upload,
  X,
} from 'lucide-react';

const navigation = [
  { name: '工作台', icon: Home },
  { name: '我的调研', icon: Files },
  { name: '竞品档案', icon: BookOpen },
  { name: '竞争情报', icon: Radar },
  { name: '报告中心', icon: FileChartColumn },
  { name: '技能中心', icon: Shapes },
  { name: '运行追踪', icon: Activity },
];

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { data } = useIdentity();
  const location = useLocation();
  const pageTitle = location.pathname.startsWith('/research')
    ? '我的调研'
    : location.pathname === '/settings'
      ? '账户与工作空间'
      : '工作台';
  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? 'is-open' : ''}`} aria-label="全局侧边栏">
        <Link to="/" className="brand" onClick={() => setMenuOpen(false)}>
          <Compass size={32} strokeWidth={2.4} />
          <span>Spyglass</span>
        </Link>
        <button
          className="icon-button close-menu"
          aria-label="关闭导航"
          onClick={() => setMenuOpen(false)}
        >
          <X size={20} />
        </button>
        <nav aria-label="主导航">
          {navigation.map(({ name, icon: Icon }, index) =>
            index <= 1 ? (
              <NavLink
                to={index === 0 ? '/' : '/research'}
                end={index === 0}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                key={name}
                onClick={() => setMenuOpen(false)}
              >
                <Icon size={19} />
                {name}
              </NavLink>
            ) : (
              <div className="nav-disabled" key={name}>
                <button
                  className="nav-item"
                  disabled
                  title="后续切片开放"
                  aria-describedby="navigation-note"
                >
                  <Icon size={19} />
                  {name}
                </button>
              </div>
            ),
          )}
        </nav>
        <p id="navigation-note" className="navigation-note">
          研究服务接入中
          <br />
          其余业务页面将陆续开放
        </p>
        <div className="workspace">
          <div className="workspace-label">
            <CircleUserRound size={17} />
            <span title={data?.tenant.name}>我的工作空间</span>
            <span className="small-badge">个人</span>
          </div>
          <div className="profile-row">
            <span className="avatar">{data?.user.display_name.slice(0, 1)}</span>
            <div>
              <strong>{data?.user.display_name}</strong>
              <small>个人工作空间 · 所有者</small>
            </div>
            <Link
              to="/settings"
              className="icon-button"
              title="账户与工作空间"
              aria-label="账户设置"
            >
              <Settings size={19} />
            </Link>
          </div>
        </div>
      </aside>
      {menuOpen && (
        <button
          className="menu-scrim"
          aria-label="关闭导航遮罩"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <div className="main-shell">
        <header className="topbar">
          <div className="flex items-center gap-3">
            <button
              className="icon-button open-menu"
              aria-label="打开导航"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(true)}
            >
              <Menu size={20} />
            </button>
            <Shapes size={18} />
            <strong>{pageTitle}</strong>
            <span className="baseline-badge">个人工作空间</span>
          </div>
          <div className="topbar-actions">
            <Link
              to="/"
              className="soft-button"
              onClick={() =>
                document.querySelector<HTMLTextAreaElement>('#research-input')?.focus()
              }
            >
              <Plus size={17} />
              新建调研
            </Link>
            <button className="outline-button" disabled title="导入尚未开放">
              <Upload size={16} />
              导入项目
            </button>
            <button
              className="icon-button"
              disabled
              aria-label="通知（尚未开放）"
              title="通知尚未开放"
            >
              <Bell size={18} />
            </button>
          </div>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
