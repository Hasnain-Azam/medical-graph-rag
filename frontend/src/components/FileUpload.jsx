/**
 * FileUpload — drag-and-drop document ingestion component.
 * Accepts PDF and TXT files, shows upload progress, displays extraction stats.
 */
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { uploadDocument } from "../services/api";

const SAMPLE_FILE_PATH = "/sample_medical.txt"; // Served from public/

export default function FileUpload({ onUploadComplete }) {
  const [uploadState, setUploadState] = useState("idle"); // idle | uploading | success | error
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleUpload = useCallback(
    async (file) => {
      setUploadState("uploading");
      setProgress(0);
      setError(null);
      setResult(null);

      try {
        const data = await uploadDocument(file, setProgress);
        setResult(data);
        setUploadState("success");
        onUploadComplete?.();
      } catch (err) {
        setError(err.message);
        setUploadState("error");
      }
    },
    [onUploadComplete]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (accepted) => {
      if (accepted[0]) handleUpload(accepted[0]);
    },
    accept: {
      "application/pdf": [".pdf"],
      "text/plain": [".txt"],
      "text/markdown": [".md"],
    },
    maxFiles: 1,
    disabled: uploadState === "uploading",
  });

  const handleSampleLoad = async () => {
    try {
      const res = await fetch("/sample_medical.txt");
      const blob = await res.blob();
      const file = new File([blob], "sample_medical.txt", { type: "text/plain" });
      handleUpload(file);
    } catch {
      setError("Could not load the sample file. Make sure the dev server is running.");
      setUploadState("error");
    }
  };

  return (
    <div className="upload-container">
      <div className="panel-section">
        <h3>📂 Document Ingestion</h3>
      </div>

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? "active" : ""}`}
        style={{ marginTop: 10 }}
      >
        <input {...getInputProps()} />

        {uploadState === "uploading" ? (
          <>
            <span className="dropzone-icon">⚙️</span>
            <p className="dropzone-text">Processing document with GPT-4o...</p>
            <p className="dropzone-subtext">Extracting entities &amp; building graph</p>
            <div className="upload-progress">
              <div className="progress-bar-track">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${Math.max(progress, 8)}%` }}
                />
              </div>
            </div>
          </>
        ) : (
          <>
            <span className="dropzone-icon">
              {isDragActive ? "📥" : "📄"}
            </span>
            <p className="dropzone-text">
              {isDragActive ? "Drop your file here" : "Drag & drop a PDF or TXT file"}
            </p>
            <p className="dropzone-subtext">or click to browse · Max 20MB</p>
          </>
        )}
      </div>

      {/* Sample dataset shortcut */}
      {uploadState !== "uploading" && (
        <button
          onClick={handleSampleLoad}
          style={{
            marginTop: 8,
            width: "100%",
            padding: "7px",
            background: "transparent",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--radius-sm)",
            color: "var(--text-muted)",
            fontSize: "11px",
            cursor: "pointer",
            transition: "var(--transition)",
          }}
          onMouseOver={(e) => {
            e.target.style.borderColor = "var(--accent-cyan)";
            e.target.style.color = "var(--accent-cyan)";
          }}
          onMouseOut={(e) => {
            e.target.style.borderColor = "var(--border-color)";
            e.target.style.color = "var(--text-muted)";
          }}
        >
          ⚡ Load Sample Dataset (Diabetes / T2DM)
        </button>
      )}

      {/* Success Result */}
      {uploadState === "success" && result && (
        <div className="upload-result success">
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            ✅ {result.filename} ingested successfully
          </div>
          <div className="upload-result-stats">
            <div className="result-stat">🔵 <span>{result.entities_extracted}</span> Entities</div>
            <div className="result-stat">🔗 <span>{result.relationships_extracted}</span> Relationships</div>
            <div className="result-stat">📄 <span>{result.chunks_processed}</span> Chunks</div>
          </div>
        </div>
      )}

      {/* Error Result */}
      {uploadState === "error" && error && (
        <div className="upload-result error">
          <div style={{ fontWeight: 600, marginBottom: 2 }}>❌ Upload failed</div>
          <div style={{ fontSize: "11px", opacity: 0.85 }}>{error}</div>
        </div>
      )}
    </div>
  );
}
