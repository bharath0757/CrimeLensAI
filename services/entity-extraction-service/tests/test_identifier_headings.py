"""Named-entity labels must not create false graph locations for identifier headings."""

from app.extractors import pipeline


def test_upi_heading_is_not_a_location_when_followed_by_a_payment_handle(monkeypatch):
    narrative = "Payment to UPI demo26189@upi was reported in Lucknow."
    offset = narrative.index("UPI")
    monkeypatch.setattr(pipeline, "extract_spacy_entities", lambda _: [{
        "entity_type": "LOCATION", "value": "UPI", "start_offset": offset,
        "end_offset": offset + 3, "confidence": .7,
    }])
    mentions = pipeline.run_extraction(narrative, "fir_text")
    assert any(mention.entity_type == "UPI_ID" and mention.value == "demo26189@upi" for mention in mentions)
    assert not any(mention.value == "UPI" for mention in mentions)


def test_heading_filter_does_not_globally_blacklist_a_person_name(monkeypatch):
    narrative = "Pan spoke to the investigator."
    monkeypatch.setattr(pipeline, "extract_spacy_entities", lambda _: [{
        "entity_type": "PERSON", "value": "Pan", "start_offset": 0,
        "end_offset": 3, "confidence": .7,
    }])
    assert any(mention.value == "Pan" for mention in pipeline.run_extraction(narrative, "fir_text"))
