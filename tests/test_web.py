from fastapi.testclient import TestClient


def test_home_and_run_pages_render_and_label_mocks(monkeypatch, make_orch, brief):
    import app.main as main
    orch = make_orch()
    monkeypatch.setattr(main, "orch", orch)
    c = TestClient(main.app)
    home = c.get("/")
    assert home.status_code == 200 and "MOCKED" in home.text and "STUBBED" in home.text
    st = orch.start(brief)
    page = c.get(f"/runs/{st.run_id}")
    assert page.status_code == 200 and "Your approval is needed" in page.text
    _, q = orch.load(st.run_id)
    orch.approve(st.run_id, q.pending()[0].id, True)
    page = c.get(f"/runs/{st.run_id}")
    assert "Your decision is needed" in page.text and "(recommended)" in page.text
    assert c.get("/api/decision-log/validate").json()["valid"]
