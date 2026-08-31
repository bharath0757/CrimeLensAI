import asyncio
import csv
import sys
sys.path.insert(0, 'services/ingestion-service')
from app.services.pipeline import process_fir, FIRPayload

async def main():
    with open('data/synthetic/fir/fir_records.csv', 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
        
    records_to_process = reader[:20]
    
    print('--- FIRST RUN ---')
    totals = {}
    total_entities = 0
    
    for r in records_to_process:
        payload = FIRPayload(**r)
        res = await process_fir(payload)
        
        counts_by_type = {}
        for ent in res['entities']:
            t = ent['entity_type']
            counts_by_type[t] = counts_by_type.get(t, 0) + 1
            totals[t] = totals.get(t, 0) + 1
            
        print(f"Case: {res['case_id']}, Extracted: {res['extracted_count']}, Saved: {res['saved_count']}, Breakdown: {counts_by_type}")
        total_entities += res['saved_count']
        
    print(f"Aggregate Totals: {total_entities} entities saved. Breakdown: {totals}")
    
    print('\n--- SECOND RUN (IDEMPOTENCY) ---')
    duplicates = 0
    for r in records_to_process:
        payload = FIRPayload(**r)
        res = await process_fir(payload)
        duplicates += res['saved_count']
        if res['saved_count'] > 0:
            print(f"ERROR: Duplicate entities saved for {res['case_id']}!")
            
    print(f"Second run saved {duplicates} duplicate entities.")
    if duplicates == 0:
        print("IDEMPOTENCY VERIFIED: 0 duplicates created.")
        
asyncio.run(main())
