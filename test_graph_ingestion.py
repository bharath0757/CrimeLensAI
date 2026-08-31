import asyncio
import csv
import json
import httpx
import sys

# Need to fix python path
sys.path.append('services/ingestion-service')

from app.services.pipeline import process_fir, process_cdr, process_transaction, FIRPayload, CDRPayload, TransactionPayload

FIR_PATH = 'data/synthetic/fir/fir_records.csv'
CDR_PATH = 'data/synthetic/cdr/cdr_records.csv'
TXN_PATH = 'data/synthetic/transactions/transactions.csv'
PAT_PATH = 'data/synthetic/expected-patterns/expected_patterns.csv'

def read_csv(path, limit=None):
    with open(path, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
        if limit:
            return reader[:limit]
        return reader

async def main():
    print("--- STARTING GRAPH TEST ---")
    cdrs = read_csv(CDR_PATH, 100)
    txns = read_csv(TXN_PATH, 100)
    
    needed_cases = set()
    for c in cdrs: needed_cases.add(c['case_id'])
    for t in txns: needed_cases.add(t['case_id'])
    
    firs = read_csv(FIR_PATH)
    firs_to_process = [f for f in firs if f['case_id'] in needed_cases]
    
    print(f"Ingesting {len(firs_to_process)} FIRs to seed cases...")
    for f in firs_to_process:
        payload = FIRPayload(**f)
        await process_fir(payload)
            
    print(f"Ingesting {len(cdrs)} CDRs...")
    for i in range(2):
        created = 0
        skipped = 0
        for c in cdrs:
            c_dict = dict(c)
            c_dict['duration_seconds'] = int(c_dict['duration_seconds'])
            res = await process_cdr(CDRPayload(**c_dict))
            if res['status'] == 'created': created += 1
            elif res['status'] == 'skipped': skipped += 1
        print(f"CDR Run {i+1}: Created {created}, Skipped {skipped}")
        
    print(f"Ingesting {len(txns)} Transactions...")
    for i in range(2):
        created = 0
        skipped = 0
        for t in txns:
            t_dict = dict(t)
            t_dict['amount'] = float(t_dict['amount'])
            res = await process_transaction(TransactionPayload(**t_dict))
            if res['status'] == 'created': created += 1
            elif res['status'] == 'skipped': skipped += 1
        print(f"TXN Run {i+1}: Created {created}, Skipped {skipped}")
        
    print("--- GRAPH VALIDATION ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        test_case = firs_to_process[0]['case_number']
        print(f"Querying stats for case {test_case}...")
        c_res = await client.get(f"http://127.0.0.1:8000/api/v1/cases?search={test_case}")
        c_id = c_res.json()['items'][0]['id']
        stats_res = await client.get(f"http://127.0.0.1:8000/api/v1/cases/{c_id}/graph/stats")
        print("Stats:", json.dumps(stats_res.json(), indent=2))
        
        # Test expected patterns
        pats = read_csv(PAT_PATH)
        print("Validating first 5 expected patterns...")
        for p in pats[:5]:
            print(f"Pattern {p['pattern_id']}: {p['entity_value']} expected in {p['case_id_a']} and {p['case_id_b']}")

if __name__ == '__main__':
    asyncio.run(main())
