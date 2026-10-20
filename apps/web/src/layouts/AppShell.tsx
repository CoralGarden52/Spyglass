import { useState } from 'react';
import { Link, Outlet } from 'react-router';
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
            index === 0 ? (
              <Link
                to="/"
                aria-current="page"
                className="nav-item active"
                key={name}
                onClick={() => setMenuOpen(false)}
              >
                <Icon size={19} />
                {name}
              </Link>
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
          工程初始化中
          <br />
          业务页面将在后续切片开放
        </p>
        <div className="workspace">
          <div className="workspace-label">
            <CircleUserRound size={17} />
            <span>我的工作空间</span>
            <span className="small-badge">本地开发</span>
          </div>
          <div className="profile-row">
            <span className="avatar">S</span>
            <div>
              <strong>访客</strong>
              <small>认证将在 Slice 1 开放</small>
            </div>
            <button
              className="icon-button"
              disabled
              title="设置尚未开放"
              aria-label="设置（尚未开放）"
            >
              <Settings size={19} />
            </button>
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
            <strong>工作台</strong>
            <span className="baseline-badge">工程基线 · Slice 0</span>
          </div>
          <div className="topbar-actions">
            <button
              className="soft-button"
              onClick={() =>
                document.querySelector<HTMLTextAreaElement>('#research-input')?.focus()
              }
            >
              <Plus size={17} />
              新建调研
            </button>
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
