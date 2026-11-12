def test_unknown_route_is_404_envelope(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "not_found"
    assert isinstance(body["message"], str)


def test_wrong_method_is_405_envelope(client):
    response = client.delete("/api/session")
    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"


def test_validation_error_envelope(client):
    response = client.put("/api/preferences", content=b"not json",
                          headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert body["details"]["errors"]


def test_screenshot_route_rejects_bad_names_and_serves_png(client, app):
    assert client.get("/api/screenshots/..%2Fstate.json").status_code == 404
    assert client.get("/api/screenshots/missing.png").json()["code"] == "not_found"
    png = b"\x89PNG\r\n\x1a\nfake"
    (app.state.store.dir("screenshots") / "job-1-filled.png").write_bytes(png)
    response = client.get("/api/screenshots/job-1-filled.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == png


def test_cors_allows_vite_origin(client):
    response = client.options("/api/session", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
