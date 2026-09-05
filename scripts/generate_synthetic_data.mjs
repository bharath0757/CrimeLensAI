import fs from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const OUT = path.join(ROOT, "data", "synthetic");

function mulberry32(seed) {
  return () => {
    let value = (seed += 0x6d2b79f5);
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

const random = mulberry32(26189);
const pick = (items) => items[Math.floor(random() * items.length)];
const pad = (value, width) => String(value).padStart(width, "0");
const isoAt = (index, minuteStep = 17) =>
  new Date(Date.UTC(2026, 0, 1, 6, 0) + index * minuteStep * 60_000).toISOString();

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function toCsv(rows, columns) {
  return [
    columns.join(","),
    ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(",")),
  ].join("\n") + "\n";
}

const firstNames = [
  "Aarav", "Aditi", "Akash", "Ananya", "Arjun", "Deepak", "Divya", "Farhan",
  "Ishita", "Kabir", "Kavya", "Manoj", "Meera", "Neha", "Nikhil", "Pooja",
  "Pranav", "Priya", "Rahul", "Rajesh", "Rakesh", "Riya", "Rohan", "Sameer",
  "Sanjay", "Shreya", "Suresh", "Tanvi", "Varun", "Vikram",
];
const lastNames = [
  "Agarwal", "Bansal", "Chauhan", "Das", "Gupta", "Iyer", "Jain", "Kapoor",
  "Khan", "Kumar", "Mehta", "Mishra", "Nair", "Patel", "Rao", "Reddy",
  "Shah", "Sharma", "Singh", "Verma",
];
const locations = [
  "Bengaluru Central", "Chandni Chowk Delhi", "Charminar Hyderabad",
  "Gomti Nagar Lucknow", "Howrah Kolkata", "Indiranagar Bengaluru",
  "Kochi Marine Drive", "Mumbai Central", "Pune Camp", "Sector 17 Chandigarh",
  "T Nagar Chennai", "Vaishali Ghaziabad",
];
const towers = locations.map((location, index) => `TWR-${pad(index + 1, 3)}-${location.split(" ")[0].toUpperCase()}`);
const stateCodes = ["DL", "KA", "MH", "TN", "TS", "UP", "WB", "GJ", "RJ", "KL"];
const upiHandles = ["oksbi", "okaxis", "okicici", "ybl", "paytm", "upi"];

const persons = Array.from({ length: 240 }, (_, index) => ({
  id: `P-${pad(index + 1, 4)}`,
  name: `${firstNames[index % firstNames.length]} ${lastNames[Math.floor(index / firstNames.length) % lastNames.length]}`,
  phone: `+91${7000000000 + index * 7919}`.slice(0, 13),
  imei: `${860000000000000 + index * 1009}`,
  upi: `${firstNames[index % firstNames.length].toLowerCase()}.${pad(index + 1, 4)}@${upiHandles[index % upiHandles.length]}`,
  account: `${510000000000 + index * 3571}`,
  aadhaar: `${200000000000 + index * 7919}`,
  pan: `CLNAI${pad(index + 1, 4)}${String.fromCharCode(65 + (index % 26))}`,
}));

const firs = [];
for (let index = 0; index < 1000; index += 1) {
  const cluster = index % 40;
  const memberOffset = Math.floor(index / 40) % 5;
  const primary = persons[(cluster * 5 + memberOffset) % persons.length];
  const associate = persons[(cluster * 5 + ((memberOffset + 1) % 5)) % persons.length];
  const location = locations[cluster % locations.length];
  const vehicle = `${stateCodes[cluster % stateCodes.length]}${pad((cluster % 35) + 1, 2)}AB${pad(1000 + cluster * 7 + memberOffset, 4)}`;
  const caseId = `FIR-2026-${pad(index + 1, 4)}`;
  const date = isoAt(index, 720).slice(0, 10);
  const complaint =
    `On ${date}, complainant reported suspect ${primary.name} near ${location}. ` +
    `The suspect used phone ${primary.phone}, vehicle ${vehicle}, UPI ${primary.upi}, ` +
    `bank account number ${primary.account}, Aadhaar ${primary.aadhaar.match(/.{1,4}/g).join(" ")}, ` +
    `PAN ${primary.pan}, and contacted associate ${associate.name}. Offences were recorded under IPC section 420.`;
  firs.push({
    case_id: caseId,
    complaint,
    persons: `${primary.name}|${associate.name}`,
    phone: primary.phone,
    vehicle,
    upi_id: primary.upi,
    location,
    date,
  });
}

const cdr = [];
const organizedCdrIds = [];
for (let index = 0; index < 20_000; index += 1) {
  const cluster = index % 40;
  const memberOffset = Math.floor(index / 40) % 5;
  const caller = persons[(cluster * 5 + memberOffset) % persons.length];
  const receiver = persons[(cluster * 5 + ((memberOffset + 1 + (index % 3)) % 5)) % persons.length];
  const cdrId = `CDR-${pad(index + 1, 6)}`;
  if (cluster === 7 && organizedCdrIds.length < 25) organizedCdrIds.push(cdrId);
  cdr.push({
    cdr_id: cdrId,
    case_id: `FIR-2026-${pad((index % 1000) + 1, 4)}`,
    caller: caller.phone,
    receiver: receiver.phone,
    timestamp: isoAt(index, 7),
    duration: 20 + ((index * 37) % 1180),
    tower: towers[(cluster + memberOffset) % towers.length],
    imei: caller.imei,
  });
}

const transactions = [];
const launderingIds = [];
const muleIds = [];
const circularIds = [];
for (let index = 0; index < 20_000; index += 1) {
  const cluster = index % 40;
  const step = Math.floor(index / 40) % 5;
  const sender = persons[(cluster * 5 + step) % persons.length];
  const receiver = persons[(cluster * 5 + ((step + 1) % 5)) % persons.length];
  const transactionId = `TXN-${pad(index + 1, 7)}`;
  if (cluster === 3 && launderingIds.length < 20) launderingIds.push(transactionId);
  if (cluster === 11 && muleIds.length < 30) muleIds.push(transactionId);
  if (cluster === 19 && circularIds.length < 15) circularIds.push(transactionId);
  transactions.push({
    sender: sender.account,
    receiver: receiver.account,
    amount: (2500 + ((index * 7919) % 475000) + (cluster === 3 ? 500000 : 0)).toFixed(2),
    upi: receiver.upi,
    timestamp: isoAt(index, 11),
    transaction_id: transactionId,
    case_id: `FIR-2026-${pad((index % 1000) + 1, 4)}`,
  });
}

const clusterCases = (cluster, count = 10) =>
  Array.from({ length: count }, (_, offset) => `FIR-2026-${pad(cluster + 1 + offset * 40, 4)}`);

const expectedPatterns = {
  dataset_version: "1.0.0",
  seed: 26189,
  disclaimer: "Entirely synthetic data for system validation; not linked to real people.",
  patterns: [
    {
      pattern_id: "PAT-LAUNDER-001",
      type: "money_laundering_chain",
      case_ids: clusterCases(3),
      transaction_ids: launderingIds,
      explanation: "High-value transfers move through five accounts in sequence before returning to the originating cluster.",
    },
    {
      pattern_id: "PAT-MULE-001",
      type: "mule_accounts",
      case_ids: clusterCases(11),
      transaction_ids: muleIds,
      account_ids: persons.slice(55, 60).map((person) => person.account),
      explanation: "Several FIR subjects route frequent transfers through a compact receiving-account group.",
    },
    {
      pattern_id: "PAT-CIRCULAR-001",
      type: "circular_transactions",
      case_ids: clusterCases(19),
      transaction_ids: circularIds,
      explanation: "A five-account transfer ring returns funds to its starting account.",
    },
    {
      pattern_id: "PAT-PHONE-001",
      type: "organized_crime_phone_network",
      case_ids: clusterCases(7),
      cdr_ids: organizedCdrIds,
      phone_numbers: persons.slice(35, 40).map((person) => person.phone),
      explanation: "Five devices repeatedly communicate across FIRs using a stable tower corridor.",
    },
  ],
};

await Promise.all([
  fs.mkdir(path.join(OUT, "fir"), { recursive: true }),
  fs.mkdir(path.join(OUT, "cdr"), { recursive: true }),
  fs.mkdir(path.join(OUT, "transactions"), { recursive: true }),
  fs.mkdir(path.join(OUT, "expected-patterns"), { recursive: true }),
]);

await Promise.all([
  fs.writeFile(
    path.join(OUT, "fir", "fir_cases.csv"),
    toCsv(firs, ["case_id", "complaint", "persons", "phone", "vehicle", "upi_id", "location", "date"]),
  ),
  fs.writeFile(path.join(OUT, "fir", "fir_cases.json"), JSON.stringify(firs, null, 2) + "\n"),
  fs.writeFile(
    path.join(OUT, "cdr", "cdr.csv"),
    toCsv(cdr, ["cdr_id", "case_id", "caller", "receiver", "timestamp", "duration", "tower", "imei"]),
  ),
  fs.writeFile(
    path.join(OUT, "transactions", "transactions.csv"),
    toCsv(transactions, ["sender", "receiver", "amount", "upi", "timestamp", "transaction_id", "case_id"]),
  ),
  fs.writeFile(
    path.join(OUT, "expected-patterns", "fraud_patterns.json"),
    JSON.stringify(expectedPatterns, null, 2) + "\n",
  ),
]);

console.log(JSON.stringify({
  firs: firs.length,
  cdr_records: cdr.length,
  transactions: transactions.length,
  expected_patterns: expectedPatterns.patterns.length,
}));
