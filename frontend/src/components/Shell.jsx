import { CalendarDays, LogOut, ShieldCheck, Soup, UserRound, UsersRound } from "lucide-react";

export function BrandMark({ className = "brand-mark" }) {
  return (
    <svg className={className} viewBox="0 0 64 64" aria-hidden="true">
      <circle cx="32" cy="32" r="30" fill="#D6DDD9" />
      <circle cx="32" cy="32" r="24" fill="#FBFCFB" />
      <path d="M32 8a24 24 0 0 1 23.5 19" fill="none" stroke="#E8A317" strokeWidth="6" strokeLinecap="round" />
      <circle cx="24" cy="30" r="7" fill="#0F3D2E" />
      <circle cx="40" cy="30" r="7" fill="#9C5A1E" />
      <circle cx="32" cy="43" r="7" fill="#E2B93B" />
    </svg>
  );
}

function navItems(user) {
  const items = [
    { id: "today", label: "Today", short: "Today", icon: Soup },
    { id: "history", label: "History", short: "History", icon: CalendarDays },
    { id: "profile", label: "Profile & goal", short: "Profile", icon: UserRound },
  ];
  if (user.is_admin) items.push({ id: "admin", label: "Admin console", short: "Admin", icon: ShieldCheck, sep: true });
  if (user.is_superadmin) items.push({ id: "team", label: "Admin team", short: "Team", icon: UsersRound });
  return items;
}

const ROLE_LABEL = { superadmin: "Super-admin", admin: "Admin", user: "Member" };

export function Shell({ user, page, onNavigate, onSignOut, children }) {
  const items = navItems(user);
  const initial = (user.full_name || user.email)[0]?.toUpperCase();
  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <BrandMark />
          <span className="brand-name">CALARO</span>
        </div>
        <nav className="nav" aria-label="Main">
          {items.map((it) => (
            <div key={it.id}>
              {it.sep && <div className="nav-sep" />}
              <button className="nav-item" aria-current={page === it.id ? "page" : undefined} onClick={() => onNavigate(it.id)}>
                <it.icon size={19} /> {it.label}
              </button>
            </div>
          ))}
        </nav>
        <div className="rail-foot">
          <div className="who">
            <span className="avatar">{initial}</span>
            <div className="who-text">
              <div className="who-name">{user.full_name || user.email.split("@")[0]}</div>
              <div className="who-role">{ROLE_LABEL[user.role] || "Member"}</div>
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onSignOut}>
            <LogOut size={15} /> Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="mobile-top">
          <div className="brand" style={{ padding: 0 }}>
            <BrandMark />
            <span className="brand-name">CALARO</span>
          </div>
          <button className="icon-btn" onClick={onSignOut} aria-label="Sign out"><LogOut size={17} /></button>
        </div>
        {children}
      </main>

      <nav className="tabbar" aria-label="Main">
        {items.map((it) => (
          <button key={it.id} aria-current={page === it.id ? "page" : undefined} onClick={() => onNavigate(it.id)}>
            <it.icon size={21} />
            {it.short}
          </button>
        ))}
      </nav>
    </div>
  );
}
