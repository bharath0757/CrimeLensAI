/**
 * CrimeLensAI — Network Analysis Page
 *
 * Dedicated interactive criminal network visualization.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import ForceGraph2D from "react-force-graph-2d";
import { useTheme } from "../contexts/ThemeContext";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  val?: number; // Size in graph
  color?: string;
  confidence?: number;
  status?: string;
  linkedCaseNames?: string[];
}

interface GraphLink {
  source: string;
  target: string;
}

const TYPE_COLORS: Record<string, string> = {
  CASE: "#6366f1",    // primary-500
  PERSON: "#3b82f6",  // blue-500
  PHONE: "#22c55e",   // green-500
  VEHICLE: "#eab308", // yellow-500
  UPI_ID: "#a855f7",  // purple-500
  LOCATION: "#ef4444",// red-500
  ORG: "#06b6d4"      // cyan-500
};

export function NetworkAnalysis() {
  const { theme } = useTheme();

  const [graphStatus, setGraphStatus] = useState<"loading" | "success" | "error" | "empty">("loading");
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [actionProcessing, setActionProcessing] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 600 });

  // Fetch Graph Data based on existing Cases API since a dedicated Graph API is missing
  const fetchGraphData = useCallback(async () => {
    setGraphStatus("loading");
    setSelectedNode(null);
    setActionFeedback(null);
    try {
      // Integration point: attempting to build network from existing cases
      const casesData = await api.cases.list(0, 100) as any;
      const cases = Array.isArray(casesData) ? casesData : (casesData?.items || []);

      const nodes: GraphNode[] = [];
      const links: GraphLink[] = [];
      const nodeIds = new Set<string>();

      cases.forEach((c: any) => {
        const caseId = c.id || c._id || c.firNumber;
        const caseName = c.title || c.firNumber || "Unknown Case";
        if (!caseId) return;

        if (!nodeIds.has(caseId)) {
          nodes.push({
            id: caseId,
            name: caseName,
            type: "CASE",
            val: 5,
            color: TYPE_COLORS["CASE"]
          });
          nodeIds.add(caseId);
        }

        if (Array.isArray(c.entities)) {
          c.entities.forEach((e: any) => {
            const entId = e.id || e.value;
            if (!entId) return;

            if (!nodeIds.has(entId)) {
              nodes.push({
                id: entId,
                name: e.value,
                type: e.type || "UNKNOWN",
                val: 3,
                confidence: e.confidence,
                status: e.status || "PENDING",
                linkedCaseNames: [caseName],
                color: TYPE_COLORS[e.type] || "#94a3b8" // slate-400 fallback
              });
              nodeIds.add(entId);
            } else {
              // Increment linked cases for entities
              const existingNode = nodes.find(n => n.id === entId);
              if (existingNode && existingNode.type !== "CASE") {
                if (!existingNode.linkedCaseNames) existingNode.linkedCaseNames = [];
                if (!existingNode.linkedCaseNames.includes(caseName)) {
                  existingNode.linkedCaseNames.push(caseName);
                }
              }
            }

            links.push({
              source: caseId,
              target: entId
            });
          });
        }
      });

      if (nodes.length > 0) {
        setGraphData({ nodes, links });
        setGraphStatus("success");
        // Auto zoom to fit after graph loads
        setTimeout(() => {
          if (graphRef.current) {
            graphRef.current.zoomToFit(400, 50);
          }
        }, 800);
      } else {
        setGraphStatus("empty");
      }
    } catch (error) {
      console.error("Failed to fetch graph data:", error);
      setGraphStatus("error");
    }
  }, []);

  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  // Handle Resize for ForceGraph
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: Math.max(containerRef.current.offsetHeight, 600)
        });
      }
    };
    handleResize(); // Initial measurement
    
    // Add a small delay for flexbox calculation to complete
    const timeout = setTimeout(handleResize, 100);
    
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      clearTimeout(timeout);
    };
  }, []);

  const handleEntityAction = async (action: "confirm" | "reject") => {
    if (!selectedNode) return;
    setActionProcessing(true);
    setActionFeedback(null);
    try {
      if (action === "confirm") {
        await api.entities.confirm(selectedNode.id);
        const newStatus = "CONFIRMED";
        setSelectedNode({ ...selectedNode, status: newStatus });
        setGraphData(prev => ({
          ...prev,
          nodes: prev.nodes.map(n => n.id === selectedNode.id ? { ...n, status: newStatus } : n)
        }));
        setActionFeedback({ type: "success", message: "Entity confirmed successfully." });
      } else {
        await api.entities.reject(selectedNode.id);
        const newStatus = "REJECTED";
        setSelectedNode({ ...selectedNode, status: newStatus });
        setGraphData(prev => ({
          ...prev,
          nodes: prev.nodes.map(n => n.id === selectedNode.id ? { ...n, status: newStatus } : n)
        }));
        setActionFeedback({ type: "success", message: "Entity rejected successfully." });
      }
    } catch (error) {
      console.error(error);
      setActionFeedback({ type: "error", message: `Unable to ${action} entity. Please try again.` });
    } finally {
      setActionProcessing(false);
    }
  };

  const handleZoomIn = () => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(currentZoom * 1.5, 400);
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(currentZoom / 1.5, 400);
    }
  };

  const handleResetView = () => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 50);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] space-y-4">
      {/* Page Header */}
      <div className="flex items-center justify-between z-10 relative">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-white transition-colors">Network Analysis</h1>
          <p className="text-surface-600 dark:text-surface-200 mt-1 transition-colors">
            Interactive criminal network visualization
          </p>
        </div>
        <Link 
          to="/dashboard"
          className="px-4 py-2 bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 text-surface-700 dark:text-surface-200 hover:bg-surface-50 dark:hover:bg-surface-700 rounded-lg text-sm font-medium transition-colors shadow-sm dark:shadow-none"
        >
          ← Back to Dashboard
        </Link>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-6 min-h-0 z-10 relative pb-6">
        {/* Graph Visualization */}
        <div className="lg:col-span-3 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-4 shadow-sm dark:shadow-none flex flex-col h-full transition-colors relative">
          
          <div className="flex justify-between items-center mb-4 relative z-10 shrink-0">
            <div className="flex flex-wrap gap-3">
              {Object.entries(TYPE_COLORS).map(([type, color]) => (
                <div key={type} className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                  <span className="text-xs text-surface-600 dark:text-surface-200 font-medium transition-colors">{type}</span>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={handleZoomIn} className="p-1.5 bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300 rounded hover:bg-surface-200 dark:hover:bg-surface-700 transition-colors" title="Zoom In">➕</button>
              <button onClick={handleZoomOut} className="p-1.5 bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300 rounded hover:bg-surface-200 dark:hover:bg-surface-700 transition-colors" title="Zoom Out">➖</button>
              <button onClick={handleResetView} className="p-1.5 bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300 rounded hover:bg-surface-200 dark:hover:bg-surface-700 transition-colors text-xs font-medium px-2" title="Reset View">Reset</button>
              <button 
                onClick={fetchGraphData} 
                className="text-sm px-3 py-1.5 ml-2 bg-surface-100 hover:bg-surface-200 text-surface-600 hover:text-surface-900 dark:bg-surface-800 dark:hover:bg-surface-700 dark:text-surface-200 dark:hover:text-white rounded transition-colors"
                title="Refresh Graph"
              >
                🔄 Refresh
              </button>
            </div>
          </div>
          
          <div ref={containerRef} className="flex-1 min-h-0 border border-surface-200 dark:border-surface-800 rounded-lg overflow-hidden bg-white dark:bg-surface-950 relative transition-colors h-full w-full shadow-inner">
            {graphStatus === "loading" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-surface-600 dark:text-surface-200 z-10 bg-white/80 dark:bg-surface-950/80 transition-colors">
                <p className="text-3xl mb-3 animate-spin">🕸️</p>
                <p className="font-medium">Loading Relationships...</p>
              </div>
            )}
            
            {graphStatus === "error" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-danger-500 z-10 bg-white dark:bg-surface-950 transition-colors">
                <p className="text-3xl mb-3">⚠️</p>
                <p className="font-medium">Unable to load case relationships.</p>
                <button onClick={fetchGraphData} className="mt-4 px-4 py-2 bg-surface-200 hover:bg-surface-300 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-900 dark:text-white rounded-lg text-sm transition-colors">
                  Retry
                </button>
              </div>
            )}
            
            {graphStatus === "empty" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-surface-600 dark:text-surface-200 z-10 bg-white dark:bg-surface-950 transition-colors">
                <p className="text-3xl mb-3">📭</p>
                <p className="font-medium">No case relationships available.</p>
                <p className="text-xs mt-2 text-surface-500 dark:text-surface-400">Ingest more cases to generate the network.</p>
              </div>
            )}

            {graphStatus === "success" && dimensions.width > 0 && dimensions.height > 0 && (
              <ForceGraph2D
                ref={graphRef}
                width={dimensions.width}
                height={dimensions.height}
                graphData={graphData}
                nodeAutoColorBy="type"
                nodeColor={(node: any) => node.color}
                nodeVal={(node: any) => node.val}
                nodeLabel="name"
                onNodeClick={(node: any) => {
                  setSelectedNode(node);
                  setActionFeedback(null);
                }}
                linkColor={() => theme === "light" ? "#e2e8f0" : "#334155"} // slate-200 for light, slate-700 for dark
                backgroundColor={theme === "light" ? "#ffffff" : "#020617"} // white for light, surface-950 for dark
              />
            )}
          </div>
        </div>

        {/* Entity Profile Panel */}
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none flex flex-col h-full overflow-y-auto transition-colors">
          <h2 className="text-lg font-semibold text-surface-900 dark:text-white mb-4 transition-colors shrink-0">Selected Entity</h2>
          
          {!selectedNode ? (
            <div className="flex-1 flex flex-col items-center justify-center text-surface-500 dark:text-surface-400 border border-dashed border-surface-300 dark:border-surface-700 rounded-lg transition-colors p-6">
              <p className="text-4xl mb-3">🔍</p>
              <p className="text-sm text-center px-4">Select an entity from the graph to view details.</p>
            </div>
          ) : (
            <div className="space-y-4 flex-1">
              <p className="text-sm text-surface-600 dark:text-surface-200 transition-colors">
                Review extracted entity and connections.
              </p>
              
              <div className="border-t border-surface-200 dark:border-surface-800 pt-4 space-y-3 transition-colors">
                <div className="bg-surface-50 border border-surface-100 dark:border-transparent dark:bg-surface-800/50 rounded-lg p-3 transition-colors">
                  <p className="text-xs text-surface-500 dark:text-surface-200">Node Type</p>
                  <p className="text-sm font-medium text-surface-900 dark:text-white break-words transition-colors">{selectedNode.type}</p>
                </div>
                <div className="bg-surface-50 border border-surface-100 dark:border-transparent dark:bg-surface-800/50 rounded-lg p-3 transition-colors">
                  <p className="text-xs text-surface-500 dark:text-surface-200">Value / Name</p>
                  <p className="text-sm font-medium text-surface-900 dark:text-white break-all transition-colors">{selectedNode.name}</p>
                </div>
                
                {selectedNode.type !== "CASE" && (
                  <>
                    <div className="bg-surface-50 border border-surface-100 dark:border-transparent dark:bg-surface-800/50 rounded-lg p-3 transition-colors">
                      <p className="text-xs text-surface-500 dark:text-surface-200">Confidence</p>
                      <p className="text-sm font-medium text-surface-900 dark:text-white transition-colors">
                        {selectedNode.confidence !== undefined ? `${Math.round(selectedNode.confidence * 100)}%` : "—"}
                      </p>
                    </div>
                    
                    <div className="bg-surface-50 border border-surface-100 dark:border-transparent dark:bg-surface-800/50 rounded-lg p-3 transition-colors">
                      <p className="text-xs text-surface-500 dark:text-surface-200">Status</p>
                      <div className="mt-1">
                        {selectedNode.status === "CONFIRMED" ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-success-50 text-success-700 border border-success-200 dark:bg-success-500/10 dark:text-success-500 dark:border-success-500/20">
                            Confirmed
                          </span>
                        ) : selectedNode.status === "REJECTED" ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-danger-50 text-danger-700 border border-danger-200 dark:bg-danger-500/10 dark:text-danger-500 dark:border-danger-500/20">
                            Rejected
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-warning-50 text-warning-700 border border-warning-200 dark:bg-warning-500/10 dark:text-warning-500 dark:border-warning-500/20">
                            Pending Review
                          </span>
                        )}
                      </div>
                    </div>
                  </>
                )}
                
                <div className="bg-surface-50 border border-surface-100 dark:border-transparent dark:bg-surface-800/50 rounded-lg p-3 transition-colors">
                  <p className="text-xs text-surface-500 dark:text-surface-200 mb-1">Linked Cases</p>
                  {selectedNode.type === "CASE" ? (
                    <p className="text-sm text-surface-700 dark:text-surface-300 transition-colors">Self</p>
                  ) : (
                    <ul className="text-sm font-medium text-surface-900 dark:text-white list-disc list-inside space-y-1 transition-colors">
                      {selectedNode.linkedCaseNames?.map((caseName, idx) => (
                        <li key={idx} className="truncate">{caseName}</li>
                      )) || <p className="text-sm text-surface-700 dark:text-surface-300">—</p>}
                    </ul>
                  )}
                </div>
              </div>
              
              {/* Confirm / Reject Actions */}
              {selectedNode.type !== "CASE" && (
                <div className="pt-2">
                  <div className="flex gap-3">
                    <button
                      disabled={actionProcessing || selectedNode.status === "CONFIRMED"}
                      className="flex-1 px-4 py-2 bg-success-100 text-success-700 hover:bg-success-200 dark:bg-success-600/20 dark:text-success-500 dark:hover:bg-success-600/30 rounded-lg text-sm font-medium border border-success-200 dark:border-success-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      onClick={() => handleEntityAction("confirm")}
                    >
                      {actionProcessing ? "Processing..." : "✓ Confirm"}
                    </button>
                    <button
                      disabled={actionProcessing || selectedNode.status === "REJECTED"}
                      className="flex-1 px-4 py-2 bg-danger-100 text-danger-700 hover:bg-danger-200 dark:bg-danger-600/20 dark:text-danger-500 dark:hover:bg-danger-600/30 rounded-lg text-sm font-medium border border-danger-200 dark:border-danger-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      onClick={() => handleEntityAction("reject")}
                    >
                      {actionProcessing ? "Processing..." : "✕ Reject"}
                    </button>
                  </div>
                  
                  {actionFeedback && (
                    <div className={`mt-3 p-3 rounded-lg text-sm ${
                      actionFeedback.type === "success" 
                        ? "bg-success-50 text-success-700 border-success-200 dark:bg-success-500/10 dark:text-success-500 dark:border-success-500/20 border" 
                        : "bg-danger-50 text-danger-700 border-danger-200 dark:bg-danger-500/10 dark:text-danger-500 dark:border-danger-500/20 border"
                    }`}>
                      {actionFeedback.message}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
