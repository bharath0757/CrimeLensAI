/**
 * CrimeLensAI — Network Analysis Page
 *
 * Dedicated interactive criminal network visualization & intelligence workspace.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import ForceGraph2D from "react-force-graph-2d";
import { useTheme } from "../contexts/ThemeContext";
import { InterfaceIcon } from "../components/InterfaceIcon";
import type { CaseRecord } from "../lib/contracts";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  val: number;
  color: string;
  confidence?: number;
  status?: string;
  properties?: Record<string, any>;
  linkedCaseNames?: string[];
  x?: number;
  y?: number;
}

interface GraphLink {
  id?: string;
  source: string | any;
  target: string | any;
  label?: string;
  type?: string;
  confidence?: number;
}

interface GraphStatsData {
  total_nodes: number;
  total_edges: number;
  density: number;
  node_types_breakdown: Record<string, number>;
  relationship_types_breakdown: Record<string, number>;
  top_connected_entities: Array<{ entity_id: string; entity_name: string; degree: number; entity_type?: string }>;
}

const TYPE_COLORS: Record<string, string> = {
  CASE: "#6366f1",         // Indigo
  PERSON: "#3b82f6",       // Blue
  PHONE: "#10b981",        // Emerald
  PHONE_NUMBER: "#10b981", // Emerald
  VEHICLE: "#f59e0b",      // Amber
  UPI_ID: "#8b5cf6",       // Purple
  LOCATION: "#ef4444",     // Red
  ORG: "#06b6d4",          // Cyan
  ORGANIZATION: "#06b6d4", // Cyan
  BANK_ACCOUNT: "#14b8a6", // Teal
  IP_ADDRESS: "#f97316",   // Orange
  EMAIL: "#ec4899",        // Pink
  CRYPTO_WALLET: "#e11d48",// Rose
  OTHER: "#64748b",        // Slate
};

function formatEntityType(type: string): string {
  if (type === "PHONE_NUMBER") return "PHONE";
  if (type === "ORGANIZATION") return "ORG";
  return type.replace(/_/g, " ");
}

export function NetworkAnalysis() {
  const { theme } = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedCaseId = searchParams.get("caseId") || "";

  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>(requestedCaseId);
  const [graphStatus, setGraphStatus] = useState<"loading" | "success" | "error" | "empty">("loading");
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({ nodes: [], links: [] });
  const [graphStats, setGraphStats] = useState<GraphStatsData | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [actionProcessing, setActionProcessing] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 600 });

  // 1. Fetch available cases once on mount
  useEffect(() => {
    let active = true;
    const loadCases = async () => {
      try {
        const casesRes = await api.cases.metadata(0, 100);
        if (!active) return;
        const items = casesRes?.items || [];
        setCases(items);

        if (items.length > 0) {
          if (requestedCaseId && items.some(c => c.id === requestedCaseId)) {
            setSelectedCaseId(requestedCaseId);
          } else if (items.some(c => c.id === "DEMO-FIR-001")) {
            setSelectedCaseId("DEMO-FIR-001");
          } else {
            setSelectedCaseId(items[0].id);
          }
        }
      } catch (err) {
        if (!active) return;
        console.error("Failed to load cases list:", err);
      }
    };
    loadCases();
    return () => { active = false; };
  }, [requestedCaseId]);

  // 2. Fetch Graph Data & Cross-Case Linkage reactively without stale closure
  const fetchGraphData = useCallback(async (caseIdToLoad?: string) => {
    const caseId = caseIdToLoad || selectedCaseId;
    if (!caseId) return;

    setGraphStatus("loading");
    setSelectedNode(null);
    setActionFeedback(null);

    try {
      // Parallel fetch of topology and cross-case linkage
      const [graphRes, linkageRes] = await Promise.allSettled([
        api.graph.getCaseGraph(caseId),
        api.graph.getCaseLinkage(caseId),
      ]);

      if (graphRes.status === "rejected") {
        throw graphRes.reason;
      }

      const rawGraph: any = graphRes.value;
      const linkage: any = linkageRes.status === "fulfilled" ? linkageRes.value : null;

      // Build cross-case map
      const entityLinkedCasesMap: Record<string, string[]> = {};
      if (linkage?.linked_cases) {
        linkage.linked_cases.forEach((lc: any) => {
          const matchedCase = cases.find(c => c.id === lc.case_id);
          const caseLabel = matchedCase?.case_number
            ? `[${matchedCase.case_number}] ${matchedCase.title}`
            : (matchedCase?.title || lc.case_id);
          (lc.shared_entities || []).forEach((se: any) => {
            const val = String(se.value || "").trim().toLowerCase();
            if (val) {
              if (!entityLinkedCasesMap[val]) entityLinkedCasesMap[val] = [];
              entityLinkedCasesMap[val].push(`${caseLabel} (${Math.round((lc.link_strength || 0) * 100)}% match)`);
            }
          });
        });
      }

      const rawNodes = rawGraph.nodes || [];
      const rawEdges = rawGraph.edges || [];

      if (rawNodes.length === 0) {
        setGraphStatus("empty");
        setGraphData({ nodes: [], links: [] });
        setGraphStats(null);
        return;
      }

      const nodes: GraphNode[] = rawNodes.map((n: any) => {
        const valStr = String(n.label || "").trim().toLowerCase();
        const linkedCases = entityLinkedCasesMap[valStr] || [];
        return {
          id: n.id,
          name: n.label,
          type: n.type,
          val: n.type === "CASE" ? 8 : (linkedCases.length > 0 ? 6 : 4),
          color: TYPE_COLORS[n.type] || TYPE_COLORS["OTHER"] || "#94a3b8",
          confidence: n.confidence_score,
          status: n.properties?.status || n.properties?.review_status || "PENDING",
          properties: n.properties || {},
          linkedCaseNames: linkedCases,
        };
      });

      const links: GraphLink[] = rawEdges.map((e: any) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label || e.type || "",
        type: e.type || "",
        confidence: e.confidence_score,
      }));

      // If the case has entities but no internal edges, attach to a central case hub
      if (links.length === 0 && nodes.length > 0) {
        const currCase = cases.find(c => c.id === caseId);
        const caseNodeId = `hub-${caseId}`;
        const caseNode: GraphNode = {
          id: caseNodeId,
          name: currCase?.case_number ? `[${currCase.case_number}] ${currCase.title}` : (currCase?.title || caseId),
          type: "CASE",
          val: 8,
          color: TYPE_COLORS["CASE"],
          confidence: 1.0,
          status: "CONFIRMED",
          properties: { case_id: caseId },
          linkedCaseNames: ["Self"],
        };
        nodes.unshift(caseNode);
        nodes.forEach(n => {
          if (n.id !== caseNodeId) {
            links.push({
              id: `edge-hub-${n.id}`,
              source: caseNodeId,
              target: n.id,
              label: "BELONGS_TO",
              type: "BELONGS_TO",
              confidence: 1.0,
            });
          }
        });
      }

      setGraphData({ nodes, links });
      setGraphStats(rawGraph.stats || null);
      setGraphStatus("success");

      setTimeout(() => {
        if (graphRef.current) {
          graphRef.current.zoomToFit(400, 50);
        }
      }, 500);
    } catch (error) {
      console.error("Failed to fetch graph data:", error);
      setGraphStatus("error");
    }
  }, [selectedCaseId, cases]);

  // Trigger fetch whenever selectedCaseId changes
  useEffect(() => {
    if (selectedCaseId) {
      fetchGraphData(selectedCaseId);
    }
  }, [selectedCaseId, fetchGraphData]);

  // 3. Responsive container measuring via ResizeObserver
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({
            width: Math.floor(width),
            height: Math.max(Math.floor(height), 550),
          });
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // 4. Entity confirm / reject action handlers
  const handleEntityAction = async (action: "confirm" | "reject") => {
    if (!selectedNode || selectedNode.type === "CASE") return;
    setActionProcessing(true);
    setActionFeedback(null);
    try {
      if (action === "confirm") {
        await api.entities.confirm(selectedNode.id);
        const newStatus = "CONFIRMED";
        setSelectedNode(prev => prev ? { ...prev, status: newStatus } : null);
        setGraphData(prev => ({
          ...prev,
          nodes: prev.nodes.map(n => n.id === selectedNode.id ? { ...n, status: newStatus } : n)
        }));
        setActionFeedback({ type: "success", message: "Entity confirmed as verified investigative evidence." });
      } else {
        await api.entities.reject(selectedNode.id);
        const newStatus = "REJECTED";
        setSelectedNode(prev => prev ? { ...prev, status: newStatus } : null);
        setGraphData(prev => ({
          ...prev,
          nodes: prev.nodes.map(n => n.id === selectedNode.id ? { ...n, status: newStatus } : n)
        }));
        setActionFeedback({ type: "success", message: "Entity rejected and marked as false positive." });
      }
    } catch (error: any) {
      console.error(error);
      const msg = error?.message || `Unable to ${action} entity.`;
      setActionFeedback({ type: "error", message: msg });
    } finally {
      setActionProcessing(false);
    }
  };

  // 5. Filtered graph data based on active type chip
  const displayedGraphData = useMemo(() => {
    if (typeFilter === "ALL") return graphData;
    const filteredNodes = graphData.nodes.filter(n => n.type === typeFilter || n.type === "CASE");
    const allowedNodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredLinks = graphData.links.filter(l => {
      const srcId = typeof l.source === "object" ? l.source.id : l.source;
      const tgtId = typeof l.target === "object" ? l.target.id : l.target;
      return allowedNodeIds.has(srcId) && allowedNodeIds.has(tgtId);
    });
    return { nodes: filteredNodes, links: filteredLinks };
  }, [graphData, typeFilter]);

  // Available types in current graph for filter chips
  const availableTypes = useMemo(() => {
    const counts: Record<string, number> = {};
    graphData.nodes.forEach(n => {
      if (n.type !== "CASE") {
        counts[n.type] = (counts[n.type] || 0) + 1;
      }
    });
    return counts;
  }, [graphData.nodes]);

  // Connected neighbors of selected node
  const selectedNeighbors = useMemo(() => {
    if (!selectedNode) return [];
    const neighbors: Array<{ node: GraphNode; edgeLabel: string }> = [];
    const nodeId = selectedNode.id;

    graphData.links.forEach(link => {
      const srcId = typeof link.source === "object" ? link.source.id : link.source;
      const tgtId = typeof link.target === "object" ? link.target.id : link.target;

      if (srcId === nodeId) {
        const targetNode = graphData.nodes.find(n => n.id === tgtId);
        if (targetNode) neighbors.push({ node: targetNode, edgeLabel: link.label || "CONNECTED" });
      } else if (tgtId === nodeId) {
        const sourceNode = graphData.nodes.find(n => n.id === srcId);
        if (sourceNode) neighbors.push({ node: sourceNode, edgeLabel: link.label || "CONNECTED" });
      }
    });
    return neighbors;
  }, [selectedNode, graphData]);

  // Zoom helpers
  const handleZoomIn = () => {
    if (graphRef.current) graphRef.current.zoom(graphRef.current.zoom() * 1.4, 400);
  };
  const handleZoomOut = () => {
    if (graphRef.current) graphRef.current.zoom(graphRef.current.zoom() / 1.4, 400);
  };
  const handleResetView = () => {
    if (graphRef.current) graphRef.current.zoomToFit(400, 50);
  };

  // Canvas Custom Painters
  const drawNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.name || node.id || "Entity";
    const radius = Math.max((node.val || 4) * 1.8, 6);
    const isSelected = selectedNode?.id === node.id;
    const isDark = theme === "dark";

    // Circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = node.color || "#94a3b8";
    ctx.fill();

    // Halo
    if (isSelected) {
      ctx.lineWidth = 3 / globalScale;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(node.x, node.y, radius + (4 / globalScale), 0, 2 * Math.PI, false);
      ctx.strokeStyle = node.color || "#3b82f6";
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    } else {
      ctx.lineWidth = 1.5 / globalScale;
      ctx.strokeStyle = isDark ? "#0f172a" : "#ffffff";
      ctx.stroke();
    }

    // Label Pill
    const fontSize = Math.max(10 / globalScale, 2.5);
    ctx.font = `500 ${fontSize}px system-ui, -apple-system, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";

    const textWidth = ctx.measureText(label).width;
    const paddingX = 4 / globalScale;
    const paddingY = 2 / globalScale;
    const pillHeight = fontSize + (paddingY * 2);
    const pillWidth = textWidth + (paddingX * 2);
    const pillY = node.y + radius + (3 / globalScale);

    ctx.fillStyle = isDark ? "rgba(15, 23, 42, 0.88)" : "rgba(255, 255, 255, 0.94)";
    ctx.strokeStyle = isDark ? "rgba(51, 65, 85, 0.8)" : "rgba(203, 213, 225, 0.8)";
    ctx.lineWidth = 0.8 / globalScale;
    ctx.beginPath();
    ctx.roundRect(node.x - pillWidth / 2, pillY, pillWidth, pillHeight, 3 / globalScale);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = isDark ? "#f8fafc" : "#0f172a";
    ctx.fillText(label, node.x, pillY + paddingY);
  }, [selectedNode, theme]);

  const paintPointerArea = useCallback((node: any, color: string, ctx: CanvasRenderingContext2D) => {
    const radius = Math.max((node.val || 4) * 1.8, 6) + 4;
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = color;
    ctx.fill();
  }, []);

  const drawLink = useCallback((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    if (globalScale < 1.1 || !link.label) return;
    const start = link.source;
    const end = link.target;
    if (!start || !end || typeof start.x !== "number" || typeof end.x !== "number") return;

    const textPos = {
      x: start.x + (end.x - start.x) * 0.5,
      y: start.y + (end.y - start.y) * 0.5,
    };
    const fontSize = Math.max(8 / globalScale, 2);
    ctx.font = `${fontSize}px system-ui, -apple-system, sans-serif`;
    ctx.fillStyle = theme === "dark" ? "#94a3b8" : "#64748b";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(link.label).replace(/_/g, " "), textPos.x, textPos.y);
  }, [theme]);

  const selectedCase = cases.find(c => c.id === selectedCaseId);

  return (
    <div className="flex flex-col h-[calc(100vh-130px)] space-y-4">
      {/* Top Header & Stats Summary */}
      <header className="flex flex-wrap items-center justify-between gap-4 z-10 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-primary-600 dark:text-primary-400">
              <InterfaceIcon name="network" size={24} />
            </span>
            <h1 className="text-2xl font-bold text-surface-900 dark:text-white">
              Network Analysis
            </h1>
          </div>
          <p className="text-xs text-surface-600 dark:text-surface-300 mt-0.5">
            {selectedCase 
              ? `Investigation: ${selectedCase.case_number ? `[${selectedCase.case_number}] ` : ""}${selectedCase.title}`
              : "Criminal network graph, entity relationships & cross-case linkage intelligence"}
          </p>
        </div>

        {/* Header Stats Bar */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-4 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-lg px-3 py-1.5 text-xs shadow-sm">
            <div>
              <span className="text-surface-500 block text-[10px] uppercase font-semibold">Nodes</span>
              <span className="font-bold text-surface-900 dark:text-white">{graphData.nodes.length}</span>
            </div>
            <div className="border-l border-surface-200 dark:border-surface-700 pl-3">
              <span className="text-surface-500 block text-[10px] uppercase font-semibold">Edges</span>
              <span className="font-bold text-surface-900 dark:text-white">{graphData.links.length}</span>
            </div>
            <div className="border-l border-surface-200 dark:border-surface-700 pl-3">
              <span className="text-surface-500 block text-[10px] uppercase font-semibold">Density</span>
              <span className="font-bold text-surface-900 dark:text-white">
                {graphStats ? `${(graphStats.density * 100).toFixed(1)}%` : "—"}
              </span>
            </div>
            {graphStats?.top_connected_entities?.[0] && (
              <div className="border-l border-surface-200 dark:border-surface-700 pl-3 max-w-[140px] truncate">
                <span className="text-surface-500 block text-[10px] uppercase font-semibold">Top Hub</span>
                <span className="font-bold text-primary-600 dark:text-primary-400 truncate block" title={graphStats.top_connected_entities[0].entity_name}>
                  {graphStats.top_connected_entities[0].entity_name}
                </span>
              </div>
            )}
          </div>

          <Link 
            to="/dashboard"
            className="px-3.5 py-1.5 bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 text-surface-700 dark:text-surface-200 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg text-xs font-medium transition-colors shadow-sm"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      {/* Main Graph Grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-4 min-h-0 z-10 pb-2">
        {/* Graph Canvas Card */}
        <div className="lg:col-span-3 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-4 shadow-sm flex flex-col h-full relative min-h-0">
          
          {/* Controls toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3 shrink-0">
            {/* Case Selector */}
            <div className="flex items-center gap-2">
              <label htmlFor="case-select" className="text-xs font-semibold text-surface-500 uppercase tracking-wider">
                Case:
              </label>
              <select 
                id="case-select"
                value={selectedCaseId} 
                onChange={(e) => {
                  const newId = e.target.value;
                  setSelectedCaseId(newId);
                  setSearchParams({ caseId: newId });
                }}
                className="px-3 py-1.5 bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg text-xs font-medium text-surface-900 dark:text-white max-w-[280px] sm:max-w-[360px] truncate focus:outline-none focus:ring-1 focus:ring-primary-500"
              >
                <option value="" disabled>Select an Investigation Case</option>
                {cases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.case_number ? `[${c.case_number}] ${c.title}` : c.title || c.id}
                  </option>
                ))}
              </select>
            </div>

            {/* Type Filter Chips */}
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={() => setTypeFilter("ALL")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  typeFilter === "ALL"
                    ? "bg-surface-900 text-white dark:bg-white dark:text-surface-900"
                    : "bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300 hover:bg-surface-200"
                }`}
              >
                All ({graphData.nodes.length})
              </button>
              {Object.entries(availableTypes).map(([type, count]) => {
                const color = TYPE_COLORS[type] || "#64748b";
                const isSelected = typeFilter === type;
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setTypeFilter(type)}
                    className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border transition-colors ${
                      isSelected
                        ? "border-primary-500 bg-primary-50 dark:bg-primary-950/50 text-primary-700 dark:text-primary-300"
                        : "border-transparent bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300 hover:bg-surface-200"
                    }`}
                  >
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                    <span>{formatEntityType(type)}</span>
                    <span className="text-[9px] opacity-70">({count})</span>
                  </button>
                );
              })}
            </div>

            {/* Zoom / View Actions */}
            <div className="flex items-center gap-1.5 ml-auto">
              <button onClick={handleZoomIn} className="p-1.5 bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-200 rounded hover:bg-surface-200 dark:hover:bg-surface-700 transition-colors text-xs font-bold" title="Zoom In">＋</button>
              <button onClick={handleZoomOut} className="p-1.5 bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-200 rounded hover:bg-surface-200 dark:hover:bg-surface-700 transition-colors text-xs font-bold" title="Zoom Out">－</button>
              <button onClick={handleResetView} className="px-2 py-1 bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-200 rounded hover:bg-surface-200 dark:hover:bg-surface-700 transition-colors text-xs font-medium" title="Center Network">Fit</button>
              <button 
                onClick={() => fetchGraphData(selectedCaseId)} 
                className="px-2.5 py-1 bg-primary-50 hover:bg-primary-100 text-primary-700 dark:bg-primary-950/40 dark:hover:bg-primary-900/60 dark:text-primary-300 rounded text-xs font-medium transition-colors"
                title="Refresh Graph"
              >
                🔄 Refresh
              </button>
            </div>
          </div>
          
          {/* Canvas container */}
          <div 
            ref={containerRef} 
            className="flex-1 min-h-0 border border-surface-200 dark:border-surface-800 rounded-lg overflow-hidden bg-surface-50/50 dark:bg-surface-950 relative transition-colors h-full w-full shadow-inner"
          >
            {graphStatus === "loading" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-surface-600 dark:text-surface-300 z-20 bg-white/85 dark:bg-surface-950/85 backdrop-blur-xs">
                <div className="w-8 h-8 border-3 border-primary-500 border-t-transparent rounded-full animate-spin mb-3" />
                <p className="font-semibold text-sm">Building Knowledge Graph...</p>
                <p className="text-xs text-surface-500 mt-1">Resolving entities, cross-case links, and associations</p>
              </div>
            )}
            
            {graphStatus === "error" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-danger-600 dark:text-danger-400 z-20 bg-white dark:bg-surface-950 p-6 text-center">
                <p className="text-3xl mb-2">⚠️</p>
                <p className="font-semibold text-sm">Unable to load case network topology.</p>
                <p className="text-xs text-surface-500 mt-1 mb-4">The graph query could not be completed for this case.</p>
                <button 
                  onClick={() => fetchGraphData(selectedCaseId)} 
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg text-xs font-medium hover:bg-primary-700 transition-colors"
                >
                  Retry Analysis
                </button>
              </div>
            )}
            
            {graphStatus === "empty" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-surface-500 dark:text-surface-400 z-20 bg-white dark:bg-surface-950 p-6 text-center">
                <p className="text-3xl mb-2">📭</p>
                <p className="font-semibold text-sm text-surface-800 dark:text-surface-200">No entities extracted for this case.</p>
                <p className="text-xs text-surface-500 mt-1 max-w-sm">Upload FIR documents or CDR/transaction CSVs in Case Intake to populate the graph.</p>
              </div>
            )}

            {graphStatus === "success" && dimensions.width > 0 && dimensions.height > 0 && (
              <ForceGraph2D
                ref={graphRef}
                width={dimensions.width}
                height={dimensions.height}
                graphData={displayedGraphData}
                nodeAutoColorBy="type"
                nodeCanvasObject={drawNode}
                nodePointerAreaPaint={paintPointerArea}
                onNodeClick={(node: any) => {
                  setSelectedNode(node);
                  setActionFeedback(null);
                }}
                linkCanvasObjectMode={() => "after"}
                linkCanvasObject={drawLink}
                linkDirectionalArrowLength={6}
                linkDirectionalArrowRelPos={0.8}
                linkDirectionalArrowColor={() => theme === "dark" ? "#94a3b8" : "#64748b"}
                linkColor={() => theme === "dark" ? "#334155" : "#cbd5e1"}
                linkWidth={1.5}
                backgroundColor={theme === "dark" ? "#020617" : "#f8fafc"}
                cooldownTicks={100}
                onEngineStop={() => {
                  // Optional auto fit once simulation stabilizes
                }}
              />
            )}
          </div>
        </div>

        {/* Entity Profile Sidebar */}
        <aside className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-sm flex flex-col h-full overflow-y-auto transition-colors min-h-0">
          <div className="flex items-center justify-between mb-3 shrink-0">
            <h2 className="text-base font-bold text-surface-900 dark:text-white">
              Entity Dossier
            </h2>
            {selectedNode && (
              <button 
                onClick={() => setSelectedNode(null)} 
                className="text-xs text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
              >
                Clear
              </button>
            )}
          </div>
          
          {!selectedNode ? (
            <div className="flex-1 flex flex-col items-center justify-center text-surface-500 dark:text-surface-400 border border-dashed border-surface-300 dark:border-surface-700 rounded-lg p-6 text-center">
              <span className="text-3xl mb-2 opacity-60">🔍</span>
              <p className="text-xs font-medium text-surface-700 dark:text-surface-300">No Entity Selected</p>
              <p className="text-[11px] text-surface-500 mt-1 max-w-[200px]">
                Click any node on the graph canvas to inspect attributes, confidence, and cross-case connections.
              </p>
            </div>
          ) : (
            <div className="space-y-4 flex-1 flex flex-col min-h-0">
              {/* Primary Identity Pill */}
              <div className="bg-surface-50 dark:bg-surface-800/60 border border-surface-200 dark:border-surface-700 rounded-lg p-3.5 space-y-2 shrink-0">
                <div className="flex items-center justify-between">
                  <span 
                    className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase text-white shadow-xs"
                    style={{ backgroundColor: selectedNode.color || "#3b82f6" }}
                  >
                    {formatEntityType(selectedNode.type)}
                  </span>
                  {selectedNode.type !== "CASE" && (
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                      selectedNode.status === "CONFIRMED"
                        ? "bg-success-50 text-success-700 border-success-200 dark:bg-success-950/40 dark:text-success-400 dark:border-success-800"
                        : selectedNode.status === "REJECTED"
                        ? "bg-danger-50 text-danger-700 border-danger-200 dark:bg-danger-950/40 dark:text-danger-400 dark:border-danger-800"
                        : "bg-warning-50 text-warning-700 border-warning-200 dark:bg-warning-950/40 dark:text-warning-400 dark:border-warning-800"
                    }`}>
                      {selectedNode.status === "CONFIRMED" ? "✓ Confirmed" : selectedNode.status === "REJECTED" ? "✕ Rejected" : "⏳ Pending"}
                    </span>
                  )}
                </div>

                <div className="flex items-baseline justify-between gap-2 pt-1">
                  <p className="text-sm font-bold text-surface-900 dark:text-white break-all leading-tight">
                    {selectedNode.name}
                  </p>
                  <button
                    onClick={() => navigator.clipboard?.writeText(selectedNode.name)}
                    className="text-[10px] text-primary-600 hover:text-primary-700 dark:text-primary-400 shrink-0 underline"
                    title="Copy identifier"
                  >
                    Copy
                  </button>
                </div>

                {selectedNode.confidence !== undefined && (
                  <div className="pt-1">
                    <div className="flex justify-between text-[11px] text-surface-500 mb-1">
                      <span>Extraction Confidence</span>
                      <span className="font-semibold text-surface-800 dark:text-surface-200">
                        {Math.round(selectedNode.confidence * 100)}%
                      </span>
                    </div>
                    <div className="w-full bg-surface-200 dark:bg-surface-700 h-1.5 rounded-full overflow-hidden">
                      <div 
                        className="bg-primary-500 h-full rounded-full transition-all" 
                        style={{ width: `${Math.round(selectedNode.confidence * 100)}%` }} 
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Cross-Case Intelligence Alert */}
              {selectedNode.linkedCaseNames && selectedNode.linkedCaseNames.length > 0 && selectedNode.type !== "CASE" && (
                <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 rounded-lg p-3 space-y-1.5 shrink-0">
                  <div className="flex items-center gap-1.5 text-amber-800 dark:text-amber-300 font-semibold text-xs">
                    <span>🔗</span>
                    <span>Cross-Case Link Detected</span>
                  </div>
                  <p className="text-[11px] text-amber-900 dark:text-amber-200 leading-normal">
                    This identifier is also linked to other investigations:
                  </p>
                  <ul className="text-[11px] space-y-1 text-amber-800 dark:text-amber-300 pl-3 list-disc">
                    {selectedNode.linkedCaseNames.map((linkStr, idx) => (
                      <li key={idx} className="font-medium break-words">{linkStr}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Connected Neighbors in this Network */}
              <div className="flex-1 space-y-2 min-h-0 overflow-y-auto">
                <p className="text-xs font-semibold text-surface-700 dark:text-surface-300 uppercase tracking-wider">
                  Direct Connections ({selectedNeighbors.length})
                </p>

                {selectedNeighbors.length === 0 ? (
                  <p className="text-xs text-surface-500 italic">No direct neighbors found in this subgraph.</p>
                ) : (
                  <div className="space-y-1.5">
                    {selectedNeighbors.map(({ node, edgeLabel }, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => {
                          setSelectedNode(node);
                          setActionFeedback(null);
                        }}
                        className="w-full text-left p-2 rounded-lg border border-surface-200 dark:border-surface-800 bg-surface-50/70 dark:bg-surface-800/40 hover:bg-primary-50 dark:hover:bg-primary-950/40 hover:border-primary-300 transition-colors flex items-center justify-between gap-2"
                      >
                        <div className="min-w-0">
                          <span className="text-[9px] uppercase font-bold tracking-wider text-surface-500 block">
                            {formatEntityType(edgeLabel)}
                          </span>
                          <span className="text-xs font-semibold text-surface-900 dark:text-white truncate block">
                            {node.name}
                          </span>
                        </div>
                        <span 
                          className="w-2.5 h-2.5 rounded-full shrink-0" 
                          style={{ backgroundColor: node.color }} 
                          title={node.type}
                        />
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Entity Actions: Confirm / Reject */}
              {selectedNode.type !== "CASE" && (
                <div className="pt-2 border-t border-surface-200 dark:border-surface-800 shrink-0 space-y-2">
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={actionProcessing || selectedNode.status === "CONFIRMED"}
                      onClick={() => handleEntityAction("confirm")}
                      className="flex-1 py-1.5 px-3 bg-success-600 hover:bg-success-700 disabled:opacity-40 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors"
                    >
                      {actionProcessing ? "Saving..." : "✓ Confirm"}
                    </button>
                    <button
                      type="button"
                      disabled={actionProcessing || selectedNode.status === "REJECTED"}
                      onClick={() => handleEntityAction("reject")}
                      className="flex-1 py-1.5 px-3 bg-danger-600 hover:bg-danger-700 disabled:opacity-40 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors"
                    >
                      {actionProcessing ? "Saving..." : "✕ Reject"}
                    </button>
                  </div>

                  {actionFeedback && (
                    <div className={`p-2 rounded-md text-[11px] leading-tight border ${
                      actionFeedback.type === "success"
                        ? "bg-success-50 text-success-800 border-success-200 dark:bg-success-950/50 dark:text-success-300 dark:border-success-800"
                        : "bg-danger-50 text-danger-800 border-danger-200 dark:bg-danger-950/50 dark:text-danger-300 dark:border-danger-800"
                    }`}>
                      {actionFeedback.message}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

