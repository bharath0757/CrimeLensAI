# Synthetic Women-Safety Network Scenario

This dataset is entirely fictional. It is designed to exercise the specific
failure mode in SIH26189: related records are filed separately, while phone,
vehicle and payment signals recur across districts and sources.

The files deliberately include:

- formatting variants (`UP 32 AB 1234`, `UP-32-AB-1234`, `UP32 AB 1234`);
- phone-number variants with and without `+91`;
- one high-value UPI recipient across three cases;
- a second phone/UPI chain that supports an explainable missing-link lead;
- realistic negative detail so the network is not just a list of planted IDs.

`ground_truth.json` defines expected exact signals. It is for regression tests
and demo rehearsal, not for reporting model accuracy. A credible evaluation
must add noisy spelling, OCR errors, code-mixed language, distractor entities,
and blinded annotations that the algorithm has not seen.
