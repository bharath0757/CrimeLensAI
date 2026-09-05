# CrimeLensAI presentation FIR pack

These reports are entirely synthetic. They are designed to demonstrate how
CrimeLensAI discovers a network that is not obvious when each FIR is reviewed
independently. Upload the files in numerical order as separate cases.

Polished, text-based PDF versions can be regenerated with
`python scripts/generate_demo_fir_pdfs.py`. They are written to
`output/pdf/demo-firs/` and preserve the same evidence identifiers without
adding shared branding that could create false-positive links.

## Recommended demo order

| File | Suggested case number | Category | What it contributes |
| --- | --- | --- | --- |
| `01-courier-phishing-lucknow.txt` | `DEMO-FIR-001` | Cyber crime | Introduces the first phone, UPI ID and vehicle. |
| `02-marketplace-fraud-kanpur.txt` | `DEMO-FIR-002` | Financial fraud | Reuses the first phone, UPI ID and vehicle, creating a strong direct link. |
| `03-mule-account-hyderabad.txt` | `DEMO-FIR-003` | Financial fraud | Introduces the mule UPI ID, bank account and second phone. |
| `04-warehouse-call-network-kanpur.txt` | `DEMO-FIR-004` | Other | Connects the two clusters through the vehicle, mule UPI ID and second phone. |
| `05-unrelated-control-case-jaipur.txt` | `DEMO-FIR-005` | Theft | A control case that should not join the principal network. |

Use priority `High` for files 1–4 and `Medium` for file 5. The names,
identifiers, addresses and events are fabricated and must never be treated as
real allegations.

## Connections the judges should see

- FIR 001 and FIR 002 share phone `9000990189`, UPI ID
  `demohub26189@upi`, vehicle `UP 32 AB 2618`, and related fraud language.
- FIR 002 and FIR 004 share vehicle `UP 32 AB 2618` and location `Kanpur`.
- FIR 003 and FIR 004 share phone `9876502618`, UPI ID
  `mule26189@ybl`, bank account `123456789012`, and organization
  `North Star Trading`.
- FIR 004 therefore becomes the bridge that reveals one multi-case network.
- FIR 005 demonstrates that the software does not force unrelated cases into
  the network.

## Suggested narration

“Each officer initially sees a separate local complaint. CrimeLensAI extracts
the evidence with source positions, normalizes differently formatted values,
and finds that the same phone, payment handle and vehicle recur across police
stations. A later warehouse report bridges the payment and call clusters. The
system alerts the officer and explains every link, while the original FIR
remains the source of truth and every action is recorded in the audit ledger.”
