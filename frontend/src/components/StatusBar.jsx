/**
 * StatusBar — top navigation bar.
 * Shows app branding, Neo4j connection status, and live graph statistics.
 */
export default function StatusBar({ isConnected, graphStats }) {
  return (
    <header className="status-bar">
      {/* Brand */}
      <div className="status-bar-brand">
        <div className="logo-icon">🧬</div>
        <span>Medical Graph RAG</span>
      </div>

      {/* Graph Stats */}
      <div className="status-bar-stats">
        <div className="stat-item">
          <span>Nodes</span>
          <span className="stat-value">{graphStats?.totalNodes ?? 0}</span>
        </div>
        <div className="stat-item">
          <span>Relationships</span>
          <span className="stat-value">{graphStats?.totalRelationships ?? 0}</span>
        </div>
        <div className="stat-item">
          <span>Entity Types</span>
          <span className="stat-value">
            {graphStats?.nodeTypes ? Object.keys(graphStats.nodeTypes).length : 0}
          </span>
        </div>
      </div>

      {/* Neo4j Status */}
      <div className={`status-badge ${isConnected ? "connected" : "disconnected"}`}>
        <div className="status-dot" />
        <span>{isConnected ? "Neo4j Connected" : "Neo4j Offline"}</span>
      </div>
    </header>
  );
}
