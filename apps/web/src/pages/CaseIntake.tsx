/**
 * CrimeLensAI — Case Intake Page
 *
 * Case intake form with live entity extraction preview.
 * As the investigator types or pastes FIR text, the extraction
 * service highlights entities in real-time.
 */

import { useState } from "react";

export function CaseIntake() {
  const [firText, setFirText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);

  const handleExtract = async () => {
    setIsExtracting(true);
    // TODO: Call /api/v1/extract with firText
    // For now, simulate a delay
    setTimeout(() => setIsExtracting(false), 1000);
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Case Intake</h1>
        <p className="text-surface-200 mt-1">
          Submit new case data for entity extraction and cross-case analysis.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="space-y-6">
          {/* Case Title */}
          <div className="bg-surface-900 border border-surface-800 rounded-xl p-6">
            <label className="block text-sm font-medium text-surface-200 mb-2">
              Case Title
            </label>
            <input
              type="text"
              placeholder="e.g., Missing Person Report — Lucknow District"
              className="w-full px-4 py-3 bg-surface-800 border border-surface-700 rounded-lg text-white placeholder-surface-200 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
            />
          </div>

          {/* FIR Text */}
          <div className="bg-surface-900 border border-surface-800 rounded-xl p-6">
            <label className="block text-sm font-medium text-surface-200 mb-2">
              FIR Text / Case Narrative
            </label>
            <textarea
              value={firText}
              onChange={(e) => setFirText(e.target.value)}
              placeholder="Paste the FIR text here. The system will extract entities (persons, phone numbers, vehicles, UPI IDs, locations) in real-time..."
              rows={10}
              className="w-full px-4 py-3 bg-surface-800 border border-surface-700 rounded-lg text-white placeholder-surface-200 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors resize-none font-mono text-sm"
            />
            <div className="flex justify-between items-center mt-3">
              <span className="text-xs text-surface-200">
                {firText.length} characters
              </span>
              <button
                onClick={handleExtract}
                disabled={!firText.trim() || isExtracting}
                className="px-6 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-surface-700 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
              >
                {isExtracting ? "Extracting..." : "🔍 Extract Entities"}
              </button>
            </div>
          </div>

          {/* Additional Data Sources */}
          <div className="bg-surface-900 border border-surface-800 rounded-xl p-6">
            <h3 className="text-sm font-medium text-surface-200 mb-4">
              Additional Data Sources (Optional)
            </h3>
            <div className="space-y-4">
              {["Call Records (CSV)", "Financial Transaction Logs", "Location Data"].map(
                (label) => (
                  <div key={label}>
                    <label className="block text-xs text-surface-200 mb-1">
                      {label}
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        type="file"
                        className="flex-1 text-sm text-surface-200 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-surface-800 file:text-surface-200 hover:file:bg-surface-700 file:cursor-pointer"
                      />
                    </div>
                  </div>
                )
              )}
            </div>
          </div>
        </div>

        {/* Live Extraction Preview */}
        <div className="bg-surface-900 border border-surface-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4">
            🔍 Live Extraction Preview
          </h2>
          <div className="space-y-4">
            <p className="text-sm text-surface-200">
              Entities will appear here as they are extracted from the input text.
              Each entity shows its type, confidence score, and source position.
            </p>

            {/* Entity type legend */}
            <div className="flex flex-wrap gap-2">
              {[
                { type: "PERSON", color: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
                { type: "PHONE", color: "bg-green-500/20 text-green-300 border-green-500/30" },
                { type: "VEHICLE", color: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" },
                { type: "UPI_ID", color: "bg-purple-500/20 text-purple-300 border-purple-500/30" },
                { type: "LOCATION", color: "bg-red-500/20 text-red-300 border-red-500/30" },
                { type: "ORG", color: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30" },
              ].map(({ type, color }) => (
                <span
                  key={type}
                  className={`px-2 py-1 rounded text-xs font-medium border ${color}`}
                >
                  {type}
                </span>
              ))}
            </div>

            {/* Extraction results placeholder */}
            <div className="border-t border-surface-800 pt-4">
              <div className="flex items-center justify-center h-60 border-2 border-dashed border-surface-700 rounded-lg">
                <div className="text-center text-surface-200">
                  <p className="text-3xl mb-2">📋</p>
                  <p className="text-sm">
                    {firText.trim()
                      ? "Click 'Extract Entities' to preview results"
                      : "Enter FIR text to begin extraction"}
                  </p>
                </div>
              </div>
            </div>

            {/* Submit Case Button */}
            <button
              disabled
              className="w-full px-6 py-3 bg-primary-600 hover:bg-primary-700 disabled:bg-surface-700 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
            >
              Submit Case for Analysis
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
