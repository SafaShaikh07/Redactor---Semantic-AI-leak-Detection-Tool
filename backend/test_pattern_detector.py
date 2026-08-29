from pattern_detector import scan_and_redact

def test_api_key():
    text = "My key is sk-123456789012345678901234"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "api_key" in reasons
    assert "[REDACTED: api_key]" in redacted
    assert len(spans) == 1
    assert spans[0]["reason"] == "api_key"

def test_email():
    text = "Contact me at user@example.com for info"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "email" in reasons
    assert "[REDACTED: email]" in redacted

def test_project_codename():
    text = "Details on Project Apollo are classified"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "project_codename" in reasons
    assert "[REDACTED: project_codename]" in redacted

def test_db_connection_string():
    text = "Connect via postgresql://admin:secret123@db.internal:5432/Customer_Master"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "db_connection_string" in reasons
    assert "postgresql://[REDACTED: db_connection_string]/Customer_Master" in redacted

def test_pan_number():
    text = "My PAN number is ABCDE1234F."
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "pan_number" in reasons
    assert "[REDACTED: pan_number]" in redacted

def test_phone_number():
    text = "Call +91-9876543210 or (555) 123-4567 today."
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "phone_number" in reasons
    assert "[REDACTED: phone_number]" in redacted

def test_generic_secret_assignment():
    text = "MY_TOKEN=abc12345\nDB_PASSWORD: supersecretpass"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "generic_secret_assignment" in reasons
    assert "MY_TOKEN=[REDACTED: generic_secret_assignment]" in redacted
    assert "DB_PASSWORD: [REDACTED: generic_secret_assignment]" in redacted

def test_private_key_block():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "private_key_block" in reasons
    assert "[REDACTED: private_key_block]" in redacted

def test_credit_card():
    # Valid Visa card vs invalid number
    text = "Valid: 4532 0151 1283 0366, Invalid: 1234 5678 9012 3456"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "credit_card" in reasons
    assert "Valid: [REDACTED: credit_card]" in redacted
    assert "Invalid: 1234 5678 9012 3456" in redacted

def test_ssn():
    text = "Social security: 123-45-6789"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "ssn" in reasons
    assert "[REDACTED: ssn]" in redacted

def test_aadhaar_number():
    text = "Aadhaar number is 3675 9834 6012"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "aadhaar_number" in reasons
    assert "[REDACTED: aadhaar_number]" in redacted

def test_ip_address():
    text = "Local IP is 192.168.1.50 and Public DNS is 8.8.8.8"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "ip_address:private" in reasons
    assert "ip_address:public" in reasons
    assert "[REDACTED: ip_address:private]" in redacted
    assert "[REDACTED: ip_address:public]" in redacted

def test_crypto_wallet():
    text = "BTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa and ETH: 0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert "crypto_wallet" in reasons
    assert "BTC: [REDACTED: crypto_wallet]" in redacted
    assert "ETH: [REDACTED: crypto_wallet]" in redacted

def test_multiple_categories():
    text = "User user@example.com with PAN ABCDE1234F called +1-555-123-4567"
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert has_secrets
    assert set(reasons) == {"email", "pan_number", "phone_number"}
    assert "[REDACTED: email]" in redacted
    assert "[REDACTED: pan_number]" in redacted
    assert "[REDACTED: phone_number]" in redacted

def test_no_false_positives():
    text = "In year 2026, we counted 5000 items and 123 apples."
    redacted, has_secrets, reasons, spans = scan_and_redact(text)
    assert not has_secrets
    assert reasons == []
    assert redacted == text

def test_severity_levels():
    # BLOCK-level categories
    _, _, _, spans1 = scan_and_redact("My SSN is 123-45-6789")
    assert spans1[0]["severity"] == "block"

    _, _, _, spans2 = scan_and_redact("Aadhaar 3675 9834 6012")
    assert spans2[0]["severity"] == "block"

    _, _, _, spans3 = scan_and_redact("-----BEGIN RSA PRIVATE KEY-----\nkey\n-----END RSA PRIVATE KEY-----")
    assert spans3[0]["severity"] == "block"

    # DB connection with password -> block
    _, _, _, spans4 = scan_and_redact("postgresql://admin:secret123@db.internal/Customer_Master")
    assert spans4[0]["severity"] == "block"

    # DB connection without password -> redact
    _, _, _, spans5 = scan_and_redact("postgresql://admin@db.internal/Customer_Master")
    assert spans5[0]["severity"] == "redact"

    # REDACT-level categories
    _, _, _, spans6 = scan_and_redact("sk-123456789012345678901234 user@example.com")
    assert all(s["severity"] == "redact" for s in spans6)

if __name__ == "__main__":
    test_api_key()
    test_email()
    test_project_codename()
    test_db_connection_string()
    test_pan_number()
    test_phone_number()
    test_generic_secret_assignment()
    test_private_key_block()
    test_credit_card()
    test_ssn()
    test_aadhaar_number()
    test_ip_address()
    test_crypto_wallet()
    test_multiple_categories()
    test_no_false_positives()
    test_severity_levels()
    print("All tests passed!")
