from app.core.config import settings


def test_allowed_frontend_can_read_export_verification_headers(client):
    origin = settings.ALLOWED_ORIGINS[0]
    response = client.get("/health", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin
    exposed = {item.strip().lower() for item in response.headers["access-control-expose-headers"].split(",")}
    assert {"content-disposition", "x-report-sha256", "x-audit-event-id"} <= exposed


def test_untrusted_origin_is_not_allowed(client):
    response = client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_frontend_authorization_preflight(client):
    response = client.options("/api/v1/cases", headers={
        "Origin": settings.ALLOWED_ORIGINS[0],
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == settings.ALLOWED_ORIGINS[0]
