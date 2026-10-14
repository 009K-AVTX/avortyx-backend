def test_health(client):
    assert client.get("/health").get_json() == {"ok": True}


def test_panel_needs_sign_in(client):
    res = client.get("/panel/")
    assert res.status_code == 302 and "/panel/login" in res.headers["Location"]
