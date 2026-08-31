/**
 * CrimeLensAI — Case Intake Page
 *
 * Case intake form with live entity extraction preview.
 * As the investigator types or pastes FIR text, the extraction
 * service highlights entities in real-time.
 */

import { useState } from "react";
import { api } from "../lib/api";

type EntityType = "PERSON" | "PHONE" | "VEHICLE" | "UPI_ID" | "LOCATION" | "ORG";

interface ExtractedEntity {
  id: string;
  type: EntityType;
  value: string;
  confidence: number;
}

export function CaseIntake() {
  const [metadata, setMetadata] = useState({
    title: "",
    firNumber: "",
    district: "",
    filedDate: "",
    category: "",
  });
  const [firText, setFirText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedEntities, setExtractedEntities] = useState<ExtractedEntity[]>([]);
  const [extractionStatus, setExtractionStatus] = useState<"idle" | "loading" | "success" | "error" | "empty">("idle");
  const [extractionError, setExtractionError] = useState<string | null>(null);

  const [files, setFiles] = useState<Record<string, File | null>>({
    callRecords: null,
    financialLogs: null,
    locationData: null,
  });

  const [submitStatus, setSubmitStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleMetadataChange = (field: string, value: string) => {
    setMetadata((prev) => ({ ...prev, [field]: value }));
  };

  const handleFileChange = (key: string, file: File | null) => {
    setFiles((prev) => ({ ...prev, [key]: file }));
  };

  const handleExtract = async () => {
    setIsExtracting(true);
    setExtractionStatus("loading");
    setExtractionError(null);
    
    // NOTE: /api/v1/extract endpoint is missing from backend API contract.
    // Simulating extraction on the frontend to demonstrate UX flow.
    setTimeout(() => {
      try {
        const mockEntities: ExtractedEntity[] = [];
        if (firText.toLowerCase().includes("lakh") || firText.includes("stolen")) {
          mockEntities.push({ id: "1", type: "LOCATION", value: metadata.district || "Unknown District", confidence: 0.85 });
        }
        
        // Simple mock regex for phones (10 digits)
        const phoneRegex = /\b\d{10}\b/g;
        let match;
        let idCounter = 2;
        while ((match = phoneRegex.exec(firText)) !== null) {
          mockEntities.push({ id: String(idCounter++), type: "PHONE", value: match[0], confidence: 0.95 });
        }

        if (mockEntities.length > 0) {
          setExtractedEntities(mockEntities);
          setExtractionStatus("success");
        } else {
          setExtractedEntities([]);
          setExtractionStatus("empty");
        }
      } catch (err) {
        setExtractionStatus("error");
        setExtractionError("Extraction failed. Note: The backend /extract API contract is missing.");
      } finally {
        setIsExtracting(false);
      }
    }, 1200);
  };

  const isFormValid = () => {
    return (
      metadata.title.trim() !== "" &&
      metadata.firNumber.trim() !== "" &&
      metadata.district.trim() !== "" &&
      firText.trim() !== ""
    );
  };

  const handleSubmit = async () => {
    if (!isFormValid()) return;

    setSubmitStatus("submitting");
    setSubmitError(null);

    try {
      const payload = {
        ...metadata,
        firText,
        entities: extractedEntities,
        // In a real scenario, files might be uploaded first and we send file IDs/URLs,
        // or we use multipart/form-data. Since api.ts cases.create accepts JSON `data: unknown`,
        // we'll just pass file names as a placeholder for the backend contract.
        files: Object.entries(files)
          .filter(([_, file]) => file !== null)
          .map(([key, file]) => ({ type: key, name: file?.name })),
      };

      await api.cases.create(payload);
      setSubmitStatus("success");
      
      // Optional: reset form after success
      // setMetadata({ title: "", firNumber: "", district: "", filedDate: "", category: "" });
      // setFirText("");
      // setExtractedEntities([]);
      // setFiles({ callRecords: null, financialLogs: null, locationData: null });
      // setExtractionStatus("idle");
    } catch (err: any) {
      setSubmitStatus("error");
      setSubmitError(err.message || "Failed to submit case.");
    }
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-white transition-colors">Case Intake</h1>
        <p className="text-surface-600 dark:text-surface-200 mt-1 transition-colors">
          Submit new case data for entity extraction and cross-case analysis.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="space-y-6">
          {/* Case Metadata */}
          <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none space-y-4 transition-colors">
            <h2 className="text-lg font-semibold text-surface-900 dark:text-white mb-2 transition-colors">Case Details</h2>
            
            <div>
              <label className="block text-sm font-medium text-surface-600 dark:text-surface-200 mb-2 transition-colors">
                Case Title *
              </label>
              <input
                type="text"
                value={metadata.title}
                onChange={(e) => handleMetadataChange("title", e.target.value)}
                placeholder="e.g., Missing Person Report — Lucknow District"
                className="w-full px-4 py-3 bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-lg text-surface-900 dark:text-white placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20 transition-colors shadow-sm dark:shadow-none"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-surface-600 dark:text-surface-200 mb-2 transition-colors">
                  FIR Number *
                </label>
                <input
                  type="text"
                  value={metadata.firNumber}
                  onChange={(e) => handleMetadataChange("firNumber", e.target.value)}
                  placeholder="e.g., FIR-2023-0145"
                  className="w-full px-4 py-2 bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-lg text-surface-900 dark:text-white placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20 transition-colors shadow-sm dark:shadow-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-600 dark:text-surface-200 mb-2 transition-colors">
                  District *
                </label>
                <input
                  type="text"
                  value={metadata.district}
                  onChange={(e) => handleMetadataChange("district", e.target.value)}
                  placeholder="e.g., Lucknow"
                  className="w-full px-4 py-2 bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-lg text-surface-900 dark:text-white placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20 transition-colors shadow-sm dark:shadow-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-600 dark:text-surface-200 mb-2 transition-colors">
                  Filed Date
                </label>
                <input
                  type="date"
                  value={metadata.filedDate}
                  onChange={(e) => handleMetadataChange("filedDate", e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-lg text-surface-900 dark:text-white placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20 transition-colors shadow-sm dark:shadow-none dark:[&::-webkit-calendar-picker-indicator]:invert"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-600 dark:text-surface-200 mb-2 transition-colors">
                  Category
                </label>
                <select
                  value={metadata.category}
                  onChange={(e) => handleMetadataChange("category", e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-lg text-surface-900 dark:text-white placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20 transition-colors shadow-sm dark:shadow-none"
                >
                  <option value="">Select a category</option>
                  <option value="missing_person">Missing Person</option>
                  <option value="financial_fraud">Financial Fraud</option>
                  <option value="cyber_crime">Cyber Crime</option>
                  <option value="theft">Theft</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>
          </div>

          {/* FIR Text */}
          <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors">
            <label className="block text-sm font-medium text-surface-600 dark:text-surface-200 mb-2 transition-colors">
              FIR Text / Case Narrative *
            </label>
            <textarea
              value={firText}
              onChange={(e) => setFirText(e.target.value)}
              placeholder="Paste the FIR text here. The system will extract entities (persons, phone numbers, vehicles, UPI IDs, locations) in real-time..."
              rows={10}
              className="w-full px-4 py-3 bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-lg text-surface-900 dark:text-white placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20 transition-colors resize-none font-mono text-sm shadow-sm dark:shadow-none"
            />
            <div className="flex justify-between items-center mt-3">
              <span className="text-xs text-surface-500 dark:text-surface-200 transition-colors">
                {firText.length} characters
              </span>
              <button
                onClick={handleExtract}
                disabled={!firText.trim() || isExtracting}
                className="px-6 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-surface-200 disabled:text-surface-500 dark:disabled:bg-surface-700 dark:disabled:text-surface-400 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
              >
                {isExtracting ? "Extracting..." : "🔍 Extract Entities"}
              </button>
            </div>
            
            {extractionStatus === "error" && (
              <div className="mt-3 text-sm text-danger-700 bg-danger-50 border border-danger-200 dark:text-danger-500 dark:bg-danger-500/10 dark:border-danger-500/20 rounded-lg p-3 transition-colors">
                {extractionError}
              </div>
            )}
            {extractionStatus === "empty" && (
              <div className="mt-3 text-sm text-warning-700 bg-warning-50 border border-warning-200 dark:text-warning-500 dark:bg-warning-500/10 dark:border-warning-500/20 rounded-lg p-3 transition-colors">
                No entities found in the provided text.
              </div>
            )}
          </div>

          {/* Additional Data Sources */}
          <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors">
            <h3 className="text-sm font-medium text-surface-600 dark:text-surface-200 mb-4 transition-colors">
              Additional Data Sources (Optional)
            </h3>
            <div className="space-y-4">
              {[
                { key: "callRecords", label: "Call Records (CSV)" },
                { key: "financialLogs", label: "Financial Transaction Logs" },
                { key: "locationData", label: "Location Data" },
              ].map(({ key, label }) => (
                <div key={key}>
                  <label className="block text-xs text-surface-600 dark:text-surface-200 mb-1 transition-colors">
                    {label}
                  </label>
                  <div className="flex items-center gap-3">
                    <input
                      type="file"
                      onChange={(e) => handleFileChange(key, e.target.files ? e.target.files[0] : null)}
                      className="flex-1 text-sm text-surface-600 dark:text-surface-200 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-surface-50 file:text-surface-900 hover:file:bg-surface-100 dark:file:bg-surface-800 dark:file:text-surface-200 dark:hover:file:bg-surface-700 file:cursor-pointer transition-colors"
                    />
                    {files[key] && (
                      <span className="text-xs text-success-700 bg-success-100 dark:text-success-500 dark:bg-success-500/10 px-2 py-1 rounded transition-colors">
                        Selected
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Live Extraction Preview & Submission */}
        <div className="space-y-6">
          <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors">
            <h2 className="text-lg font-semibold text-surface-900 dark:text-white mb-4 transition-colors">
              🔍 Live Extraction Preview
            </h2>
            <div className="space-y-4">
              <p className="text-sm text-surface-600 dark:text-surface-200 transition-colors">
                Entities will appear here as they are extracted from the input text.
                Each entity shows its type, confidence score, and source position.
              </p>

              {/* Entity type legend */}
              <div className="flex flex-wrap gap-2">
                {[
                  { type: "PERSON", color: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-500/20 dark:text-blue-300 dark:border-blue-500/30" },
                  { type: "PHONE", color: "bg-green-100 text-green-700 border-green-200 dark:bg-green-500/20 dark:text-green-300 dark:border-green-500/30" },
                  { type: "VEHICLE", color: "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-500/20 dark:text-yellow-300 dark:border-yellow-500/30" },
                  { type: "UPI_ID", color: "bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-500/20 dark:text-purple-300 dark:border-purple-500/30" },
                  { type: "LOCATION", color: "bg-red-100 text-red-700 border-red-200 dark:bg-red-500/20 dark:text-red-300 dark:border-red-500/30" },
                  { type: "ORG", color: "bg-cyan-100 text-cyan-700 border-cyan-200 dark:bg-cyan-500/20 dark:text-cyan-300 dark:border-cyan-500/30" },
                ].map(({ type, color }) => (
                  <span
                    key={type}
                    className={`px-2 py-1 rounded text-xs font-medium border ${color} transition-colors`}
                  >
                    {type}
                  </span>
                ))}
              </div>

              {/* Extraction results display */}
              <div className="border-t border-surface-200 dark:border-surface-800 pt-4 transition-colors">
                {extractionStatus === "success" && extractedEntities.length > 0 ? (
                  <div className="space-y-3">
                    {extractedEntities.map((entity) => (
                      <div key={entity.id} className="flex items-center justify-between p-3 bg-white dark:bg-surface-800 rounded-lg border border-surface-200 dark:border-surface-700 shadow-sm dark:shadow-none transition-colors">
                        <div>
                          <p className="text-sm font-medium text-surface-900 dark:text-white transition-colors">{entity.value}</p>
                          <span className="text-xs text-surface-500 dark:text-surface-400 transition-colors">{entity.type}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden transition-colors">
                            <div 
                              className="h-full bg-primary-500" 
                              style={{ width: `${entity.confidence * 100}%` }}
                            />
                          </div>
                          <span className="text-xs text-surface-600 dark:text-surface-200 transition-colors">
                            {Math.round(entity.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-60 border-2 border-dashed border-surface-300 dark:border-surface-700 rounded-lg bg-surface-50/50 dark:bg-surface-800/50 transition-colors">
                    <div className="text-center text-surface-500 dark:text-surface-200 transition-colors">
                      <p className="text-3xl mb-2">{isExtracting ? "⏳" : "📋"}</p>
                      <p className="text-sm">
                        {isExtracting 
                          ? "Extracting entities..." 
                          : firText.trim()
                            ? "Click 'Extract Entities' to preview results"
                            : "Enter FIR text to begin extraction"}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Submission Feedback */}
          {submitStatus === "success" && (
            <div className="p-4 bg-success-50 text-success-700 border border-success-200 dark:bg-success-500/10 dark:border-success-500/20 dark:text-success-500 rounded-xl transition-colors">
              <h3 className="font-medium mb-1">Case Submitted Successfully</h3>
              <p className="text-sm opacity-90">The case data has been recorded and is ready for analysis.</p>
            </div>
          )}
          {submitStatus === "error" && (
            <div className="p-4 bg-danger-50 text-danger-700 border border-danger-200 dark:bg-danger-500/10 dark:border-danger-500/20 dark:text-danger-500 rounded-xl transition-colors">
              <h3 className="font-medium mb-1">Submission Failed</h3>
              <p className="text-sm opacity-90">{submitError}</p>
            </div>
          )}

          {/* Submit Case Button */}
          <button
            onClick={handleSubmit}
            disabled={!isFormValid() || submitStatus === "submitting"}
            className="w-full px-6 py-4 bg-primary-600 hover:bg-primary-700 disabled:bg-surface-200 disabled:text-surface-500 dark:disabled:bg-surface-700 dark:disabled:text-surface-400 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-colors text-lg"
          >
            {submitStatus === "submitting" ? "Submitting Case..." : "Submit Case for Analysis"}
          </button>
          
          {!isFormValid() && (
            <p className="text-xs text-center text-surface-500 dark:text-surface-400 transition-colors">
              Fill in all required fields (*) to submit.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
