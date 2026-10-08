export default function SpecimenInput({
  selectedFile,
  error,
  loading,
  inputRef,
  onFileChange,
  onDiagnose,
  onReset,
}) {
  return (
    <div className="control-card glass">
      <div className="section-head">
        <span>01 / SPECIMEN INPUT</span>
        <b>IMAGE CAPTURE</b>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/jpg"
        onChange={onFileChange}
        hidden
      />

      <button
        className="drop-zone"
        onClick={() => inputRef.current?.click()}
      >
        <div className="upload-orb">↑</div>

        <div>
          <strong>
            {selectedFile
              ? selectedFile.name
              : "DROP CROP IMAGE"}
          </strong>

          <small>
            {selectedFile
              ? `${(
                  selectedFile.size /
                  1024 /
                  1024
                ).toFixed(2)} MB • READY`
              : "JPG / PNG • CLICK TO BROWSE"}
          </small>
        </div>
      </button>

      {error && (
        <div className="error-line">
          ⚠ {error}
        </div>
      )}

      <button
        className="primary-action"
        disabled={!selectedFile || loading}
        onClick={onDiagnose}
      >
        {loading ? (
          <>
            <i className="mini-spinner" />
            RUNNING V6 INFERENCE
          </>
        ) : (
          <>
            RUN DIAGNOSIS <span>→</span>
          </>
        )}
      </button>

      {selectedFile && (
        <button
          className="ghost-action"
          onClick={onReset}
        >
          CLEAR SPECIMEN
        </button>
      )}
    </div>
  );
}
