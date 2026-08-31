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

# Regex patterns for deterministic extraction
PHONE_PATTERN = re.compile(r'\+91\d{10}')
VEHICLE_PATTERN = re.compile(r'[A-Z]{2}\d{2}[A-Z]{2}\d{4}')
UPI_PATTERN = re.compile(r'[a-zA-Z0-9.\-_]+@[a-zA-Z]+')

def extract_entities_from_text(text: str, source_field: str = "fir_text"):
    entities = []
    
    # Deterministic Rule-Based Extraction
    for match in PHONE_PATTERN.finditer(text):
        entities.append({
            "entity_type": "PHONE",
            "value": match.group(),
            "confidence": 1.0,
            "start_offset": match.start(),
            "end_offset": match.end(),
            "source_field": source_field
        })
        
    for match in VEHICLE_PATTERN.finditer(text):
        entities.append({
            "entity_type": "VEHICLE",
            "value": match.group(),
            "confidence": 1.0,
            "start_offset": match.start(),
            "end_offset": match.end(),
            "source_field": source_field
        })
        
    for match in UPI_PATTERN.finditer(text):
        entities.append({
            "entity_type": "UPI_ID",
            "value": match.group(),
            "confidence": 1.0,
            "start_offset": match.start(),
            "end_offset": match.end(),
            "source_field": source_field
        })
        
    # NLP / NER Extraction
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            entity_type = "PERSON"
            confidence = 0.90
        elif ent.label_ in ("ORG", "COMPANY"):
            entity_type = "ORG"
            confidence = 0.85
        elif ent.label_ in ("GPE", "LOC", "FAC"):
            entity_type = "LOCATION"
            confidence = 0.85
        else:
            continue
            
        entities.append({
            "entity_type": entity_type,
            "value": ent.text,
            "confidence": confidence,
            "start_offset": ent.start_char,
            "end_offset": ent.end_char,
            "source_field": source_field
        })
        
    return entities
