import fs from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const DATA = path.join(ROOT, "data", "synthetic");

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        cell += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(cell);
      cell = "";
    } else if (char === "\n") {
      row.push(cell.replace(/\r$/, ""));
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  const [headers, ...values] = rows;
  return values.map((items) =>
    Object.fromEntries(headers.map((header, index) => [header, items[index] ?? ""])),
  );
}

async function readCsv(relativePath) {
  return parseCsv(await fs.readFile(path.join(DATA, relativePath), "utf8"));
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function unique(items, label) {
  assert(new Set(items).size === items.length, `${label} contains duplicate identifiers`);
}

const [firCsv, firJson, cdr, transactions, patterns] = await Promise.all([
  readCsv(path.join("fir", "fir_cases.csv")),
  fs.readFile(path.join(DATA, "fir", "fir_cases.json"), "utf8").then(JSON.parse),
  readCsv(path.join("cdr", "cdr.csv")),
  readCsv(path.join("transactions", "transactions.csv")),
  fs.readFile(path.join(DATA, "expected-patterns", "fraud_patterns.json"), "utf8").then(JSON.parse),
]);

assert(firCsv.length === 1000, `Expected 1000 FIR CSV rows, found ${firCsv.length}`);
assert(firJson.length === 1000, `Expected 1000 FIR JSON records, found ${firJson.length}`);
assert(cdr.length === 20_000, `Expected 20000 CDR rows, found ${cdr.length}`);
assert(transactions.length === 20_000, `Expected 20000 transaction rows, found ${transactions.length}`);
assert(patterns.patterns.length >= 4, "Expected all four hidden pattern categories");

const caseIds = new Set(firJson.map((item) => item.case_id));
const firPhones = new Set(firJson.map((item) => item.phone));
const firUpis = new Set(firJson.map((item) => item.upi_id));
unique(firJson.map((item) => item.case_id), "FIR JSON");
unique(cdr.map((item) => item.cdr_id), "CDR");
unique(transactions.map((item) => item.transaction_id), "Transactions");

for (let index = 0; index < firJson.length; index += 1) {
  assert(firCsv[index].case_id === firJson[index].case_id, `FIR CSV/JSON mismatch at row ${index + 1}`);
  assert(firJson[index].complaint.includes(firJson[index].phone), `FIR ${firJson[index].case_id} omits its phone`);
  assert(firJson[index].complaint.includes(firJson[index].upi_id), `FIR ${firJson[index].case_id} omits its UPI ID`);
}
for (const row of cdr) {
  assert(caseIds.has(row.case_id), `CDR ${row.cdr_id} references unknown case ${row.case_id}`);
  assert(firPhones.has(row.caller), `CDR ${row.cdr_id} caller is absent from FIR data`);
  assert(firPhones.has(row.receiver), `CDR ${row.cdr_id} receiver is absent from FIR data`);
  assert(Number.isInteger(Number(row.duration)) && Number(row.duration) >= 0, `Invalid duration in ${row.cdr_id}`);
}
for (const row of transactions) {
  assert(caseIds.has(row.case_id), `Transaction ${row.transaction_id} references unknown case`);
  assert(firUpis.has(row.upi), `Transaction ${row.transaction_id} UPI is absent from FIR data`);
  assert(Number(row.amount) > 0, `Transaction ${row.transaction_id} has invalid amount`);
}
const knownCdrIds = new Set(cdr.map((item) => item.cdr_id));
const knownTransactionIds = new Set(transactions.map((item) => item.transaction_id));
for (const pattern of patterns.patterns) {
  for (const caseId of pattern.case_ids ?? []) assert(caseIds.has(caseId), `${pattern.pattern_id} references unknown case`);
  for (const cdrId of pattern.cdr_ids ?? []) assert(knownCdrIds.has(cdrId), `${pattern.pattern_id} references unknown CDR`);
  for (const transactionId of pattern.transaction_ids ?? []) {
    assert(knownTransactionIds.has(transactionId), `${pattern.pattern_id} references unknown transaction`);
  }
}

console.log(JSON.stringify({
  status: "valid",
  fir_records: firJson.length,
  cdr_records: cdr.length,
  transaction_records: transactions.length,
  expected_patterns: patterns.patterns.map((item) => item.type),
}));
