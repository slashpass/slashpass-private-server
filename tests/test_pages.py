import os
from unittest.mock import MagicMock, patch

import pytest
from flask.testing import FlaskClient

SLACK_SERVER = "https://testing.slashpass.co"
PASSWORD_STORAGE = "test-slashpass-storage"
os.environ |= {
    "AWS_LAMBDA_FUNCTION_NAME": "testing",
    "SLACK_SERVER": SLACK_SERVER,
    "PASSWORD_STORAGE": PASSWORD_STORAGE,
    "BIP39": "bip39 seed",
}

from slashpass_private_server.run_server import public_key, server


@pytest.fixture
def client() -> FlaskClient:
    """Fixture to get the Flask test client."""
    with server.test_client() as client:
        yield client


# Test for status page
def test_status_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Server status:" in response.data


# Test for stats page with mocked S3 response
@patch("slashpass_private_server.run_server.s3.list_objects")
def test_stats_page(mock_list_objects, client):
    # Mock the S3 response with some objects
    mock_list_objects.return_value = {
        "Contents": [
            {"Key": "ABC123/secret1"},
            {"Key": "XYZ321/secret2"},
            {"Key": "secret3"},
            {"Key": "ABC123/secret4"},
        ]
    }

    response = client.get("/stats")
    assert response.status_code == 200
    assert b"Total secrets" in response.data
    assert b'<span class="stat number">3/20</span>' in response.data
    assert b"Total channels with secrets" in response.data
    assert b'<span class="stat number">2</span>' in response.data


# Test for retrieving the public key
def test_get_public_key(client):
    response = client.get("/public_key")
    assert response.status_code == 200
    assert b"-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAA" in response.data


@patch("slashpass_private_server.run_server._get_s3_object")
@patch("slashpass_private_server.run_server.decrypt")
@patch("slashpass_private_server.run_server.encrypt")
@patch("slashpass_private_server.run_server.OneTimeSecretCli")
@patch("slashpass_private_server.run_server._get_encryption_key")
def test_get_onetime_link_success(
    mock_get_encryption_key,
    mock_one_time_secret_cli,
    mock_encrypt,
    mock_decrypt,
    mock_get_s3_object,
    client,
):
    # Mocking the dependencies
    mock_get_s3_object.return_value = b"encrypted_secret"
    mock_decrypt.return_value = "decrypted_secret"
    mock_encryption_key = b"encryption_key"
    mock_get_encryption_key.return_value = mock_encryption_key
    mock_cli = MagicMock()
    mock_one_time_secret_cli.return_value = mock_cli
    mock_cli.create_link.return_value = "mock_link"
    mock_encrypt.return_value = b"encrypted_link"

    response = client.post("/onetime_link", data={"secret": "mock_secret"})
    assert response.status_code == 200
    assert response.data == b"encrypted_link"


# Test for listing secrets
@patch("slashpass_private_server.run_server.encrypt")
@patch("slashpass_private_server.run_server._get_encryption_key")
@patch("slashpass_private_server.run_server.s3.list_objects")
def test_list_secrets(mock_list_objects, mock_get_encryption_key, mock_encrypt, client):
    # Mocking the S3 response
    mock_list_objects.return_value = {
        "Contents": [
            {"Key": "channel1/secret1"},
            {"Key": "channel2/secret2"},
            {"Key": "secret3"},
        ]
    }
    mock_get_encryption_key.return_value = public_key
    mock_encrypt.side_effect = lambda data, key, _: data

    response = client.post("/list/secret")
    assert response.status_code == 200
    assert (
        mock_encrypt.call_args_list[0][0][0]
        == b"channel1/secret1\nchannel2/secret2\nsecret3"
    )


# Test for insert (GET and POST)
@patch("slashpass_private_server.run_server.requests.get")
@patch("slashpass_private_server.run_server.s3.put_object")
@patch("slashpass_private_server.run_server._save_backup_copy")
def test_insert(mock_save_backup_copy, mock_put_object, mock_requests_get, client):
    mock_requests_get.return_value = MagicMock(status_code=200, text="mock_path")

    # Test GET request
    response = client.get("/insert/mock_token")
    assert response.status_code == 200
    assert b"[slashpass] mock_path secret" in response.data

    # Test POST request
    mock_save_backup_copy.return_value = True
    response = client.post(
        "/insert/mock_token", data={"secret": "secret_value", "encrypted": False}
    )
    assert response.status_code == 200
    assert b"[slashpass] Success" in response.data


# Test for remove
@patch("slashpass_private_server.run_server.s3.delete_object")
@patch("slashpass_private_server.run_server._save_backup_copy")
def test_remove(mock_save_backup_copy, mock_delete_object, client):
    mock_save_backup_copy.return_value = True

    response = client.post(
        "/remove", data={"channel": "mock_channel", "app": "mock_app"}
    )
    assert response.status_code == 200
    assert b"ok" in response.data
    mock_delete_object.assert_called_once_with(
        Bucket=PASSWORD_STORAGE, Key="mock_channel/mock_app"
    )
