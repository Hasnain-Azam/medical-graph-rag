/**
 * App.jsx — Root component.
 *
 * Layout:
 *  ┌──────────────────────────────────────────────────────┐
 *  │                  StatusBar (top)                     │
 *  ├─────────────────────┬────────────────────────────────┤
 *  │   Left Panel        │   Right Panel                  │
 *  │   ─────────         │   ────────────                 │
 *  │   FileUpload        │   GraphVisualization           │
 *  │   ─────────         │   (react-force-graph-2d)       │
 *  │   ChatInterface     │                                │
 *  └─────────────────────┴────────────────────────────────┘
 *
 * State:
 *  - graphData / graphMode: shared between chat (writes) and graph (reads)
 *  - isConnected: Neo4j health check
 *  - graphStats: node/relationship counts for StatusBar
 */
import { useState, useEffect, useCallback } from "react";
import StatusBar from "./components/StatusBar";
import FileUpload from "./components/FileUpload";
import ChatInterface from "./components/ChatInterface";
import GraphVisualization from "./components/GraphVisualization";
import { healthCheck, getFullGraph } from "./services/api";

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [graphMode, setGraphMode] = useState("empty");    // empty | overview | query
  const [graphStats, setGraphStats] = useState(null);
  const [isGraphLoading, setIsGraphLoading] = useState(false);

  // ── Health check on mount ──────────────────────────────────────────────────
  useEffect(() => {
    const check = async () => {
      try {
        const data = await healthCheck();
        setIsConnected(data.neo4j_connected);
      } catch {
        setIsConnected(false);
      }
    };

    check();
    const interval = setInterval(check, 30_000); // re-check every 30s
    return () => clearInterval(interval);
  }, []);

  // ── Fetch full graph overview ──────────────────────────────────────────────
  const loadFullGraph = useCallback(async () => {
    setIsGraphLoading(true);
    try {
      const data = await getFullGraph();
      setGraphData(data.graph);
      setGraphMode("overview");
      setGraphStats({
        totalNodes: data.total_nodes,
        totalRelationships: data.total_relationships,
        nodeTypes: data.node_types,
        relationshipTypes: data.relationship_types,
      });
    } catch (err) {
      console.error("Failed to load graph overview:", err);
    } finally {
      setIsGraphLoading(false);
    }
  }, []);

  // ── Called by FileUpload after successful ingestion ───────────────────────
  const handleUploadComplete = useCallback(() => {
    loadFullGraph();
  }, [loadFullGraph]);

  // ── Called by ChatInterface after a successful query ──────────────────────
  const handleGraphUpdate = useCallback((subgraph, mode) => {
    setGraphData(subgraph);
    setGraphMode(mode);
    // Update stats to reflect subgraph size
    setGraphStats((prev) => ({
      ...prev,
      totalNodes: subgraph.nodes.length,
      totalRelationships: subgraph.links.length,
    }));
  }, []);

  return (
    <div className="app-container">
      {/* ── Top Bar ── */}
      <StatusBar isConnected={isConnected} graphStats={graphStats} />

      {/* ── Main Body ── */}
      <div className="app-body">

        {/* ── Left Panel ── */}
        <div className="left-panel">
          <FileUpload onUploadComplete={handleUploadComplete} />
          <ChatInterface onGraphUpdate={handleGraphUpdate} />
        </div>

        {/* ── Right Panel ── */}
        <div className="right-panel">
          {/* Overview button */}
          {graphStats?.totalNodes > 0 && graphMode === "query" && (
            <div
              style={{
                position: "absolute",
                top: 60,
                left: 12,
                zIndex: 20,
              }}
            >
              <button
                className="graph-control-btn"
                onClick={loadFullGraph}
                style={{ background: "var(--bg-card)" }}
              >
                ← Full Graph
              </button>
            </div>
          )}

          <GraphVisualization
            graphData={graphData}
            mode={graphMode}
            isLoading={isGraphLoading}
          />
        </div>

      </div>
    </div>
  );
}
