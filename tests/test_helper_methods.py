import os
from unittest.mock import MagicMock, patch

import pytest
import requests
from botocore.exceptions import ClientError

SLACK_SERVER = "https://testing.slashpass.co"
PASSWORD_STORAGE = "test-slashpass-storage"
os.environ |= {
    "AWS_LAMBDA_FUNCTION_NAME": "testing",
    "SLACK_SERVER": SLACK_SERVER,
    "PASSWORD_STORAGE": PASSWORD_STORAGE,
    "BIP39": "bip39 seed",
}

from slashpass_private_server.run_server import (
    EncryptionKeyRetrievalError,
    _get_encryption_key,
    _get_s3_object,
    _save_backup_copy,
)


# Test for successful object retrieval
@patch("slashpass_private_server.run_server.s3.get_object")
def test_get_s3_object_success(mock_get_object):
    # Mock the S3 response
    mock_response = MagicMock()
    mock_response["Body"].read.return_value = b"mocked data"
    mock_get_object.return_value = mock_response

    result = _get_s3_object("mock-bucket", "mock-key")
    assert result == b"mocked data"
    mock_get_object.assert_called_once_with(Bucket="mock-bucket", Key="mock-key")


# Test for object not found (NoSuchKey)
@patch("slashpass_private_server.run_server.s3.get_object")
def test_get_s3_object_not_found(mock_get_object):
    mock_get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}}, "GetObject"
    )

    result = _get_s3_object("mock-bucket", "mock-key")
    assert result is None


# Test for other S3 errors
@patch("slashpass_private_server.run_server.s3.get_object")
def test_get_s3_object_other_error(mock_get_object):
    mock_get_object.side_effect = ClientError(
        {"Error": {"Code": "SomeOtherError"}}, "GetObject"
    )

    with pytest.raises(ClientError):
        _get_s3_object("mock-bucket", "mock-key")


# Test when the encryption key is found in S3
@patch("slashpass_private_server.run_server._get_s3_object")
def test_get_encryption_key_from_s3(mock_get_s3_object):
    mock_get_s3_object.return_value = b"public_encryption_key"

    result = _get_encryption_key()
    assert result == b"public_encryption_key"
    mock_get_s3_object.assert_called_once_with(
        PASSWORD_STORAGE, "slack.slashpass.id_rsa.pub"
    )


# Test when the encryption key is not found in S3 and is fetched from SLACK_SERVER
@patch("slashpass_private_server.run_server._get_s3_object")
@patch("slashpass_private_server.run_server.requests.get")
@patch("slashpass_private_server.run_server.s3.put_object")
def test_get_encryption_key_from_slack(
    mock_put_object, mock_requests_get, mock_get_s3_object
):
    mock_get_s3_object.return_value = None
    mock_response = MagicMock()
    mock_response.text = "slack_public_key"
    mock_requests_get.return_value = mock_response

    result = _get_encryption_key()
    assert result == b"slack_public_key"
    mock_requests_get.assert_called_once_with(f"{SLACK_SERVER}/public_key", timeout=5)
    mock_put_object.assert_called_once_with(
        Bucket=PASSWORD_STORAGE,
        Body=b"slack_public_key",
        Key="slack.slashpass.id_rsa.pub",
    )


# Test when encryption key fetch from SLACK_SERVER fails
@patch("slashpass_private_server.run_server._get_s3_object")
@patch("slashpass_private_server.run_server.requests.get")
def test_get_encryption_key_from_slack_failure(mock_requests_get, mock_get_s3_object):
    mock_get_s3_object.return_value = None
    mock_requests_get.side_effect = requests.RequestException("Server error")

    with pytest.raises(EncryptionKeyRetrievalError):
        _get_encryption_key()


# Test for successful backup copy
@patch("slashpass_private_server.run_server.s3.copy_object")
@patch("time.time", return_value=1700000000)
def test_save_backup_copy_success(mock_time, mock_copy_object):
    mock_copy_object.return_value = {}

    result = _save_backup_copy("mock-bucket", "mock-channel", "mock-key")
    assert result is True
    mock_copy_object.assert_called_once_with(
        Bucket="mock-bucket",
        CopySource="mock-bucket/mock-channel/mock-key",
        Key="mock-channel/.mock-key.1700000000",
    )


# Test for failure due to NoSuchKey error
@patch("slashpass_private_server.run_server.s3.copy_object")
def test_save_backup_copy_not_found(mock_copy_object):
    mock_copy_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}}, "CopyObject"
    )

    result = _save_backup_copy("mock-bucket", "mock-channel", "mock-key")
    assert result is False


# Test for other S3 errors
@patch("slashpass_private_server.run_server.s3.copy_object")
def test_save_backup_copy_other_error(mock_copy_object):
    mock_copy_object.side_effect = ClientError(
        {"Error": {"Code": "SomeOtherError"}}, "CopyObject"
    )

    with pytest.raises(ClientError):
        _save_backup_copy("mock-bucket", "mock-channel", "mock-key")
