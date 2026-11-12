"""
Tests: Fernet credential encryption for ExternalSystem.
"""
import pytest
from integrations.encryption import encrypt_credentials, decrypt_credentials, is_encrypted


class TestEncryptionHelpers:

    def test_encrypt_returns_enc_wrapper(self, settings):
        from cryptography.fernet import Fernet
        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
        result = encrypt_credentials({"api_key": "secret123"})
        assert "_enc" in result
        assert result["_enc"].startswith("fernet:")

    def test_decrypt_roundtrip(self, settings):
        from cryptography.fernet import Fernet
        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
        original = {"api_key": "secret", "username": "admin", "password": "pw"}
        encrypted = encrypt_credentials(original)
        assert is_encrypted(encrypted)
        decrypted = decrypt_credentials(encrypted)
        assert decrypted == original

    def test_no_key_returns_plaintext_with_warning(self, settings):
        settings.FIELD_ENCRYPTION_KEY = ""
        data = {"api_key": "will_be_plaintext"}
        result = encrypt_credentials(data)
        assert result == data  # stored as-is
        assert not is_encrypted(result)

    def test_decrypt_plaintext_returns_original(self, settings):
        settings.FIELD_ENCRYPTION_KEY = ""
        plain = {"api_key": "legacy_plaintext"}
        result = decrypt_credentials(plain)
        assert result == plain

    def test_decrypt_empty_returns_empty(self):
        assert decrypt_credentials({}) == {}
        assert decrypt_credentials(None) == {}

    def test_is_encrypted_false_for_plain(self):
        assert not is_encrypted({"api_key": "abc"})
        assert not is_encrypted({})

    def test_different_keys_cannot_decrypt(self, settings):
        from cryptography.fernet import Fernet
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        settings.FIELD_ENCRYPTION_KEY = key1
        encrypted = encrypt_credentials({"secret": "value"})

        settings.FIELD_ENCRYPTION_KEY = key2
        result = decrypt_credentials(encrypted)
        # Should return empty dict on decryption failure
        assert result == {}


@pytest.mark.django_db
class TestExternalSystemEncryption:

    def test_model_save_encrypts_credentials(self, settings, db):
        from cryptography.fernet import Fernet
        from integrations.models import ExternalSystem

        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()

        system = ExternalSystem.objects.create(
            name="Test DHIS2",
            system_code="TEST_DHIS2",
            system_type="DHIS2",
            base_url="https://dhis2.example.com",
            auth_type="BASIC",
            credentials={"username": "admin", "password": "secret"},
        )
        # Reload from DB
        system.refresh_from_db()
        assert is_encrypted(system.credentials)

    def test_get_credentials_decrypts(self, settings, db):
        from cryptography.fernet import Fernet
        from integrations.models import ExternalSystem

        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()

        system = ExternalSystem.objects.create(
            name="Test SORMAS",
            system_code="TEST_SORMAS",
            system_type="SORMAS",
            base_url="https://sormas.example.com",
            auth_type="API_KEY",
            credentials={"api_key": "my-secret-key"},
        )
        system.refresh_from_db()
        plain = system.get_credentials()
        assert plain["api_key"] == "my-secret-key"
