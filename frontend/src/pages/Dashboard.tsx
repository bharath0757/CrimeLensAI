/**
 * CrimeLensAI — Dashboard Page
 *
 * Investigator Dashboard: stat cards showing key metrics,
 * collapsible overview, and a link to the detailed Network Analysis workspace.
 */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

interface StatData {
  totalCases: number;
  entitiesExtracted: number;
  crossCaseLinks: number;
  pendingReviews: number | null;
}

export function Dashboard() {
  const [statsData, setStatsData] = useState<StatData>({
    totalCases: 0,
    entitiesExtracted: 0,
    crossCaseLinks: 0,
    pendingReviews: null,
  });
  const [statsStatus, setStatsStatus] = useState<"loading" | "success" | "error">("loading");
  const [isOverviewExpanded, setIsOverviewExpanded] = useState(true);

  // Fetch Dashboard Stats
  useEffect(() => {
    const fetchStats = async () => {
      setStatsStatus("loading");
      try {
        const data = await api.dashboard.stats() as any;
        setStatsData({
          totalCases: data.totalCases ?? 0,
          entitiesExtracted: data.entitiesExtracted ?? 0,
          crossCaseLinks: data.crossCaseLinks ?? 0,
          pendingReviews: data.pendingReviews ?? 0,
        });
        setStatsStatus("success");
      } catch (error) {
        console.error("Failed to fetch dashboard stats:", error);
        setStatsStatus("error");
      }
    };
    fetchStats();
  }, []);

  const stats = [
    { label: "Total Cases", value: statsStatus === "error" ? "—" : statsStatus === "loading" ? "..." : statsData.totalCases.toString(), icon: "📁", color: "from-primary-500 to-primary-700", borderClass: "border-t-primary-500 dark:border-t-transparent" },
    { label: "Entities Extracted", value: statsStatus === "error" ? "—" : statsStatus === "loading" ? "..." : statsData.entitiesExtracted.toString(), icon: "🔍", color: "from-emerald-500 to-emerald-700", borderClass: "border-t-emerald-500 dark:border-t-transparent" },
    { label: "Cross-Case Links", value: statsStatus === "error" ? "—" : statsStatus === "loading" ? "..." : statsData.crossCaseLinks.toString(), icon: "🔗", color: "from-amber-500 to-amber-700", borderClass: "border-t-amber-500 dark:border-t-transparent" },
    { label: "Pending Reviews", value: statsStatus === "error" ? "—" : statsStatus === "loading" ? "..." : statsData.pendingReviews !== null ? statsData.pendingReviews.toString() : 'N/A', icon: "⏳", color: "from-rose-500 to-rose-700", borderClass: "border-t-rose-500 dark:border-t-transparent" },
  ];

  return (
    <div className="space-y-8 relative z-10">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-white transition-colors">Investigator Dashboard</h1>
        <p className="text-surface-600 dark:text-surface-200 mt-1 transition-colors">
          Clean investigator overview
        </p>
      </div>

      {/* Collapsible Overview Header */}
      <div className="flex items-center justify-between border-b border-surface-200 dark:border-surface-800 pb-2">
        <h2 className="text-lg font-semibold text-surface-900 dark:text-white transition-colors">Dashboard Overview</h2>
        <button 
          onClick={() => setIsOverviewExpanded(!isOverviewExpanded)}
          className="text-sm font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 rounded px-2 py-1"
          aria-label={isOverviewExpanded ? "Collapse dashboard overview" : "Expand dashboard overview"}
          aria-expanded={isOverviewExpanded}
        >
          {isOverviewExpanded ? "[Collapse]" : "[Expand]"}
        </button>
      </div>

      {/* Expandable Content */}
      {isOverviewExpanded && (
        <div className="space-y-8 animate-in fade-in slide-in-from-top-2 duration-300">
          {/* Stat Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className={`bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none hover:shadow-md dark:hover:shadow-none hover:border-primary-500/30 dark:hover:border-primary-500/30 transition-all duration-300 border-t-4 ${stat.borderClass}`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-surface-600 dark:text-surface-200 transition-colors">{stat.label}</p>
                    <p className="text-3xl font-bold mt-2 bg-gradient-to-r bg-clip-text text-transparent" style={{ backgroundImage: `linear-gradient(to right, var(--tw-gradient-stops))` }}>
                      {stat.value}
                    </p>
                  </div>
                  <span className="text-3xl">{stat.icon}</span>
                </div>
              </div>
            ))}
          </div>
          
          <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors">
            <h3 className="font-medium text-surface-900 dark:text-white mb-2">Summary / Important Info</h3>
            <p className="text-sm text-surface-600 dark:text-surface-300">
              Your pending reviews are currently tracking {statsData.pendingReviews !== null ? statsData.pendingReviews : 'an unknown number of'} entities. Prioritize these for validation to improve the graph accuracy.
            </p>
          </div>
        </div>
      )}

      {/* Call to Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Network Analysis Call to Action */}
        <div className="bg-gradient-to-r from-primary-50 to-indigo-50 dark:from-primary-900/20 dark:to-indigo-900/20 border border-primary-100 dark:border-primary-500/20 rounded-xl p-8 shadow-sm text-center flex flex-col items-center transition-colors">
          <h2 className="text-xl font-bold text-surface-900 dark:text-white mb-2">Explore the Network</h2>
          <p className="text-surface-600 dark:text-surface-300 mb-6 text-sm flex-1">
            Dive into the interactive criminal network visualization to examine case linkages, nodes, and entity profiles in a dedicated workspace.
          </p>
          <Link 
            to="/network"
            className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-medium shadow-md shadow-primary-500/20 transition-all focus:outline-none focus:ring-4 focus:ring-primary-500/30 w-full md:w-auto"
          >
            Open Network Analysis
          </Link>
        </div>

        {/* Case Linkage Call to Action */}
        <div className="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 border border-emerald-100 dark:border-emerald-500/20 rounded-xl p-8 shadow-sm text-center flex flex-col items-center transition-colors">
          <h2 className="text-xl font-bold text-surface-900 dark:text-white mb-2">Discover Case Linkages</h2>
          <p className="text-surface-600 dark:text-surface-300 mb-6 text-sm flex-1">
            Investigate explicit connections between cases. Identify shared entities, locations, and personnel driving multi-case criminal activity.
          </p>
          <Link 
            to="/case-linkage"
            className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium shadow-md shadow-emerald-500/20 transition-all focus:outline-none focus:ring-4 focus:ring-emerald-500/30 w-full md:w-auto"
          >
            Explore Case Linkages
          </Link>
        </div>
      </div>

    </div>
  );
}
