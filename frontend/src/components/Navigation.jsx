import { translate as t } from "../i18n";

const primaryItems = [
  { id: "home", icon: "⌂", label: "home" },
  { id: "scanner", icon: "◎", label: "checkCrop", action: true },
  { id: "reports", icon: "▤", label: "reports" },
  { id: "help", icon: "?", label: "help" },
];

const secondaryItems = [
  { id: "dashboard", label: "moreOverview" },
  { id: "expert", label: "moreExpertQueue" },
  { id: "analytics", label: "moreAnalysisSummary" },
  { id: "crops", label: "moreCropGuide" },
  { id: "model", label: "moreAboutModel" },
  { id: "settings", label: "moreConnectionSettings" },
];

export default function Navigation({ page, onNavigate, language = "en" }) {
  const text = (key) => t(language, key);
  const moreActive = secondaryItems.some((item) => item.id === page) || page === "dashboard";
  return <>
    <nav className="farmer-navigation desktop-navigation" aria-label="Main navigation">
      <div className="desktop-primary">{primaryItems.map((item) => <NavButton key={item.id} item={item} active={page === item.id} text={text} onNavigate={onNavigate} />)}</div>
      <details className={`more-menu ${moreActive ? "more-active" : ""}`}>
        <summary><span aria-hidden="true">⋯</span>{text("more")}</summary>
        <div className="more-menu-panel"><strong>{text("advanced")}</strong>{secondaryItems.map((item) => <button key={item.id} aria-current={page === item.id ? "page" : undefined} onClick={() => onNavigate(item.id)}>{text(item.label)}</button>)}</div>
      </details>
    </nav>
    <nav className="farmer-navigation mobile-navigation" aria-label="Main navigation">
      {primaryItems.map((item) => <NavButton key={item.id} item={item} active={page === item.id} text={text} onNavigate={onNavigate} />)}
    </nav>
  </>;
}

function NavButton({ item, active, text, onNavigate }) {
  return <button type="button" className={`farmer-nav-item ${item.action ? "nav-action" : ""} ${active ? "active" : ""}`} aria-current={active ? "page" : undefined} onClick={() => onNavigate(item.id)}>
    <span className="farmer-nav-icon" aria-hidden="true">{item.icon}</span>
    <span>{text(item.label)}</span>
  </button>;
}
