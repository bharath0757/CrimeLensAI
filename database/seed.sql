INSERT INTO users (
    id, email, password_hash, full_name, role, badge_number, agency
) VALUES
    (
        'user-admin-001',
        'admin@crimelens.ai',
        crypt('AdminSecret123!', gen_salt('bf')),
        'CrimeLens Administrator',
        'ADMIN',
        'ADMIN-001',
        'CrimeLens Command Centre'
    ),
    (
        'user-inv-002',
        'investigator@crimelens.ai',
        crypt('Investigator123!', gen_salt('bf')),
        'Demo Investigator',
        'INVESTIGATOR',
        'INV-002',
        'State Investigation Unit'
    ),
    (
        'user-analyst-003',
        'analyst@crimelens.ai',
        crypt('Analyst123!', gen_salt('bf')),
        'Network Analyst',
        'ANALYST',
        'ANL-003',
        'Financial Intelligence Cell'
    )
ON CONFLICT (id) DO NOTHING;

CREATE TEMP TABLE fir_seed (
    case_id TEXT,
    complaint TEXT,
    persons TEXT,
    phone TEXT,
    vehicle TEXT,
    upi_id TEXT,
    location TEXT,
    incident_date DATE
);

\copy fir_seed FROM '/datasets/fir/fir_cases.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

INSERT INTO cases (
    id, case_number, title, description, complaint, status, priority,
    owner_id, assigned_investigator_ids, tags, location, incident_date
)
SELECT
    case_id,
    case_id,
    'Synthetic investigation ' || case_id,
    left(complaint, 2000),
    complaint,
    CASE WHEN right(case_id, 1)::integer % 4 = 0 THEN 'IN_PROGRESS' ELSE 'OPEN' END,
    CASE
        WHEN right(case_id, 2)::integer % 11 = 0 THEN 'CRITICAL'
        WHEN right(case_id, 2)::integer % 5 = 0 THEN 'HIGH'
        ELSE 'MEDIUM'
    END,
    'user-admin-001',
    '["user-admin-001","user-inv-002"]'::jsonb,
    jsonb_build_array('synthetic', lower(split_part(location, ' ', 1))),
    location,
    incident_date
FROM fir_seed
ON CONFLICT (id) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT
    'ent-' || md5(case_id || ':PERSON:' || lower(trim(person))),
    case_id,
    trim(person),
    lower(trim(person)),
    'PERSON',
    'Named in FIR complaint',
    0.90
FROM fir_seed
CROSS JOIN LATERAL unnest(string_to_array(persons, '|')) AS person
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT 'ent-' || md5(case_id || ':PHONE:' || regexp_replace(phone, '\D', '', 'g')),
       case_id, phone, regexp_replace(phone, '\D', '', 'g'), 'PHONE_NUMBER',
       'Phone observed in FIR complaint', 0.99
FROM fir_seed
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT 'ent-' || md5(case_id || ':VEHICLE:' || upper(regexp_replace(vehicle, '[^A-Za-z0-9]', '', 'g'))),
       case_id, vehicle, upper(regexp_replace(vehicle, '[^A-Za-z0-9]', '', 'g')), 'VEHICLE',
       'Vehicle observed in FIR complaint', 0.98
FROM fir_seed
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT 'ent-' || md5(case_id || ':UPI:' || lower(upi_id)),
       case_id, upi_id, lower(upi_id), 'UPI_ID',
       'UPI identifier observed in FIR complaint', 0.99
FROM fir_seed
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT 'ent-' || md5(case_id || ':LOCATION:' || lower(location)),
       case_id, location, lower(location), 'LOCATION',
       'Location observed in FIR complaint', 0.90
FROM fir_seed
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT 'ent-' || md5(case_id || ':BANK_ACCOUNT:' || account_number),
       case_id, account_number, account_number, 'BANK_ACCOUNT',
       'Bank account observed in FIR complaint', 0.96
FROM (
    SELECT case_id, substring(complaint FROM 'bank account number ([0-9]{9,18})') AS account_number
    FROM fir_seed
) extracted
WHERE account_number IS NOT NULL
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT 'ent-' || md5(case_id || ':AADHAAR:' || aadhaar_number),
       case_id, aadhaar_number, aadhaar_number, 'AADHAAR',
       'Synthetic Aadhaar-format identifier observed in FIR complaint', 0.97
FROM (
    SELECT case_id,
           regexp_replace(substring(complaint FROM 'Aadhaar ([0-9 ]{14})'), '\D', '', 'g') AS aadhaar_number
    FROM fir_seed
) extracted
WHERE length(aadhaar_number) = 12
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT 'ent-' || md5(case_id || ':PAN:' || pan_number),
       case_id, pan_number, pan_number, 'PAN',
       'Synthetic PAN-format identifier observed in FIR complaint', 0.98
FROM (
    SELECT case_id, upper(substring(complaint FROM 'PAN ([A-Za-z]{5}[0-9]{4}[A-Za-z])')) AS pan_number
    FROM fir_seed
) extracted
WHERE pan_number IS NOT NULL
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

CREATE TEMP TABLE cdr_seed (
    cdr_id TEXT,
    case_id TEXT,
    caller TEXT,
    receiver TEXT,
    occurred_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    tower TEXT,
    imei TEXT
);

\copy cdr_seed FROM '/datasets/cdr/cdr.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

INSERT INTO cdr_records
SELECT * FROM cdr_seed
ON CONFLICT (case_id, cdr_id) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT DISTINCT
    'ent-' || md5(case_id || ':PHONE:' || regexp_replace(phone, '\D', '', 'g')),
    case_id,
    phone,
    regexp_replace(phone, '\D', '', 'g'),
    'PHONE_NUMBER',
    'Phone observed in call detail records',
    1.0
FROM (
    SELECT case_id, caller AS phone FROM cdr_seed
    UNION
    SELECT case_id, receiver AS phone FROM cdr_seed
) phones
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO relationships (
    id, case_id, source_entity_id, target_entity_id, relationship_type,
    description, properties, confidence_score
)
SELECT
    'rel-' || md5(cdr_id),
    case_id,
    'ent-' || md5(case_id || ':PHONE:' || regexp_replace(caller, '\D', '', 'g')),
    'ent-' || md5(case_id || ':PHONE:' || regexp_replace(receiver, '\D', '', 'g')),
    'CALLED',
    'Synthetic call detail record',
    jsonb_build_object(
        'cdr_id', cdr_id,
        'timestamp', occurred_at,
        'duration_seconds', duration_seconds,
        'tower', tower,
        'imei', imei
    ),
    1.0
FROM cdr_seed
ON CONFLICT (id) DO NOTHING;

CREATE TEMP TABLE transaction_seed (
    sender TEXT,
    receiver TEXT,
    amount NUMERIC(14,2),
    upi_id TEXT,
    occurred_at TIMESTAMPTZ,
    transaction_id TEXT,
    case_id TEXT
);

\copy transaction_seed FROM '/datasets/transactions/transactions.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

INSERT INTO transactions
SELECT transaction_id, case_id, sender, receiver, amount, upi_id, occurred_at
FROM transaction_seed
ON CONFLICT (case_id, transaction_id) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT DISTINCT
    'ent-' || md5(case_id || ':BANK_ACCOUNT:' || account_number),
    case_id,
    account_number,
    account_number,
    'BANK_ACCOUNT',
    'Account observed in transaction records',
    1.0
FROM (
    SELECT case_id, sender AS account_number FROM transaction_seed
    UNION
    SELECT case_id, receiver AS account_number FROM transaction_seed
) accounts
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO entities (id, case_id, name, normalized_value, entity_type, description, confidence_score)
SELECT DISTINCT
    'ent-' || md5(case_id || ':UPI:' || lower(upi_id)),
    case_id,
    upi_id,
    lower(upi_id),
    'UPI_ID',
    'UPI identifier observed in transaction records',
    1.0
FROM transaction_seed
ON CONFLICT (case_id, entity_type, normalized_value) DO NOTHING;

INSERT INTO relationships (
    id, case_id, source_entity_id, target_entity_id, relationship_type,
    description, properties, confidence_score
)
SELECT
    'rel-' || md5(transaction_id),
    case_id,
    'ent-' || md5(case_id || ':BANK_ACCOUNT:' || sender),
    'ent-' || md5(case_id || ':BANK_ACCOUNT:' || receiver),
    'TRANSFERRED_TO',
    'Synthetic financial transaction',
    jsonb_build_object(
        'transaction_id', transaction_id,
        'timestamp', occurred_at,
        'amount', amount,
        'upi_id', upi_id
    ),
    1.0
FROM transaction_seed
ON CONFLICT (id) DO NOTHING;

UPDATE cases c
SET entity_count = counts.entity_count,
    relationship_count = counts.relationship_count,
    updated_at = NOW()
FROM (
    SELECT
        c2.id,
        count(DISTINCT e.id)::integer AS entity_count,
        count(DISTINCT r.id)::integer AS relationship_count
    FROM cases c2
    LEFT JOIN entities e ON e.case_id = c2.id
    LEFT JOIN relationships r ON r.case_id = c2.id
    GROUP BY c2.id
) counts
WHERE c.id = counts.id;
