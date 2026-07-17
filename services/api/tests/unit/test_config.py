import pytest

from creditops.config import Settings


def test_non_synthetic_data_class_is_rejected() -> None:
    with pytest.raises(ValueError, match="synthetic"):
        Settings(app_env="development", data_class="customer")


def test_database_credentials_are_redacted_from_settings_repr() -> None:
    settings = Settings(database_url="postgresql://user:secret-password@database.test/db")

    assert "secret-password" not in repr(settings)


def test_production_rejects_non_https_jwks_url() -> None:
    with pytest.raises(ValueError, match="OIDC_JWKS_URL.*HTTPS"):
        Settings(
            app_env="production",
            database_url="postgresql://database.test/creditops",
            oidc_issuer="https://identity.example",
            oidc_audience="creditops-api",
            oidc_jwks_url="http://identity.example/.well-known/jwks.json",
        )
