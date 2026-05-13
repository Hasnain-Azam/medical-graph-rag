/**
 * GraphVisualization — interactive force-directed graph using react-force-graph-2d.
 *
 * Features:
 *  - Color-coded nodes by entity type
 *  - Hover tooltips showing name, type, description
 *  - Animated relationship arrows with labels
 *  - Zoom-to-fit controls
 *  - Toggle between "full overview" and "query subgraph" modes
 *  - Animated highlight when switching to query mode
 */
import { useCallback, useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

// ── Color palette per entity type ─────────────────────────────────────────────
const NODE_COLORS = {
  Disease:           "#ef4444",   // red
  Drug:              "#3b82f6",   // blue
  Gene:              "#8b5cf6",   // purple
  Symptom:           "#f59e0b",   // amber
  TreatmentProtocol: "#10b981",   // green
  BloodTest:         "#06b6d4",   // cyan
  default:           "#94a3b8",   // slate
};

const LEGEND_ITEMS = [
  { type: "Disease",           label: "Disease" },
  { type: "Drug",              label: "Drug" },
  { type: "Gene",              label: "Gene" },
  { type: "Symptom",           label: "Symptom" },
  { type: "TreatmentProtocol", label: "Treatment Protocol" },
  { type: "BloodTest",         label: "Blood Test" },
];

function getNodeColor(node) {
  return NODE_COLORS[node.type] ?? NODE_COLORS.default;
}

function getNodeRadius(node) {
  // Hub nodes (highly connected) appear slightly larger
  return node._degree ? Math.min(6 + node._degree * 0.8, 18) : 8;
}

export default function GraphVisualization({ graphData, mode, isLoading }) {
  const graphRef = useRef(null);
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [tooltip, setTooltip] = useState(null);
  const [fgData, setFgData] = useState({ nodes: [], links: [] });

  // ── Resize observer ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // ── Prepare graph data (add degree for sizing) ─────────────────────────────
  useEffect(() => {
    if (!graphData?.nodes?.length) {
      setFgData({ nodes: [], links: [] });
      return;
    }

    // Count degree for each node
    const degree = {};
    (graphData.links || []).forEach((link) => {
      degree[link.source] = (degree[link.source] || 0) + 1;
      degree[link.target] = (degree[link.target] || 0) + 1;
    });

    const nodes = graphData.nodes.map((n) => ({
      ...n,
      _degree: degree[n.id] || 0,
    }));

    // react-force-graph mutates link objects — provide copies
    const links = (graphData.links || []).map((l) => ({ ...l }));

    setFgData({ nodes, links });

    // Auto-zoom-to-fit after data loads
    setTimeout(() => {
      graphRef.current?.zoomToFit(400, 60);
    }, 300);
  }, [graphData]);

  // ── Custom node rendering (canvas) ────────────────────────────────────────
  const paintNode = useCallback((node, ctx, globalScale) => {
    const r = getNodeRadius(node);
    const color = getNodeColor(node);

    // Glow effect
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;

    // Node circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();

    // Border ring
    ctx.strokeStyle = "rgba(255,255,255,0.2)";
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.shadowBlur = 0;

    // Label — only show when zoomed in enough
    if (globalScale > 1.2) {
      const label = node.name.length > 18 ? node.name.slice(0, 16) + "…" : node.name;
      const fontSize = Math.min(12 / globalScale, 4);
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.fillStyle = "#f1f5f9";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, node.x, node.y + r + fontSize + 1);
    }
  }, []);

  // ── Custom link rendering ─────────────────────────────────────────────────
  const paintLink = useCallback((link, ctx, globalScale) => {
    const start = link.source;
    const end   = link.target;
    if (!start?.x || !end?.x) return;

    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const dist = Math.hypot(dx, dy);
    if (dist === 0) return;

    // Draw line
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = "rgba(148, 163, 184, 0.25)";
    ctx.lineWidth = 0.8;
    ctx.stroke();

    // Relationship label at midpoint — only when zoomed in
    if (globalScale > 1.8 && link.type) {
      const mx = (start.x + end.x) / 2;
      const my = (start.y + end.y) / 2;
      const fontSize = Math.min(8 / globalScale, 3);
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.fillStyle = "rgba(100, 116, 139, 0.9)";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(link.type, mx, my);
    }
  }, []);

  // ── Hover tooltip ─────────────────────────────────────────────────────────
  const handleNodeHover = useCallback((node, prevNode) => {
    if (node) {
      setTooltip({
        x: node.x,
        y: node.y,
        name: node.name,
        type: node.type,
        description: node.description || "",
      });
    } else {
      setTooltip(null);
    }
  }, []);

  const handleZoomToFit = () => {
    graphRef.current?.zoomToFit(400, 60);
  };

  const isEmpty = !fgData.nodes.length;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div className="graph-panel-header">
        <div className="graph-panel-title">
          <span>🕸️</span>
          <span>
            Knowledge Graph
            {mode === "query" && (
              <span style={{ marginLeft: 8, fontSize: 11, color: "var(--accent-cyan)", fontWeight: 400 }}>
                — Query Subgraph
              </span>
            )}
            {mode === "overview" && (
              <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-muted)", fontWeight: 400 }}>
                — Full Overview
              </span>
            )}
          </span>
        </div>
        <div className="graph-controls">
          <button className="graph-control-btn" onClick={handleZoomToFit} title="Zoom to fit">
            ⊡ Fit
          </button>
        </div>
      </div>

      {/* Canvas Wrapper */}
      <div className="graph-canvas-wrapper" ref={containerRef}>
        {/* Empty State */}
        {isEmpty && !isLoading && (
          <div className="graph-empty">
            <div className="graph-empty-icon">🧬</div>
            <h3>No Graph Data Yet</h3>
            <p>
              Upload a medical document using the panel on the left.
              After ingestion, the knowledge graph will appear here.
              Ask a question to see the relevant subgraph highlighted.
            </p>
          </div>
        )}

        {/* Loading Overlay */}
        {isLoading && (
          <div className="graph-loading">
            <div className="spinner" />
            <span>Building knowledge graph...</span>
          </div>
        )}

        {/* Force Graph */}
        {!isEmpty && (
          <ForceGraph2D
            ref={graphRef}
            graphData={fgData}
            width={dimensions.width}
            height={dimensions.height}
            backgroundColor="#0a0e1a"
            // Node rendering
            nodeCanvasObject={paintNode}
            nodeCanvasObjectMode={() => "replace"}
            nodeLabel={(node) => `${node.name} (${node.type})`}
            onNodeHover={handleNodeHover}
            // Link rendering
            linkCanvasObject={paintLink}
            linkCanvasObjectMode={() => "replace"}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkDirectionalArrowColor={() => "rgba(148,163,184,0.4)"}
            // Physics
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            cooldownTicks={120}
            // Interaction
            enableZoomInteraction
            enablePanInteraction
            enableNodeDrag
          />
        )}

        {/* Node Tooltip */}
        {tooltip && (
          <div
            className="graph-tooltip"
            style={{
              left: Math.min(tooltip.x + 15, dimensions.width - 260),
              top:  Math.min(tooltip.y + 15, dimensions.height - 120),
            }}
          >
            <div
              className="tooltip-name"
              style={{ borderLeft: `3px solid ${NODE_COLORS[tooltip.type] ?? NODE_COLORS.default}`, paddingLeft: 8 }}
            >
              {tooltip.name}
            </div>
            <div className="tooltip-type">{tooltip.type}</div>
            {tooltip.description && (
              <div className="tooltip-desc">{tooltip.description}</div>
            )}
          </div>
        )}

        {/* Legend */}
        {!isEmpty && (
          <div className="graph-legend">
            <div className="legend-title">Entity Types</div>
            {LEGEND_ITEMS.map(({ type, label }) => (
              <div key={type} className="legend-item">
                <div
                  className="legend-dot"
                  style={{ background: NODE_COLORS[type] }}
                />
                <span>{label}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Stats Bar */}
      <div className="graph-stats-bar">
        <div className="graph-stat">
          Nodes <span>{fgData.nodes.length}</span>
        </div>
        <div className="graph-stat">
          Relationships <span>{fgData.links.length}</span>
        </div>
        {fgData.nodes.length > 0 && (
          <div className="graph-stat">
            Types&nbsp;
            <span>
              {[...new Set(fgData.nodes.map((n) => n.type))].join(", ")}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
