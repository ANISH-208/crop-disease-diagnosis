export default function Scanner({ preview, loading }) {
  return (
    <div
      className={`scanner-stage ${loading ? "scanning" : ""} ${
        preview ? "has-image" : ""
      }`}
    >
      <div className="scanner-grid" />

      <div className="scan-ring ring-one" />
      <div className="scan-ring ring-two" />

      <div className="reticle reticle-tl" />
      <div className="reticle reticle-tr" />
      <div className="reticle reticle-bl" />
      <div className="reticle reticle-br" />

      {preview ? (
        <img
          src={preview}
          alt="Crop preview"
          className="scan-image"
        />
      ) : (
        <div className="leaf-placeholder">
          <span>◈</span>
          <small>WAITING FOR SPECIMEN</small>
        </div>
      )}

      {loading && <div className="scan-beam" />}

      <div className="scanner-label">
        <span>
          {loading
            ? "LIVE ANALYSIS"
            : preview
              ? "SPECIMEN LOCKED"
              : "OPTICAL SENSOR"}
        </span>

        <b>{loading ? "SCANNING" : "READY"}</b>
      </div>
    </div>
  );
}
