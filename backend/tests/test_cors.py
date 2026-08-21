from fastapi.testclient import TestClient

from server import app


def test_authenticated_browser_preflight_allows_request_id_header():
    response = TestClient(app).options(
        "/api/transcribe-audio?retain=false",
        headers={
            "Origin": "https://xtox.celladoresystems.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-request-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://xtox.celladoresystems.com"
    )
    assert "X-Request-ID" in response.headers["access-control-allow-headers"]
