# CrimeLensAI - Judge Demo Brief

## Core motive

CrimeLensAI turns fragmented case records into reviewable investigative leads:
it shows an officer that a new FIR shares a phone, vehicle, payment identity or
network path with older cases, explains exactly why, links back to the source
occurrence, and raises an alert before the connection is lost in manual review.

The product is not an autonomous accusation engine. It is an evidence-backed
prioritisation and institutional-memory layer for investigators.

## The real operational problem

The problem is not simply that police records are undigitised. MHA states that
CCTNS is intended to inter-link police stations for investigation and analytics,
and that ICJS integrates police, courts, prisons, forensics and prosecution. MHA
also lists national automatic matching alerts and a Criminal Network Link
Analysis module among current capabilities. Therefore, a credible SIH prototype
must not claim that a graph or national search is itself new.

The remaining practical difficulty is turning varied, noisy records into the
same reliable entity, combining signals across record types, ranking what needs
attention now, and allowing an officer to verify every machine-suggested link.
UNODC's criminal-intelligence guidance describes investigative information as
voluminous and varied, and link analysis as a way to organise relationships so
meaning can be inferred. It separately stresses evaluating source reliability
and information quality. CrimeLensAI implements that distinction through source
offsets, confidence, explanation, and human confirmation.

Authoritative references:

- MHA CCTNS/ICJS and police-investigation features:
  https://www.mha.gov.in/en/divisionofmha/women-safety-division/cctns
- UNODC Criminal Intelligence Manual for Analysts:
  https://www.unodc.org/documents/organized-crime/Law-Enforcement/Criminal_Intelligence_for_Analysts.pdf
- UNODC integrated investigation/case-management challenge:
  https://gocase.unodc.org/gocase/en/about-gocase.html

## What is technically distinctive in this prototype

1. **Evidence-first extraction.** The system retains the original text span,
   source field, observed spelling, canonical value, method and confidence.
2. **Conservative identity resolution.** Exact identifiers are normalised and
   matched exactly. Ambiguous names are only proposed as candidate merges.
3. **Cross-source convergence.** FIR, CDR and transaction signals strengthen a
   lead when independent sources converge; a common location alone stays weak.
4. **Explainable missing-pattern detection.** Repeated identifiers, bridge
   entities, multi-signal convergence, shortest paths and common-neighbour link
   predictions all return their supporting entities/paths.
5. **Officer alerts with state.** A newly discovered cross-case match creates a
   severity-ranked alert that can be acknowledged without deleting its history.
6. **Human decision boundary.** Predictions are labelled
   `INVESTIGATIVE_LEAD_NOT_FACT`; the original record remains one click away.

## Six-minute live demo

### 0:00-0:45 - Establish the failure

Show five fictional missing-person FIRs filed in separate Uttar Pradesh
districts. Ask: "If each officer sees only one file, who notices the network?"

### 0:45-1:45 - Ingest a new FIR

Paste `FIR-UNN-005`. Show extraction of two phone numbers and a person. Click a
result to highlight the exact characters in the FIR. Mention that the model is
proposing observations, not declaring identities.

### 1:45-2:45 - Reveal the connection and alert

Submit the case. A high-severity alert should state that `9876543210` already
appears in Lucknow and Sitapur records. Open the alert and show each source
occurrence, including its record type and offsets.

### 2:45-3:45 - Move from one match to a network

Open the linkage graph. Display the recurring vehicle, phone and UPI recipient.
Use edge thickness for evidence strength and node size for centrality. Select a
bridge entity and explain that high betweenness means it connects clusters; it
does not mean the node is automatically the criminal leader.

### 3:45-4:40 - Show the missing pattern

Open Patterns. Show multi-signal convergence and one common-neighbour candidate
link. Expand "Why suggested" to reveal the supporting path. Emphasise the
`INVESTIGATIVE_LEAD_NOT_FACT` label and confirm/reject workflow.

### 4:40-5:25 - Prove traceability

Move from a graph edge back to the FIR/CDR/transaction row. Then open the audit
record and verify its hash. This joins graph intelligence to courtroom-oriented
provenance rather than presenting a black-box score.

### 5:25-6:00 - Close on impact

"CrimeLensAI does not replace the investigator or CCTNS. It reduces the chance
that a cross-district pattern waits for the fifth victim before someone sees it."

## Metrics judges can trust

Report separate metrics instead of one vague "AI accuracy" number:

- extraction precision/recall/F1 by entity type;
- exact source-offset accuracy;
- entity-resolution pair precision and false-merge rate;
- alert precision at top K and median time-to-triage;
- pattern recall under controlled deletion of known graph edges;
- explanation completeness (percentage of leads with inspectable source paths);
- analyst acceptance/rejection and time saved in a blinded task study.

Do not report performance measured only on the planted demo ground truth as a
real-world accuracy result.

## Future scope - credible rollout path

### Phase 1 - stronger prototype evidence

- noisy, code-mixed and OCR-degraded FIR evaluation;
- blinded synthetic benchmark with distractors and withheld links;
- multilingual extraction for Hindi plus one state language;
- temporal patterns such as burst calls, rapid fund movement and changing SIMs;
- geospatial/jurisdiction filters with explicit legal access controls.

### Phase 2 - controlled state pilot

- one Women Safety Cell, read-only adapters to authorised CCTNS exports;
- legally authorised CDR/financial ingestion, data minimisation and retention;
- supervisor review queues, district scoping and feedback-based threshold tuning;
- security, bias, privacy and legal-admissibility assessment.

### Phase 3 - institutional integration

- approved CCTNS/ICJS integration rather than a parallel data silo;
- cross-state candidate resolution through authorised national systems;
- permissioned, multi-district tamper-evidence ledger;
- multilingual domain models trained only on governed, anonymised records;
- monitored model versions, drift detection and reproducible historical results.

## Questions judges are likely to ask

**"Doesn't CCTNS already do link analysis?"**  Yes. Our prototype targets the
hard layer around it: entity extraction from messy multi-source records,
evidence-preserving normalisation, explainable pattern ranking and actionable
review alerts. It is designed as an authorised integration module, not a rival
national database.

**"How do you prevent false accusations?"**  Exact and fuzzy identity are kept
separate; low-specificity signals carry less weight; every lead exposes sources;
predictions are labelled non-factual; and officers confirm or reject them.

**"Is the synthetic demo circular?"**  It proves end-to-end behaviour, not
accuracy. The next evaluation withholds links, adds distractors/noise and uses
blinded annotations. We report false merges and precision at K explicitly.

**"Why graph technology?"**  The product question is path-based: which cases
share entities, who bridges clusters, and what evidence path connects two nodes.
Graphs represent and query those relationships directly while preserving the
source edge that explains each result.
