/**
 * CrimeLensAI — Audit Trail Page
 *
 * Displays the hash-chain tamper-evidence ledger as a verification table.
 * Each record shows its action, timestamp, actor, hash, and verification status.
 * Includes evidence PDF export functionality.
 */

export function AuditTrail() {
  // Placeholder ledger records — will be fetched from /api/v1/ledger/chain
  const placeholderHeaders = [
    "Chain #",
    "Timestamp",
    "Action",
    "Actor",
    "Resource",
    "Data Hash",
    "Status",
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Audit Trail</h1>
          <p className="text-surface-200 mt-1">
            Tamper-evident hash-chain ledger. Every entity and relationship write
            is recorded and verifiable.
          </p>
        </div>
        <button
          disabled
          className="px-6 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-surface-700 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
        >
          📄 Export Evidence PDF
        </button>
      </div>

      {/* Verification Status Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-surface-900 border border-surface-800 rounded-xl p-6">
          <p className="text-sm text-surface-200">Total Records</p>
          <p className="text-3xl font-bold text-white mt-2">0</p>
        </div>
        <div className="bg-surface-900 border border-success-500/20 rounded-xl p-6">
          <p className="text-sm text-surface-200">Verified ✓</p>
          <p className="text-3xl font-bold text-success-500 mt-2">0</p>
        </div>
        <div className="bg-surface-900 border border-danger-500/20 rounded-xl p-6">
          <p className="text-sm text-surface-200">Tampered ✕</p>
          <p className="text-3xl font-bold text-danger-500 mt-2">0</p>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-surface-900 border border-surface-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-800">
                {placeholderHeaders.map((header) => (
                  <th
                    key={header}
                    className="px-6 py-4 text-left text-xs font-medium text-surface-200 uppercase tracking-wider"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td
                  colSpan={placeholderHeaders.length}
                  className="px-6 py-16 text-center text-surface-200"
                >
                  <div>
                    <p className="text-3xl mb-3">🔗</p>
                    <p className="font-medium">No audit records yet</p>
                    <p className="text-sm mt-1">
                      Records will appear here as entities and relationships are
                      created through the system.
                    </p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Hash Chain Integrity Info */}
      <div className="bg-surface-900 border border-primary-500/20 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-primary-300 mb-3">
          🔐 How Hash-Chain Verification Works
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-surface-200">
          <div>
            <p className="font-medium text-white mb-1">1. Record</p>
            <p>
              Every entity extraction, relationship creation, and investigator
              action is serialized and hashed with SHA-256.
            </p>
          </div>
          <div>
            <p className="font-medium text-white mb-1">2. Chain</p>
            <p>
              Each record's hash includes the previous record's hash, forming an
              append-only chain. Altering any record breaks the chain.
            </p>
          </div>
          <div>
            <p className="font-medium text-white mb-1">3. Verify</p>
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
