import os,base64,pytest
@pytest.fixture(autouse=True)
def test_mfa_key(monkeypatch):
    monkeypatch.setenv("TAF_MFA_ENCRYPTION_KEY",base64.urlsafe_b64encode(b"test-only-key-for-warehouse-1234").decode())
