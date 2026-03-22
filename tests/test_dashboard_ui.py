from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_dashboard_page_serves_react_entry() -> None:
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "__dashboardConfig" in response.text
    assert '<div id="root"></div>' in response.text
    assert "/dashboard-static/assets/dashboard-app.js" in response.text
    assert "/dashboard-static/assets/dashboard-app.css" in response.text


def test_dashboard_spa_fallback_is_available() -> None:
    response = client.get("/dashboard/openclaw")

    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text
    assert "/dashboard-static/assets/dashboard-app.js" in response.text


def test_dashboard_legacy_page_is_available() -> None:
    response = client.get("/dashboard-legacy")

    assert response.status_code == 200
    assert "CEO Dashboard" in response.text
    assert "Feishu Ops" in response.text
    assert "/dashboard-legacy-static/dashboard.js" in response.text


def test_dashboard_static_assets_are_served() -> None:
    js_response = client.get("/dashboard-static/assets/dashboard-app.js")
    css_response = client.get("/dashboard-static/assets/dashboard-app.css")
    legacy_js_response = client.get("/dashboard-legacy-static/dashboard.js")

    assert js_response.status_code == 200
    assert "createRoot" in js_response.text
    assert "CEO Dashboard" in js_response.text
    assert css_response.status_code == 200
    assert ":root" in css_response.text
    assert legacy_js_response.status_code == 200
    assert "refreshAll" in legacy_js_response.text


def test_openclaw_control_ui_launch_redirects() -> None:
    response = client.get("/openclaw-control-ui/launch", follow_redirects=False)

    assert response.status_code in {302, 307}
    location = response.headers["location"]
    assert location.startswith("http://127.0.0.1:18789/")
    assert "#token=" in location
