function Navigation({ page, onNavigate, stats }) {
  const navigation = [
    {
      id: "dashboard",
      icon: "⌂",
      label: "Dashboard",
      meta: "OVERVIEW",
    },
    {
      id: "scanner",
      icon: "⌁",
      label: "AI Scanner",
      meta: "DIAGNOSIS",
    },
    {
      id: "expert",
      icon: "!",
      label: "Expert Center",
      meta: "ALERTS",
      badge: stats.pending,
    },
    {
      id: "analytics",
      icon: "◫",
      label: "Analytics",
      meta: "INSIGHTS",
    },
    {
      id: "crops",
      icon: "✦",
      label: "Crop Health",
      meta: "KNOWLEDGE",
    },
    {
      id: "model",
      icon: "◉",
      label: "Model Intelligence",
      meta: "V6 ENGINE",
    },
    {
      id: "settings",
      icon: "⚙",
      label: "Settings",
      meta: "SYSTEM",
    },
  ];

  return (
    <aside className="navigation-panel">
      <div className="nav-heading">
        <span>CONTROL CENTER</span>
        <i>V6</i>
      </div>

      <nav className="navigation-list">
        {navigation.map((item) => (
          <button
            key={item.id}
            className={`navigation-item ${
              page === item.id ? "active" : ""
            }`}
            aria-current={page === item.id ? "page" : undefined}
            onClick={() => onNavigate(item.id)}
          >
            <span className="navigation-icon">
              {item.icon}
            </span>

            <span className="navigation-copy">
              <strong>{item.label}</strong>
              <small>{item.meta}</small>
            </span>

            {item.badge > 0 && (
              <span className="navigation-badge">
                {item.badge}
              </span>
            )}

            <span className="navigation-arrow">
              →
            </span>
          </button>
        ))}
      </nav>

      <div className="navigation-status">
        <span className="navigation-status-dot" />

        <div>
          <strong>SYSTEM READY</strong>
          <small>AI diagnostic network active</small>
        </div>
      </div>
    </aside>
  );
}

export default Navigation;
