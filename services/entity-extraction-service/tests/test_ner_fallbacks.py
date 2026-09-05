from app.services.extractor import extract_entities_from_text


def test_person_fallback_title():
    text = "A complaint was filed against Anjali Gupta who allegedly operates under a shell company. Financial trails led to a transaction made to anjali6963@oksbi."
    ents = extract_entities_from_text(text)
    
    persons = [e for e in ents if e["entity_type"] == "PERSON"]
    assert len(persons) == 1
    assert persons[0]["value"] == "Anjali Gupta"
    assert persons[0]["confidence"] == 0.75
    
def test_location_fallback():
    text = "A vehicle an unknown vehicle was found abandoned at Andheri West. Evidence links it to Priya Sharma, who was previously contacted via +910134604279."
    ents = extract_entities_from_text(text)
    
    locations = [e for e in ents if e["entity_type"] == "LOCATION"]
    assert len(locations) >= 1
    # One of them should be Andheri West
    assert any(location["value"] == "Andheri West" for location in locations)
    
def test_org_fallback():
    text = "Suresh Rao from Apex Trading reported suspicious activity. Money was fraudulently transferred to priya7684@upi. The suspect's phone +915527465681 was switched off."
    ents = extract_entities_from_text(text)
    
    orgs = [e for e in ents if e["entity_type"] == "ORG"]
    assert len(orgs) == 1
    assert orgs[0]["value"] == "Apex Trading"
    
def test_org_suffix_fallback():
    text = "The transactions were routed to Zeta Corp before being transferred."
    ents = extract_entities_from_text(text)
    
    orgs = [e for e in ents if e["entity_type"] == "ORG"]
    assert any(o["value"] == "Zeta Corp" for o in orgs)
