import csv
import json
import asyncio
import httpx
import os
import sys
import jwt
from datetime import datetime, timedelta, timezone

BASE_URL = "http://localhost:8000/api/v1"
INGEST_URL = "http://localhost:8001/api/v1"

FIR_PATH = "data/synthetic/fir/fir_records.csv"
CDR_PATH = "data/synthetic/cdr/cdr_records.csv"
TXN_PATH = "data/synthetic/transactions/transactions.csv"
PAT_PATH = "data/synthetic/expected-patterns/expected_patterns.csv"

def get_token():
    payload = {
        "sub": "user-admin-001",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60)
    }
    return jwt.encode(payload, "CRIMELENS_AI_SECRET_KEY_SUPER_SECURE_STUDENT_SIH_TOKEN_2026", algorithm="HS256")

def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

async def main():
    print("--- 1. READING DATA ---")
    firs = read_csv(FIR_PATH)
    cdrs = read_csv(CDR_PATH)
    txns = read_csv(TXN_PATH)
    patterns = read_csv(PAT_PATH)[:10]

    case_map = {f['case_id']: f['case_number'] for f in firs}

    needed_cases = set()
    for p in patterns:
        needed_cases.add(p['case_id_a'])
        needed_cases.add(p['case_id_b'])
        
    for c in cdrs[:100]: needed_cases.add(c['case_id'])
    for t in txns[:100]: needed_cases.add(t['case_id'])

    async with httpx.AsyncClient(timeout=30.0) as client:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # FIR ingest
        print(f"--- 2. INGESTING {len(needed_cases)} FIRS ---")
        for f in firs:
            if f['case_id'] in needed_cases:
                f_dict = dict(f)
                await client.post(f"{INGEST_URL}/ingest/fir", json=f_dict, headers=headers)
                
        # CDR ingest 1
        print("--- 3. INGESTING 100 CDRs (Run 1) ---")
        cdr_c1 = cdr_s1 = 0
        for c in cdrs[:100]:
            if c['case_id'] not in case_map: continue
            c_dict = dict(c)
            # Use authoritative mapping
            c_dict['case_id'] = case_map[c['case_id']]
            r = await client.post(f"{INGEST_URL}/ingest/cdr", json=c_dict, headers=headers)
            j = r.json()
            if j.get('result', {}).get('status') == 'skipped': cdr_s1 += 1
            else: cdr_c1 += 1
            
        print(f"CDR Run 1: Created {cdr_c1}, Skipped {cdr_s1}")
        
        # CDR ingest 2
        print("--- 4. INGESTING 100 CDRs (Run 2) ---")
        cdr_c2 = cdr_s2 = 0
        for c in cdrs[:100]:
            if c['case_id'] not in case_map: continue
            c_dict = dict(c)
            c_dict['case_id'] = case_map[c['case_id']]
            r = await client.post(f"{INGEST_URL}/ingest/cdr", json=c_dict, headers=headers)
            j = r.json()
            if j.get('result', {}).get('status') == 'skipped': cdr_s2 += 1
            else: cdr_c2 += 1
            
        print(f"CDR Run 2: Created {cdr_c2}, Skipped {cdr_s2}")
        
        # TXN ingest 1
        print("--- 5. INGESTING 100 TXNs (Run 1) ---")
        txn_c1 = txn_s1 = 0
        for t in txns[:100]:
            if t['case_id'] not in case_map: continue
            t_dict = dict(t)
            t_dict['case_id'] = case_map[t['case_id']]
            r = await client.post(f"{INGEST_URL}/ingest/transactions", json=t_dict, headers=headers)
            j = r.json()
            if j.get('result', {}).get('status') == 'skipped': txn_s1 += 1
            else: txn_c1 += 1
            
        print(f"TXN Run 1: Created {txn_c1}, Skipped {txn_s1}")
        
        # TXN ingest 2
        print("--- 6. INGESTING 100 TXNs (Run 2) ---")
        txn_c2 = txn_s2 = 0
        for t in txns[:100]:
            if t['case_id'] not in case_map: continue
            t_dict = dict(t)
            t_dict['case_id'] = case_map[t['case_id']]
            r = await client.post(f"{INGEST_URL}/ingest/transactions", json=t_dict, headers=headers)
            j = r.json()
            if j.get('result', {}).get('status') == 'skipped': txn_s2 += 1
            else: txn_c2 += 1
            
        print(f"TXN Run 2: Created {txn_c2}, Skipped {txn_s2}")
        
        # VALIDATE PATTERNS
        print("--- 7. PATTERN VALIDATION ---")
        valid_count = 0
        for p in patterns:
            entity_val = p['entity_value']
            
            ca_num = case_map.get(p['case_id_a'])
            cb_num = case_map.get(p['case_id_b'])
            
            if not ca_num or not cb_num: continue
            
            ca_res = await client.get(f"{BASE_URL}/cases?search={ca_num}", headers=headers)
            cb_res = await client.get(f"{BASE_URL}/cases?search={cb_num}", headers=headers)
            ca_items = ca_res.json().get('items', [])
            cb_items = cb_res.json().get('items', [])
            if not ca_items or not cb_items: continue
            ca_uuid = ca_items[0]['id']
            cb_uuid = cb_items[0]['id']
            
            ca_ents = await client.get(f"{BASE_URL}/cases/{ca_uuid}/entities", headers=headers)
            cb_ents = await client.get(f"{BASE_URL}/cases/{cb_uuid}/entities", headers=headers)
            
            ca_has = any(e['name'] == entity_val for e in ca_ents.json().get('items', []))
            cb_has = any(e['name'] == entity_val for e in cb_ents.json().get('items', []))
            
            if ca_has and cb_has:
                print(f"Pattern {p['pattern_id']} VALIDATED: Entity {entity_val} bridges {ca_num} and {cb_num}")
                valid_count += 1
            else:
                print(f"Pattern {p['pattern_id']} PENDING: Entity {entity_val} not in both cases yet.")
                
        print(f"Total Patterns Materialized: {valid_count}/10")
        
        # GRAPH STATS
        print("--- 8. GRAPH STATS (IN-MEMORY REPOSITORY) ---")
        sample_case = list(needed_cases)[0]
        sample_num = case_map[sample_case]
        sc_res = await client.get(f"{BASE_URL}/cases?search={sample_num}", headers=headers)
        if sc_res.json().get('items'):
            sc_id = sc_res.json()['items'][0]['id']
            g_res = await client.get(f"{BASE_URL}/cases/{sc_id}/graph/stats", headers=headers)
            print("Graph Stats:", json.dumps(g_res.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
