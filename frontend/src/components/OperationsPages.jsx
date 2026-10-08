import { useEffect, useMemo, useState } from "react";
import classMapping from "../../../ml_v6/outputs/class_mapping.json";
import { API_URL, WS_URL, fetchDiseases, fetchHealth } from "../services/api";

const MODEL_CLASSES = classMapping.classes;

const cropNames = [...new Set(MODEL_CLASSES.map((item) => item.split("___")[0]))].sort();

function ModuleHeader({ number, eyebrow, title, subtitle, action }) {
  return <header className="module-header"><div><div className="eyebrow">{number} / {eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</header>;
}

function Metric({ label, value, note, tone = "" }) {
  return <article className={`ops-metric glass ${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small><i className="metric-spark" /></article>;
}

export function AnalyticsPage({ alerts, history, events, onNavigate }) {
  const [windowFilter, setWindowFilter] = useState("all");
  const filteredHistory = windowFilter === "all" ? history : history.slice(0, Number(windowFilter));
  const cropCounts = useMemo(() => Object.entries(alerts.reduce((counts, alert) => {
    counts[alert.crop || "Unknown"] = (counts[alert.crop || "Unknown"] || 0) + 1;
    return counts;
  }, {})).sort((a, b) => b[1] - a[1]).slice(0, 7), [alerts]);
  const maxCrop = Math.max(1, ...cropCounts.map(([, count]) => count));
  const severity = ["Critical", "High", "Moderate", "Low", "None", "Unknown"].map((name) => ({ name, count: alerts.filter((item) => (item.severity || "Unknown").toLowerCase() === name.toLowerCase()).length }));
  const avgConfidence = alerts.length ? (alerts.reduce((sum, item) => sum + Number(item.confidence || 0), 0) / alerts.length).toFixed(1) : "—";
  const pending = alerts.filter((item) => item.status === "pending").length;

  return <section className="page-view ops-page">
    <ModuleHeader number="04" eyebrow="FIELD SIGNALS / LIVE DATA" title={<>Analytics<span className="title-leaf">↗</span></>} subtitle="Explore the alert queue, session diagnoses, and live system events. Charts reflect data collected by this app; empty states stay honest when there is no data." action={<button className="dashboard-launch" onClick={() => onNavigate("scanner")}>NEW DIAGNOSIS <span>→</span></button>} />
    <div className="ops-metrics"><Metric label="EXPERT ALERTS" value={alerts.length} note="Saved by the backend"/><Metric label="PENDING REVIEW" value={pending} note="Waiting in expert queue" tone="mint"/><Metric label="SESSION SCANS" value={history.length} note="Since this page was opened" tone="deep"/><Metric label="AVG. ALERT CONFIDENCE" value={`${avgConfidence}${avgConfidence === "—" ? "" : "%"}`} note="Across saved alerts" tone="lime"/></div>
    <div className="ops-columns">
      <article className="ops-panel glass"><div className="ops-panel-heading"><div><span className="ops-kicker">01 / DISTRIBUTION</span><h2>Alerts by crop</h2></div><span className="ops-count">{alerts.length} TOTAL</span></div>
        {cropCounts.length ? <div className="horizontal-bars">{cropCounts.map(([crop, count], index) => <div className="hbar-row" key={crop}><span>{crop}</span><div className="hbar-track"><i style={{ width: `${Math.max(8, count / maxCrop * 100)}%`, animationDelay: `${index * 70}ms` }}/></div><b>{count}</b></div>)}</div> : <EmptyChart title="No crop data yet" detail="Expert alerts will appear here after diagnoses are escalated."/>}
      </article>
      <article className="ops-panel glass"><div className="ops-panel-heading"><div><span className="ops-kicker">02 / CASE MIX</span><h2>Severity profile</h2></div><span className="ops-count">QUEUE</span></div>
        <div className="severity-list">{severity.map((item) => <div className="severity-row" key={item.name}><span className={`severity-dot sev-${item.name.toLowerCase()}`}/><span>{item.name}</span><strong>{item.count}</strong><i style={{ width: `${alerts.length ? item.count / alerts.length * 100 : 0}%` }}/></div>)}</div>
      </article>
    </div>
    <article className="ops-panel glass session-panel"><div className="ops-panel-heading"><div><span className="ops-kicker">03 / DIAGNOSTIC LOG</span><h2>Recent scans</h2></div><label className="ops-select-label">SHOW <select value={windowFilter} onChange={(event) => setWindowFilter(event.target.value)}><option value="all">ALL</option><option value="5">5</option><option value="10">10</option></select></label></div>
      {filteredHistory.length ? <div className="ops-table-wrap"><table className="ops-table"><thead><tr><th>TIME</th><th>CROP</th><th>AI FINDING</th><th>CONFIDENCE</th><th>SEVERITY</th><th>REVIEW</th></tr></thead><tbody>{filteredHistory.map((scan) => <tr key={scan.id}><td>{new Date(scan.analyzed_at).toLocaleString()}</td><td>{scan.crop}</td><td>{scan.diagnosis}</td><td>{scan.confidence}%</td><td>{scan.severity}</td><td>{scan.expert_review ? "Recommended" : "Not flagged"}</td></tr>)}</tbody></table></div> : <EmptyChart title="Your scan log starts here" detail="Run a diagnosis to build an analysis history for this browser session." button={<button className="text-action" onClick={() => onNavigate("scanner")}>OPEN SCANNER →</button>}/>}
    </article>
    <div className="ops-panel glass event-ribbon"><span className="ops-kicker">LIVE EVENT TAPE</span><div>{events.length ? events.slice(0, 5).map((event) => <div className="tape-item" key={event.id}><time>{event.time}</time><b>{event.label}</b><span>{event.detail}</span></div>) : <p>No live events received yet.</p>}</div></div>
  </section>;
}

export function CropHealthPage({ onNavigate }) {
  const [crop, setCrop] = useState("All crops");
  const [query, setQuery] = useState("");
  const [cropRecords, setCropRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    fetchDiseases()
      .then((items) => {
        if (!active) return;
        setCropRecords(items);
        setLoadError("");
      })
      .catch((error) => {
        if (active) setLoadError(error.message || "Could not load crop reference data.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [reloadKey]);

  const results = cropRecords.filter((item) => {
    const matchesCrop = crop === "All crops" || item.crop === crop;
    const searchable = `${item.crop} ${item.diagnosis} ${item.severity} ${item.symptoms}`.toLowerCase();
    return matchesCrop && searchable.includes(query.toLowerCase());
  });
  const filteredCrops = crop === "All crops" ? cropNames.length : 1;
  return <section className="page-view ops-page">
    <ModuleHeader number="05" eyebrow="38 CLASS REFERENCE / FIELD GUIDE" title={<>Crop health<span className="title-leaf">✳</span></>} subtitle="Browse the exact crop and condition labels supported by the V6 classifier. Use AI findings as a starting point and confirm symptoms in the field." action={<button className="dashboard-launch" onClick={() => onNavigate("scanner")}>SCAN A LEAF <span>→</span></button>} />
    <div className="crop-summary"><div className="crop-summary-leaf">❋</div><div><b>MODEL COVERAGE</b><strong>{cropNames.length} crops <span>/</span> {MODEL_CLASSES.length} classes</strong><small>Reference symptoms and prevention served by the diagnosis API</small></div><div className="crop-summary-orbit"><i/><i/><i/></div></div>
    <div className="crop-toolbar"><label className="crop-search"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search crop or disease" aria-label="Search crop or disease"/></label><label className="crop-select">CROP<select value={crop} onChange={(event) => setCrop(event.target.value)}><option>All crops</option>{cropNames.map((item) => <option key={item}>{item}</option>)}</select></label><span className="crop-result-count">{results.length} CONDITIONS / {filteredCrops} {filteredCrops === 1 ? "CROP" : "CROPS"}</span></div>
    {loadError && <div className="benchmark-note" role="alert"><span>!</span><p>{loadError}</p><button className="text-action" onClick={() => { setLoading(true); setReloadKey((value) => value + 1); }}>RETRY</button></div>}
    {loading ? <EmptyChart title="Loading crop reference" detail="Requesting supported classes and field guidance from the API."/> : <div className="crop-condition-grid">{results.map((item, index) => { const healthy = item.diagnosis.toLowerCase() === "healthy"; return <article className={`crop-condition glass ${healthy ? "healthy" : "condition"}`} key={item.class} style={{ animationDelay: `${index % 12 * 35}ms` }}><div className="condition-top"><span className="condition-glyph">{healthy ? "✳" : "◌"}</span><span className="condition-index">{String(index + 1).padStart(2, "0")}</span></div><small>{item.crop.toUpperCase()}</small><h3>{item.diagnosis}</h3><p>{item.symptoms}</p><div className="condition-tags"><span>{item.severity.toUpperCase()} SEVERITY</span><span>{item.expert_review ? "EXPERT REVIEW ADVISED" : "HEALTHY CLASS"}</span></div><details className="condition-details"><summary>Prevention protocol</summary><ul>{item.prevention.map((step) => <li key={step}>{step}</li>)}</ul></details></article>; })}</div>}
    {!loading && !loadError && !results.length && <EmptyChart title="No matching class" detail="Try a different crop or search term."/>}
    <p className="knowledge-note">Reference labels reflect the model's training taxonomy. The classifier does not cover every crop variety, disease, nutrient deficiency, or field condition.</p>
  </section>;
}

export function ModelIntelligencePage({ history }) {
  const lastScan = history[0];
  const classesByCrop = Object.entries(MODEL_CLASSES.reduce((groups, raw) => { const crop = raw.split("___")[0]; groups[crop] = (groups[crop] || 0) + 1; return groups; }, {})).sort((a, b) => b[1] - a[1]);
  return <section className="page-view ops-page">
    <ModuleHeader number="06" eyebrow="VISION ENGINE / MODEL CARD" title={<>Model intelligence<span className="title-leaf">◎</span></>} subtitle="A transparent view of the classifier configuration, benchmark context, class coverage, and most recent inference."/>
    <div className="model-hero glass"><div className="model-graphic"><div className="model-plant">✳</div><div className="model-orbit one"/><div className="model-orbit two"/><span className="model-chip">V6 / ACTIVE</span></div><div className="model-summary"><span className="ops-kicker">IMAGE CLASSIFICATION</span><h2>EfficientNetV2-S</h2><p>Fine-tuned visual classifier for leaf disease recognition across the PlantVillage label set.</p><div className="model-summary-tags"><b>38 OUTPUT CLASSES</b><b>224 × 224 RGB</b><b>TOP-5 ENABLED</b></div></div><div className="model-accuracy"><strong>99.04<small>%</small></strong><span>HELD-OUT BENCHMARK ACCURACY</span></div></div>
    <div className="model-stats"><Metric label="BENCHMARK TOP-5" value="99.98%" note="Held-out PlantVillage result"/><Metric label="MACRO F1" value="98.58%" note="Held-out class-averaged score" tone="mint"/><Metric label="SESSION INFERENCES" value={history.length} note="This browser session" tone="deep"/></div>
    <div className="ops-columns model-columns"><article className="ops-panel glass"><div className="ops-panel-heading"><div><span className="ops-kicker">CLASS COVERAGE</span><h2>Supported crops</h2></div><span className="ops-count">{classesByCrop.length} CROPS</span></div><div className="coverage-list">{classesByCrop.map(([crop, count])=><div key={crop}><span>{crop}</span><div className="coverage-track"><i style={{width:`${count/Math.max(...classesByCrop.map((entry)=>entry[1]))*100}%`}}/></div><b>{count}</b></div>)}</div></article><article className="ops-panel glass"><div className="ops-panel-heading"><div><span className="ops-kicker">LATEST INFERENCE</span><h2>Run telemetry</h2></div></div>{lastScan ? <div className="last-inference"><span>{lastScan.crop}</span><strong>{lastScan.diagnosis}</strong><div><b>{lastScan.confidence}%</b><span>confidence</span></div><p>{lastScan.model_version || "EfficientNetV2-S V6"} · {new Date(lastScan.analyzed_at).toLocaleString()}</p></div> : <EmptyChart title="No inference this session" detail="Run a leaf scan to see its latest prediction and timing context."/>}</article></div>
    <div className="benchmark-note"><span>!</span><p><b>Benchmark context.</b> Reported metrics are from the held-out PlantVillage benchmark. They are not a guarantee of field performance; lighting, camera quality, crop variety, and mixed symptoms can affect predictions.</p></div>
  </section>;
}

export function SettingsPage({ preferences, onChange, socketState, onRefresh, refreshing, alertSyncError }) {
  const [health, setHealth] = useState({ state: "idle", detail: "Not checked yet" });
  const checkConnection = async () => {
    setHealth({ state: "checking", detail: "Checking API health…" });
    try {
      const payload = await fetchHealth();
      const database = payload.database || "unknown";
      const modelStatus = payload.model?.status || "unknown";
      const socketCount = payload.connections ?? 0;
      setHealth({
        state: payload.status === "healthy" ? "ok" : "degraded",
        detail: `API ${payload.status} · model ${modelStatus} · database ${database} · ${socketCount} live connection${socketCount === 1 ? "" : "s"}`,
      });
    } catch (error) { setHealth({ state: "error", detail: error.message || "API is unreachable" }); }
  };
  const patch = (values) => onChange({ ...preferences, ...values });
  return <section className="page-view ops-page">
    <ModuleHeader number="07" eyebrow="PREFERENCES / CONNECTIONS" title={<>Settings<span className="title-leaf">⚙</span></>} subtitle="Tune the visual feel of the workspace and inspect the API connection used by the scanner and expert queue."/>
    <div className="settings-grid"><article className="ops-panel glass settings-panel"><span className="ops-kicker">01 / APPEARANCE</span><h2>Field palette</h2><p>Choose a green family; every option keeps the interface rooted in botanical shades.</p><div className="palette-options">{[{id:"canopy",label:"Canopy",swatches:["#14271b","#2e7047","#a7d995"]},{id:"fern",label:"Fern",swatches:["#11201c","#377d68","#b2e5c7"]},{id:"moss",label:"Moss",swatches:["#202518","#708c3d","#d4df8b"]}].map((option)=><button key={option.id} className={preferences.palette===option.id?"chosen":""} onClick={()=>patch({palette:option.id})}><span className="palette-swatches">{option.swatches.map((color)=><i key={color} style={{background:color}}/>)}</span><b>{option.label}</b>{preferences.palette===option.id&&<em>ACTIVE</em>}</button>)}</div><div className="setting-row"><div><b>Interface motion</b><small>Animate page transitions, charts, scanner elements, and hover states.</small></div><button className={`switch ${preferences.motion?"checked":""}`} role="switch" aria-checked={preferences.motion} onClick={()=>patch({motion:!preferences.motion})}><i/></button></div></article>
      <article className="ops-panel glass settings-panel"><span className="ops-kicker">02 / BACKEND LINK</span><h2>Connection health</h2><p>These endpoints power image diagnosis, alert management, health checks, and the live event stream.</p><div className="endpoint-field"><label>REST API</label><code>{API_URL}</code><span className="endpoint-state">● CONFIGURED</span></div><div className="endpoint-field"><label>WEBSOCKET</label><code>{WS_URL}</code><span className={`endpoint-state ${socketState === "live" ? "healthy" : ""}`}>● {socketState.toUpperCase()}</span></div><div className={`health-result ${health.state}`}><span>{health.state === "ok" ? "✓" : health.state === "error" ? "!" : "◌"}</span>{health.detail}</div>{alertSyncError && <div className="error-line" role="status">{alertSyncError}</div>}<div className="settings-actions"><button className="dashboard-launch" onClick={checkConnection} disabled={health.state === "checking"}>{health.state === "checking" ? "CHECKING…" : "CHECK CONNECTION"}</button><button className="secondary-action" onClick={onRefresh} disabled={refreshing}>{refreshing ? "SYNCING…" : "SYNC ALERTS"}</button></div></article></div>
    <article className="ops-panel glass settings-about"><span className="ops-kicker">03 / SYSTEM NOTES</span><div><b>Diagnostic assistance only</b><p>AI output is a screening aid. Verify findings in the field and consult a qualified agricultural expert before applying disease-control measures.</p></div><span className="settings-version">CROP DOCTOR AI · FRONTEND V6</span></article>
  </section>;
}

function EmptyChart({ title, detail, button }) { return <div className="chart-empty"><span className="empty-mark">✳</span><strong>{title}</strong><p>{detail}</p>{button}</div>; }
