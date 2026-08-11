from app.main import app

def test_openapi_contains_quality_api_surface_and_security():
    document = app.openapi()
    paths = document["paths"]
    expected = {"/api/v1/auth/login", "/api/v1/results", "/api/v1/models", "/api/v1/evaluations", "/api/v1/reports"}
    assert expected <= paths.keys()
    assert any(p["name"] == "keyword" for p in paths["/api/v1/results"]["get"]["parameters"])
    assert any("HTTPBearer" in key or "OAuth2" in key for key in document["components"]["securitySchemes"])
