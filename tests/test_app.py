from fastapi.testclient import TestClient
from app.main import app

def test_home_and_pages():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/faq").status_code == 200
        assert client.get("/errors").status_code == 200

def test_seeded_faqs_and_errors():
    with TestClient(app) as client:
        assert len(client.get("/api/faqs").json()) >= 10
        codes = {x["code"] for x in client.get("/api/errors").json()}
        assert {400,401,403,404,429,500,503,460}.issubset(codes)

def test_custom_404():
    with TestClient(app) as client:
        response = client.get("/this-route-does-not-exist")
        assert response.status_code == 404
        assert "gone off the map" in response.text

def test_chat_error_code():
    with TestClient(app) as client:
        data = client.post("/api/chat", json={"message":"Explain error 404","session_id":"test"}).json()
        assert "404" in data["answer"]
