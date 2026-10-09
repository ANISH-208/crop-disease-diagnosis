import { translate as t } from "../i18n";

export default function HelpPage({ language, onNavigate }) {
  const text = (key) => t(language, key);
  return <section className="farmer-page page-view" aria-labelledby="help-title">
    <div className="page-intro"><span className="eyebrow">{text("cropCareEyebrow")}</span><h1 id="help-title">{text("assistance")}</h1><p>{text("guidanceNote")}</p></div>
    <div className="help-grid">
      <article className="content-card help-card"><span className="help-icon" aria-hidden="true">◎</span><span className="step-label">{text("beforeYouCheck")}</span><h2>{text("guidanceTitle")}</h2><p>{text("guidanceBody")}</p><ul><li>{text("tipOne")}</li><li>{text("tipTwo")}</li><li>{text("tipThree")}</li></ul><button className="button button-primary" onClick={() => onNavigate("scanner")}>{text("startCheck")}</button></article>
      <article className="content-card help-card"><span className="help-icon" aria-hidden="true">⌁</span><span className="step-label">{text("afterYourResult")}</span><h2>{text("useResultFirst")}</h2><p>{text("resultHelp")}</p><p>{text("avoidTreatmentOnly")}</p></article>
    </div>
    <details className="advanced-tools"><summary>{text("moreTools")}</summary><div className="advanced-tool-links"><button onClick={() => onNavigate("dashboard")}>{text("moreOverview")}</button><button onClick={() => onNavigate("expert")}>{text("moreExpertQueue")}</button><button onClick={() => onNavigate("crops")}>{text("moreCropGuide")}</button><button onClick={() => onNavigate("settings")}>{text("moreConnectionSettings")}</button><button onClick={() => onNavigate("model")}>{text("moreAboutModel")}</button><button onClick={() => onNavigate("analytics")}>{text("moreAnalysisSummary")}</button></div></details>
  </section>;
}
