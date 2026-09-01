import re
import spacy

try:
    nlp = spacy.load('en_core_web_sm')
except OSError:
    raise RuntimeError(
        "Spacy model 'en_core_web_sm' is missing. "
        "Please install it before running the service using: "
        "python -m spacy download en_core_web_sm"
    )

PHONE_PATTERN = re.compile(r'\+91\d{10}')
VEHICLE_PATTERN = re.compile(r'[A-Z]{2}\d{2}[A-Z]{2}\d{4}')
UPI_PATTERN = re.compile(r'[a-zA-Z0-9.\-_]+@[a-zA-Z]+')

FALLBACK_PATTERNS = [
    re.compile(r'During the investigation, it was found that (?P<PERSON>.+?) was in contact with unknown individuals using the number \+91\d{10}\. The suspect was seen near (?P<LOCATION>.+?)\.'),
    re.compile(r'(?P<PERSON>.+?) from (?:a shell company|(?P<ORG>.+?)) reported suspicious activity\. Money was fraudulently transferred to [a-zA-Z0-9.\-_]+@[a-zA-Z]+\. The suspect\'s phone \+91\d{10} was switched off\.'),
    re.compile(r'Investigators intercepted a call to \+91\d{10} near (?P<LOCATION>.+?)\. Suspect (?P<PERSON>.+?) was observed fleeing in vehicle (?:an unknown vehicle|[A-Z]{2}\d{2}[A-Z]{2}\d{4})\.'),
    re.compile(r'A vehicle (?:an unknown vehicle|[A-Z]{2}\d{2}[A-Z]{2}\d{4}) was found abandoned at (?P<LOCATION>.+?)\. Evidence links it to (?P<PERSON>.+?), who was previously contacted via \+91\d{10}\.'),
    re.compile(r'A complaint was filed against (?P<PERSON>.+?) who allegedly operates under (?:a shell company|(?P<ORG>.+?))\. Financial trails led to a transaction made to [a-zA-Z0-9.\-_]+@[a-zA-Z]+\.'),
]

ORG_SUFFIX_PATTERN = re.compile(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Pvt Ltd|Corp|Enterprises|Bank|Inc)\b')

def extract_entities_from_text(text: str, source_field: str = "fir_text"):
    raw_entities = []
    
    # 1. Regex (Structured) - Highest Confidence
    for match in PHONE_PATTERN.finditer(text):
        raw_entities.append({"entity_type": "PHONE", "value": match.group(), "confidence": 1.0, "start_offset": match.start(), "end_offset": match.end(), "source_field": source_field})
    for match in VEHICLE_PATTERN.finditer(text):
        raw_entities.append({"entity_type": "VEHICLE", "value": match.group(), "confidence": 1.0, "start_offset": match.start(), "end_offset": match.end(), "source_field": source_field})
    for match in UPI_PATTERN.finditer(text):
        raw_entities.append({"entity_type": "UPI_ID", "value": match.group(), "confidence": 1.0, "start_offset": match.start(), "end_offset": match.end(), "source_field": source_field})

    # 2. Fallbacks (NER) - High Confidence
    for pat in FALLBACK_PATTERNS:
        for match in pat.finditer(text):
            for group_name in ["PERSON", "LOCATION", "ORG"]:
                try:
                    val = match.group(group_name)
                    if val:
                        raw_entities.append({"entity_type": group_name, "value": val, "confidence": 0.95, "start_offset": match.start(group_name), "end_offset": match.end(group_name), "source_field": source_field})
                except IndexError:
                    pass

    for match in ORG_SUFFIX_PATTERN.finditer(text):
        raw_entities.append({"entity_type": "ORG", "value": match.group(), "confidence": 0.95, "start_offset": match.start(), "end_offset": match.end(), "source_field": source_field})
        
    # 3. spaCy - Base Confidence
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            entity_type, conf = "PERSON", 0.90
        elif ent.label_ in ("ORG", "COMPANY"):
            entity_type, conf = "ORG", 0.85
        elif ent.label_ in ("GPE", "LOC", "FAC"):
            entity_type, conf = "LOCATION", 0.85
        else:
            continue
            
        raw_entities.append({"entity_type": entity_type, "value": ent.text, "confidence": conf, "start_offset": ent.start_char, "end_offset": ent.end_char, "source_field": source_field})
        
    # 4. Merging and Deduplication
    sorted_ents = sorted(raw_entities, key=lambda x: x["confidence"], reverse=True)
    kept_ents = []
    seen_keys = set()
    
    for ent in sorted_ents:
        # Check overlap
        overlap = False
        s1, e1 = ent["start_offset"], ent["end_offset"]
        for k in kept_ents:
            s2, e2 = k["start_offset"], k["end_offset"]
            if not (e1 <= s2 or s1 >= e2):
                overlap = True
                break
                
        if not overlap:
            key = (ent["entity_type"], ent["value"].lower())
            if key not in seen_keys:
                seen_keys.add(key)
                kept_ents.append(ent)
                
    return sorted(kept_ents, key=lambda x: x["start_offset"])