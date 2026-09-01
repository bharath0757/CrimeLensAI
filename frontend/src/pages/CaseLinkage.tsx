/**
 * CrimeLensAI — Case Linkage Page
 *
 * Dedicated page to discover connections between investigations.
 */

import { useState, useEffect, useRef, useMemo } from "react";
import { api } from "../lib/api";
import ForceGraph2D from "react-force-graph-2d";
import { useTheme } from "../contexts/ThemeContext";

interface RelatedCase {
  caseId: string;
  caseTitle: string;
  entityName: string;
  entityType: string;
  status: string;
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

export function CaseLinkage() {
  const { theme } = useTheme();

  const [cases, setCases] = useState<any[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error" | "empty">("loading");
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");

  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 400 });

  useEffect(() => {
    const fetchCases = async () => {
      setStatus("loading");
      try {
        const casesData = await api.cases.list(0, 100) as any;
        const items = Array.isArray(casesData) ? casesData : (casesData?.items || []);
        if (items.length > 0) {
          setCases(items);
          setStatus("success");
        } else {
          setStatus("empty");
        }
      } catch (error) {
        console.error("Failed to fetch cases for linkage:", error);
        setStatus("error");
      }
    };
    fetchCases();
  }, []);

  // Handle Resize for ForceGraph
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: Math.max(containerRef.current.offsetHeight, 300)
        });
      }
    };
    handleResize();
    const timeout = setTimeout(handleResize, 100);
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      clearTimeout(timeout);
    };
  }, [selectedCaseId]);

  const filteredCases = useMemo(() => {
    if (!searchQuery.trim()) return cases;
    const lowerQ = searchQuery.toLowerCase();
    return cases.filter(c => {
      const id = c.id || c._id || c.firNumber || "";
      const title = c.title || c.firNumber || "";
      return id.toLowerCase().includes(lowerQ) || title.toLowerCase().includes(lowerQ);
    });
  }, [cases, searchQuery]);

  const selectedCase = useMemo(() => {
    if (!selectedCaseId) return null;
    return cases.find(c => (c.id || c._id || c.firNumber) === selectedCaseId);
  }, [cases, selectedCaseId]);

  const relationships = useMemo(() => {
    // NOTE: The backend API gateway does not expose the graph linkage endpoint.
    // Frontend entity-comparison linkage has been removed to avoid masking the missing backend feature.
    return [] as RelatedCase[];
  }, [selectedCase, cases]);

  const graphData = useMemo(() => {
    if (!selectedCase) return { nodes: [], links: [] };

    const nodes: any[] = [];
    const links: any[] = [];
    const nodeIds = new Set<string>();

    const myCaseId = selectedCase.id || selectedCase._id || selectedCase.firNumber;
    const myCaseTitle = selectedCase.title || selectedCase.firNumber || "Unknown Case";

    // Add selected case node
    nodes.push({
      id: myCaseId,
      name: myCaseTitle,
      type: "SELECTED_CASE",
      val: 8,
      color: TYPE_COLORS["CASE"]
    });
    nodeIds.add(myCaseId);

    relationships.forEach(rel => {
      // Add entity node
      const entId = `${rel.entityType}-${rel.entityName}`;
      if (!nodeIds.has(entId)) {
        nodes.push({
          id: entId,
          name: rel.entityName,
          type: rel.entityType,
          val: 4,
          color: TYPE_COLORS[rel.entityType] || "#94a3b8"
        });
        nodeIds.add(entId);

        // Link from Selected Case to Entity
        links.push({
          source: myCaseId,
          target: entId
        });
      }

      // Add related case node
      if (!nodeIds.has(rel.caseId)) {
        nodes.push({
          id: rel.caseId,
          name: rel.caseTitle,
          type: "RELATED_CASE",
          val: 6,
          color: "#94a3b8" // distinct color for related cases
        });
        nodeIds.add(rel.caseId);
      }

      // Link from Entity to Related Case
      // Avoid duplicate links
      const linkExists = links.some(l => l.source === entId && l.target === rel.caseId);
      if (!linkExists) {
        links.push({
          source: entId,
          target: rel.caseId
        });
      }
    });

    return { nodes, links };
  }, [selectedCase, relationships]);
  
  useEffect(() => {
      // Auto zoom to fit when graph updates
      if (graphRef.current && graphData.nodes.length > 0) {
        setTimeout(() => {
            if (graphRef.current) {
                graphRef.current.zoomToFit(400, 50);
            }
        }, 600);
      }
  }, [graphData]);

  if (status === "loading") {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-surface-600 dark:text-surface-200">
        <p className="text-3xl mb-3 animate-spin">🕸️</p>
        <p className="font-medium">Loading case linkages...</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-danger-500">
        <p className="text-3xl mb-3">⚠️</p>
        <p className="font-medium">Unable to load cases.</p>
        <button onClick={() => window.location.reload()} className="mt-4 px-4 py-2 bg-surface-200 hover:bg-surface-300 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-900 dark:text-white rounded-lg text-sm transition-colors">
          Retry
        </button>
      </div>
    );
  }

  if (status === "empty" || cases.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-surface-600 dark:text-surface-200">
        <p className="text-3xl mb-3">📭</p>
        <p className="font-medium text-lg">No cases available</p>
        <p className="text-sm mt-2 text-surface-500 dark:text-surface-400">Ingest cases to begin finding linkages.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] space-y-4">
      {/* Page Header */}
      <div className="flex items-center justify-between z-10 relative shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-white transition-colors">Case Linkage</h1>
          <p className="text-surface-600 dark:text-surface-200 mt-1 transition-colors">
            Discover connections between investigations
          </p>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0 z-10 relative pb-6">
        
        {/* Left Column: Search & Selected Case */}
        <div className="lg:col-span-4 flex flex-col space-y-4 h-full">
          {/* Search / Select Case */}
          <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors shrink-0">
            <h2 className="text-lg font-semibold text-surface-900 dark:text-white mb-4 transition-colors">Select Case</h2>
            <input
              type="text"
              placeholder="Search by ID or Title..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-surface-50 dark:bg-surface-950 border border-surface-200 dark:border-surface-700 rounded-lg px-4 py-2 text-surface-900 dark:text-white mb-4 focus:ring-2 focus:ring-primary-500 focus:outline-none transition-colors"
            />
            
            <div className="max-h-48 overflow-y-auto space-y-2 border border-surface-200 dark:border-surface-700 rounded-lg p-2 bg-surface-50 dark:bg-surface-950 transition-colors">
              {filteredCases.map(c => {
                const cId = c.id || c._id || c.firNumber;
                const cTitle = c.title || c.firNumber || "Unknown Case";
                const isSelected = cId === selectedCaseId;
                return (
                  <button
                    key={cId}
                    onClick={() => setSelectedCaseId(cId)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isSelected 
                        ? "bg-primary-100 text-primary-800 dark:bg-primary-600/30 dark:text-primary-300 border border-primary-200 dark:border-primary-500/30" 
                        : "text-surface-700 dark:text-surface-300 hover:bg-surface-200 dark:hover:bg-surface-800 border border-transparent"
                    }`}
                  >
                    {cTitle} <span className="text-xs opacity-70 ml-1">({cId})</span>
                  </button>
                );
              })}
              {filteredCases.length === 0 && (
                <p className="text-sm text-surface-500 p-2 text-center">No matching cases.</p>
              )}
            </div>
          </div>

          {/* Selected Case Details */}
          {selectedCase && (
            <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors flex-1 overflow-y-auto">
              <h2 className="text-lg font-semibold text-surface-900 dark:text-white mb-4 transition-colors">Selected Case</h2>
              <div className="space-y-3">
                <div className="bg-surface-50 border border-surface-100 dark:border-transparent dark:bg-surface-800/50 rounded-lg p-3 transition-colors">
                  <p className="text-xs text-surface-500 dark:text-surface-200">Case ID</p>
                  <p className="text-sm font-medium text-surface-900 dark:text-white break-words transition-colors">
                    {selectedCase.id || selectedCase._id || selectedCase.firNumber}
                  </p>
                </div>
                <div className="bg-surface-50 border border-surface-100 dark:border-transparent dark:bg-surface-800/50 rounded-lg p-3 transition-colors">
                  <p className="text-xs text-surface-500 dark:text-surface-200">Case Title</p>
                  <p className="text-sm font-medium text-surface-900 dark:text-white break-all transition-colors">
                    {selectedCase.title || selectedCase.firNumber || "Unknown Case"}
                  </p>
                </div>
                <div className="bg-surface-50 border border-surface-100 dark:border-transparent dark:bg-surface-800/50 rounded-lg p-3 transition-colors">
                  <p className="text-xs text-surface-500 dark:text-surface-200">Status</p>
                  <p className="text-sm font-medium text-surface-900 dark:text-white transition-colors">
                    {selectedCase.status || "OPEN"}
                  </p>
                </div>
                <div className="bg-surface-50 border border-surface-100 dark:border-transparent dark:bg-surface-800/50 rounded-lg p-3 transition-colors">
                  <p className="text-xs text-surface-500 dark:text-surface-200">Related Case Count</p>
                  <p className="text-sm font-medium text-surface-900 dark:text-white transition-colors">
                    {new Set(relationships.map(r => r.caseId)).size}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Related Cases & Graph */}
        <div className="lg:col-span-8 flex flex-col space-y-4 h-full">
          
          {selectedCase ? (
            <>
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 mb-4 text-amber-800 dark:text-amber-200">
                <p className="font-medium">Backend Limitation</p>
                <p className="text-sm">The backend API gateway does not currently expose the graph linkage endpoint. Cross-case linkage analysis is unavailable.</p>
              </div>
              {/* Related Cases List */}
              <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors shrink-0 max-h-64 overflow-y-auto">
                <h2 className="text-lg font-semibold text-surface-900 dark:text-white mb-4 transition-colors">Related Cases</h2>
                
                {relationships.length === 0 ? (
                  <div className="py-6 flex flex-col items-center justify-center text-surface-500 dark:text-surface-400">
                    <p className="text-2xl mb-2">🔗</p>
                    <p className="font-medium text-surface-900 dark:text-white">No case linkages found</p>
                    <p className="text-sm text-center">No confirmed connections are currently available for this case.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {relationships.map((rel, idx) => (
                      <div key={idx} className="bg-surface-50 dark:bg-surface-950 border border-surface-200 dark:border-surface-700 rounded-lg p-4 transition-colors flex flex-col">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-medium bg-primary-100 text-primary-800 dark:bg-primary-900/50 dark:text-primary-300 px-2 py-0.5 rounded truncate max-w-[40%]">
                            {selectedCase.title || selectedCase.firNumber}
                          </span>
                          <span className="text-surface-400 dark:text-surface-600 text-xs">→</span>
                          <span className="text-xs font-medium bg-surface-200 text-surface-800 dark:bg-surface-800 dark:text-surface-300 px-2 py-0.5 rounded truncate max-w-[40%]">
                            {rel.caseTitle}
                          </span>
                        </div>
                        <div className="mt-2 space-y-1">
                          <p className="text-xs text-surface-500 dark:text-surface-400">
                            Shared Entity: <span className="font-semibold text-surface-900 dark:text-white">{rel.entityName}</span>
                          </p>
                          <p className="text-xs text-surface-500 dark:text-surface-400">
                            Relationship: <span className="font-semibold text-surface-900 dark:text-white">Shared {rel.entityType}</span>
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Case Relationship Graph */}
              {relationships.length > 0 && (
                <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-4 shadow-sm dark:shadow-none flex flex-col transition-colors relative flex-1 min-h-0">
                  <div className="flex justify-between items-center mb-2 shrink-0">
                    <h2 className="text-lg font-semibold text-surface-900 dark:text-white transition-colors">Case Relationship Graph</h2>
                    <button 
                      onClick={() => { if (graphRef.current) graphRef.current.zoomToFit(400, 50); }}
                      className="text-xs font-medium px-2 py-1 bg-surface-100 hover:bg-surface-200 text-surface-600 dark:bg-surface-800 dark:hover:bg-surface-700 dark:text-surface-300 rounded transition-colors"
                    >
                      Reset View
                    </button>
                  </div>
                  <div ref={containerRef} className="flex-1 border border-surface-200 dark:border-surface-800 rounded-lg overflow-hidden bg-white dark:bg-surface-950 relative transition-colors w-full shadow-inner">
                    {dimensions.width > 0 && dimensions.height > 0 && (
                      <ForceGraph2D
                        ref={graphRef}
                        width={dimensions.width}
                        height={dimensions.height}
                        graphData={graphData}
                        nodeAutoColorBy="type"
                        nodeColor={(node: any) => node.color}
                        nodeVal={(node: any) => node.val}
                        nodeLabel="name"
                        linkColor={() => theme === "light" ? "#cbd5e1" : "#334155"} // slate-300 for light, slate-700 for dark
                        backgroundColor={theme === "light" ? "#ffffff" : "#020617"} // white for light, surface-950 for dark
                        linkDirectionalArrowLength={3.5}
                        linkDirectionalArrowRelPos={1}
                        d3VelocityDecay={0.3} // stabilizes the localized graph faster
                      />
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none h-full flex flex-col items-center justify-center transition-colors">
              <p className="text-4xl mb-4">🔗</p>
              <h2 className="text-xl font-semibold text-surface-900 dark:text-white mb-2 transition-colors">Select a Case</h2>
              <p className="text-sm text-surface-600 dark:text-surface-400 text-center max-w-md">
                Please select an investigation from the list to discover and visualize connections, shared entities, and related cases.
              </p>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
