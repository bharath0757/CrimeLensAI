import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";

interface LedgerRecord {
  id: string;
  timestamp: string;
  action: string;
  actor: string;
  resource: string;
  dataHash?: string;
  hash?: string;
  status?: string;
  verified?: boolean;
}

export function AuditTrail() {
  const [records, setRecords] = useState<LedgerRecord[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error" | "empty">("loading");
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [verificationFeedback, setVerificationFeedback] = useState<{ id: string, type: "success" | "error", message: string } | null>(null);

  const fetchRecords = useCallback(async () => {
    setStatus("loading");
    setVerificationFeedback(null);
    try {
      // Fetch from ledger chain api
      const response = await api.ledger.chain(50, 0) as any;
      
      // Determine array structure from response
      const items: LedgerRecord[] = Array.isArray(response) ? response : (response?.items || []);
      
      if (items.length > 0) {
        setRecords(items);
        setStatus("success");
      } else {
        setRecords([]);
        setStatus("empty");
      }
    } catch (error) {
      console.error("Failed to load audit records:", error);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  const handleVerify = async (recordId: string) => {
    setVerifyingId(recordId);
    setVerificationFeedback(null);
    try {
      const result = await api.ledger.verify(recordId) as any;
      
      // Assume result contains a verified boolean or status string
      const isVerified = result.verified === true || result.status === "VERIFIED" || result.status === "OK";
      
      // Update local record status
      setRecords(prev => prev.map(rec => 
        rec.id === recordId 
          ? { ...rec, verified: isVerified, status: isVerified ? "VERIFIED" : "TAMPERED" } 
          : rec
      ));

      setVerificationFeedback({
        id: recordId,
        type: isVerified ? "success" : "error",
        message: isVerified ? "Record verified successfully." : "Record verification failed. Possible tamper detected.",
      });

      // Clear feedback after 4 seconds
      setTimeout(() => {
        setVerificationFeedback(prev => prev?.id === recordId ? null : prev);
      }, 4000);

    } catch (error) {
      console.error("Verification error:", error);
      setVerificationFeedback({
        id: recordId,
        type: "error",
        message: "Unable to verify record. API error.",
      });
      // Clear feedback after 4 seconds
      setTimeout(() => {
        setVerificationFeedback(prev => prev?.id === recordId ? null : prev);
      }, 4000);
    } finally {
      setVerifyingId(null);
    }
  };

  const headers = [
    "Chain #",
    "Timestamp",
    "Action",
    "Actor",
    "Resource",
    "Data Hash",
    "Status",
    "Verify",
  ];

  // Calculate Statistics
  const totalRecords = records.length;
  const verifiedCount = records.filter(r => r.verified === true || r.status === "VERIFIED").length;
  const tamperedCount = records.filter(r => r.verified === false || r.status === "TAMPERED").length;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-white flex items-center gap-3 transition-colors">
            Audit Trail
            <button 
              onClick={fetchRecords} 
              className="text-sm px-2 py-1 bg-surface-100 hover:bg-surface-200 text-surface-600 hover:text-surface-900 dark:bg-surface-800 dark:hover:bg-surface-700 dark:text-surface-200 dark:hover:text-white rounded transition-colors"
              title="Refresh Records"
            >
              🔄 Refresh
            </button>
          </h1>
          <p className="text-surface-600 dark:text-surface-200 mt-1 transition-colors">
            Tamper-evident hash-chain ledger. Every entity and relationship write
            is recorded and verifiable.
          </p>
        </div>
        <button
          disabled
          className="px-6 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-surface-200 disabled:text-surface-500 dark:disabled:bg-surface-700 dark:disabled:text-surface-400 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
        >
          📄 Export Evidence PDF
        </button>
      </div>

      {/* Verification Status Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors">
          <p className="text-sm text-surface-600 dark:text-surface-200 transition-colors">Total Records</p>
          <p className="text-3xl font-bold text-surface-900 dark:text-white mt-2 transition-colors">{status === "loading" ? "..." : totalRecords}</p>
        </div>
        <div className="bg-white dark:bg-surface-900 border border-success-200 dark:border-success-500/20 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors">
          <p className="text-sm text-surface-600 dark:text-surface-200 transition-colors">Verified ✓</p>
          <p className="text-3xl font-bold text-success-600 dark:text-success-500 mt-2 transition-colors">{status === "loading" ? "..." : verifiedCount}</p>
        </div>
        <div className="bg-white dark:bg-surface-900 border border-danger-200 dark:border-danger-500/20 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors">
          <p className="text-sm text-surface-600 dark:text-surface-200 transition-colors">Tampered ✕</p>
          <p className="text-3xl font-bold text-danger-600 dark:text-danger-500 mt-2 transition-colors">{status === "loading" ? "..." : tamperedCount}</p>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl overflow-hidden shadow-sm dark:shadow-none transition-colors">
        <div className="overflow-x-auto min-h-[300px] relative">
          <table className="w-full">
            <thead className="bg-surface-50 dark:bg-transparent transition-colors">
              <tr className="border-b border-surface-200 dark:border-surface-800 transition-colors">
                {headers.map((header) => (
                  <th
                    key={header}
                    className="px-6 py-4 text-left text-xs font-medium text-surface-500 dark:text-surface-200 uppercase tracking-wider whitespace-nowrap transition-colors"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {status === "loading" && (
                <tr>
                  <td colSpan={headers.length} className="px-6 py-24 text-center text-surface-500 dark:text-surface-200 transition-colors">
                    <p className="text-3xl mb-3 animate-spin inline-block">⏳</p>
                    <p className="font-medium">Loading audit records...</p>
                  </td>
                </tr>
              )}
              
              {status === "error" && (
                <tr>
                  <td colSpan={headers.length} className="px-6 py-24 text-center text-danger-600 dark:text-danger-500 transition-colors">
                    <p className="text-3xl mb-3">⚠️</p>
                    <p className="font-medium">Unable to load audit records.</p>
                    <button onClick={fetchRecords} className="mt-4 px-4 py-2 bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-900 dark:text-white rounded-lg text-sm transition-colors">
                      Retry
                    </button>
                  </td>
                </tr>
              )}

              {status === "empty" && (
                <tr>
                  <td colSpan={headers.length} className="px-6 py-24 text-center text-surface-500 dark:text-surface-200 transition-colors">
                    <p className="text-3xl mb-3">🔗</p>
                    <p className="font-medium">No audit records available.</p>
                    <p className="text-sm mt-1">
                      Records will appear here as entities and relationships are
                      created through the system.
                    </p>
                  </td>
                </tr>
              )}

              {status === "success" && records.map((record) => {
                const recordHash = record.dataHash || record.hash || "—";
                const displayHash = recordHash.length > 20 ? `${recordHash.substring(0, 10)}...${recordHash.substring(recordHash.length - 10)}` : recordHash;
                
                let statusBadge = (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-surface-100 text-surface-600 border border-surface-200 dark:bg-surface-800 dark:text-surface-300 dark:border-surface-700 transition-colors">
                    Pending
                  </span>
                );
                
                if (record.verified === true || record.status === "VERIFIED") {
                  statusBadge = (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-success-100 text-success-700 border border-success-200 dark:bg-success-500/10 dark:text-success-500 dark:border-success-500/20 transition-colors">
                      Verified
                    </span>
                  );
                } else if (record.verified === false || record.status === "TAMPERED") {
                  statusBadge = (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-danger-100 text-danger-700 border border-danger-200 dark:bg-danger-500/10 dark:text-danger-500 dark:border-danger-500/20 transition-colors">
                      Tampered
                    </span>
                  );
                }

                return (
                  <tr key={record.id} className="border-b border-surface-100 dark:border-surface-800 hover:bg-primary-50/50 dark:hover:bg-surface-800/30 transition-colors">
                    <td className="px-6 py-4 text-sm font-medium text-primary-600 dark:text-primary-400 whitespace-nowrap transition-colors">
                      #{record.id.substring(0, 8)}
                    </td>
                    <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-200 whitespace-nowrap transition-colors">
                      {record.timestamp ? new Date(record.timestamp).toLocaleString() : "—"}
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-surface-900 dark:text-white whitespace-nowrap transition-colors">
                      {record.action || "—"}
                    </td>
                    <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-200 whitespace-nowrap transition-colors">
                      {record.actor || "—"}
                    </td>
                    <td className="px-6 py-4 text-sm text-surface-600 dark:text-surface-200 truncate max-w-[200px] transition-colors" title={record.resource}>
                      {record.resource || "—"}
                    </td>
                    <td className="px-6 py-4 text-xs font-mono text-surface-500 dark:text-surface-400 whitespace-nowrap transition-colors" title={recordHash}>
                      {displayHash}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {statusBadge}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-col gap-1 items-start">
                        <button
                          onClick={() => handleVerify(record.id)}
                          disabled={verifyingId === record.id}
                          className="px-3 py-1.5 bg-primary-50 hover:bg-primary-100 text-primary-600 border border-primary-200 dark:bg-primary-600/20 dark:hover:bg-primary-600/40 dark:text-primary-400 dark:border-primary-500/30 rounded text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          {verifyingId === record.id ? "Verifying..." : "Verify"}
                        </button>
                        {verificationFeedback?.id === record.id && (
                          <span className={`text-[10px] ${verificationFeedback.type === 'success' ? 'text-success-600 dark:text-success-400' : 'text-danger-600 dark:text-danger-400'}`}>
                            {verificationFeedback.message}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Hash Chain Integrity Info */}
      <div className="bg-white dark:bg-surface-900 border border-primary-200 dark:border-primary-500/20 rounded-xl p-6 shadow-sm dark:shadow-none transition-colors">
        <h3 className="text-sm font-semibold text-primary-700 dark:text-primary-300 mb-3 transition-colors">
          🔐 How Hash-Chain Verification Works
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-surface-600 dark:text-surface-200 transition-colors">
          <div>
            <p className="font-medium text-surface-900 dark:text-white mb-1 transition-colors">1. Record</p>
            <p>
              Every entity extraction, relationship creation, and investigator
              action is serialized and hashed with SHA-256.
            </p>
          </div>
          <div>
            <p className="font-medium text-surface-900 dark:text-white mb-1 transition-colors">2. Chain</p>
            <p>
              Each record's hash includes the previous record's hash, forming an
              append-only chain. Altering any record breaks the chain.
            </p>
          </div>
          <div>
            <p className="font-medium text-surface-900 dark:text-white mb-1 transition-colors">3. Verify</p>
            <p>
              Click "Verify" on any record to recompute its hash and confirm the
              chain is intact — proving the evidence hasn't been tampered with.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
