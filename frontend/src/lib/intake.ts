import { api } from "./api";
import type { CaseInput, CaseRecord } from "./contracts";

export interface IntakeCheckpoint {
  caseId?: string;
  documents: Record<string, string>;
  completed: string[];
}

export interface IntakeEvidence {
  key: string;
  file: File;
}

/** Keep acknowledged IDs so a failed processing request can be retried in-place. */
export async function submitIntake(
  metadata: CaseInput,
  evidence: IntakeEvidence[],
  checkpoint: IntakeCheckpoint,
  onProgress: (message: string) => void,
): Promise<CaseRecord> {
  if (!checkpoint.caseId) {
    onProgress("Saving case metadata…");
    const created = await api.cases.create(metadata);
    checkpoint.caseId = created.id;
  }
  for (const { key, file } of evidence) {
    if (!checkpoint.documents[key]) {
      onProgress(`Uploading ${file.name}…`);
      const uploaded = await api.documents.upload(checkpoint.caseId, file);
      checkpoint.documents[key] = uploaded.id;
    }
    if (!checkpoint.completed.includes(key)) {
      onProgress(`Extracting and synchronizing ${file.name}…`);
      const result = await api.documents.process(checkpoint.documents[key]);
      if (!result.success) throw new Error(`Processing did not complete for ${file.name}.`);
      checkpoint.completed.push(key);
    }
  }
  onProgress("Reading the saved case…");
  return api.cases.get(checkpoint.caseId);
}
