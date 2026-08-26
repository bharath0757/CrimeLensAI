/**
 * CrimeLensAI — Dashboard Page
 *
 * Investigator Dashboard: stat cards showing key metrics,
 * case linkage graph visualization placeholder (Cytoscape.js / react-force-graph),
 * and entity profile panel with confirm/reject actions.
 */

export function Dashboard() {
  // Placeholder stats — will be fetched from /api/v1/dashboard/stats
  const stats = [
    { label: "Total Cases", value: "0", icon: "📁", color: "from-primary-500 to-primary-700" },
    { label: "Entities Extracted", value: "0", icon: "🔍", color: "from-emerald-500 to-emerald-700" },
    { label: "Cross-Case Links", value: "0", icon: "🔗", color: "from-amber-500 to-amber-700" },
    { label: "Pending Reviews", value: "0", icon: "⏳", color: "from-rose-500 to-rose-700" },
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Investigator Dashboard</h1>
        <p className="text-surface-200 mt-1">
          Overview of case activity, entity extraction, and cross-case linkages.
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-surface-900 border border-surface-800 rounded-xl p-6 hover:border-primary-500/30 transition-all duration-300"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-surface-200">{stat.label}</p>
                <p className="text-3xl font-bold mt-2 bg-gradient-to-r bg-clip-text text-transparent" style={{ backgroundImage: `linear-gradient(to right, var(--tw-gradient-stops))` }}>
                  {stat.value}
                </p>
              </div>
              <span className="text-3xl">{stat.icon}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Case Linkage Graph + Entity Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Graph Visualization Placeholder */}
        <div className="lg:col-span-2 bg-surface-900 border border-surface-800 rounded-xl p-6 min-h-[400px]">
          <h2 className="text-lg font-semibold text-white mb-4">Case Linkage Network</h2>
          <div className="flex items-center justify-center h-80 border-2 border-dashed border-surface-700 rounded-lg">
            <div className="text-center text-surface-200">
              <p className="text-4xl mb-3">🕸️</p>
              <p className="font-medium">Graph Visualization</p>
              <p className="text-sm mt-1">
                Wire up Cytoscape.js or react-force-graph here.
              </p>
              <p className="text-xs mt-2 text-surface-200">
                Displays entity nodes and cross-case relationships
              </p>
            </div>
          </div>
        </div>

        {/* Entity Profile Panel */}
        <div className="bg-surface-900 border border-surface-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Entity Profile</h2>
          <div className="space-y-4">
            <p className="text-sm text-surface-200">
              Select an entity from the graph to view its profile, linked cases,
              and take confirm/reject actions.
            </p>
            <div className="border-t border-surface-800 pt-4 space-y-3">
              <div className="bg-surface-800/50 rounded-lg p-3">
                <p className="text-xs text-surface-200">Entity Type</p>
                <p className="text-sm font-medium">—</p>
              </div>
              <div className="bg-surface-800/50 rounded-lg p-3">
                <p className="text-xs text-surface-200">Value</p>
                <p className="text-sm font-medium">—</p>
              </div>
              <div className="bg-surface-800/50 rounded-lg p-3">
                <p className="text-xs text-surface-200">Confidence</p>
                <p className="text-sm font-medium">—</p>
              </div>
              <div className="bg-surface-800/50 rounded-lg p-3">
                <p className="text-xs text-surface-200">Linked Cases</p>
                <p className="text-sm font-medium">—</p>
              </div>
            </div>
            {/* Confirm / Reject Actions */}
            <div className="flex gap-3 pt-2">
              <button
                disabled
                className="flex-1 px-4 py-2 bg-success-600/20 text-success-500 rounded-lg text-sm font-medium border border-success-500/30 disabled:opacity-50 cursor-not-allowed"
              >
                ✓ Confirm
              </button>
              <button
                disabled
                className="flex-1 px-4 py-2 bg-danger-600/20 text-danger-500 rounded-lg text-sm font-medium border border-danger-500/30 disabled:opacity-50 cursor-not-allowed"
              >
                ✕ Reject
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
