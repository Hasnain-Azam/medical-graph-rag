/**
 * API Service Layer
 *
 * All HTTP communication with the FastAPI backend lives here.
 * The Vite dev-server proxy forwards /api/* to http://localhost:8000
 * so no CORS issues during development.
 */
import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 120_000, // 2-minute timeout for LLM calls
  headers: { "Content-Type": "application/json" },
});

// ── Response / Error interceptors ────────────────────────────────────────────────
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail =
      err.response?.data?.detail ||
      err.message ||
      "An unexpected error occurred.";
    return Promise.reject(new Error(detail));
  }
);

// ── API Functions ─────────────────────────────────────────────────────────────────

/**
 * Upload a PDF or TXT file for ingestion into the knowledge graph.
 * @param {File} file
 * @param {function} onProgress  - callback(percent: number)
 * @returns {Promise<UploadResponse>}
 */
export async function uploadDocument(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (e.total && onProgress) {
        onProgress(Math.round((e.loaded * 100) / e.total));
      }
    },
  });

  return response.data;
}

/**
 * Send a question to the GraphRAG pipeline.
 * Returns an AI-generated answer + the relevant subgraph for visualization.
 * @param {string} question
 * @returns {Promise<ChatResponse>}
 */
export async function sendQuery(question) {
  const response = await api.post("/query", { question });
  return response.data;
}

/**
 * Fetch the full knowledge graph for the dashboard overview.
 * @returns {Promise<GraphStatsResponse>}
 */
export async function getFullGraph() {
  const response = await api.get("/graph");
  return response.data;
}

/**
 * Health check — verifies backend and Neo4j connectivity.
 * @returns {Promise<HealthResponse>}
 */
export async function healthCheck() {
  const response = await api.get("/health");
  return response.data;
}
