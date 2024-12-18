import json
import os
import re
import time

import boto3
import requests
import urllib3
from botocore.exceptions import ClientError
from flask import Flask, abort, render_template, request
from onetimesecret import OneTimeSecretCli
from rsa import decrypt, encrypt, generate_key
from urllib3.exceptions import HTTPError

server = Flask(__name__)


class EncryptionKeyRetrievalError(Exception):
    """Exception raised when an encryption key cannot be retrieved from the server."""


if (
    os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is None
):  # If the app is NOT running on Lambda, load the development environment variables
    with open("zappa_settings.json") as json_data:
        env_vars = json.load(json_data)["dev"]["environment_variables"]
        os.environ |= env_vars


AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_S3_REGION = os.environ.get("AWS_S3_REGION", "us-east-1")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
ONETIMESECRET_KEY = os.environ.get("ONETIMESECRET_KEY", None)
ONETIMESECRET_USER = os.environ.get("ONETIMESECRET_USER", None)
ONETIMESECRET_REGION = os.environ.get("ONETIMESECRET_REGION", "us")
PASSWORD_STORAGE = os.environ.get("PASSWORD_STORAGE")
SLACK_SERVER = os.environ.get("SLACK_SERVER", "https://slack.slashpass.co")

secret_key = generate_key(os.environ.get("BIP39"))
private_key = secret_key.exportKey("PEM")
public_key = secret_key.publickey().exportKey("PEM")

s3 = boto3.client(
    "s3",
    region_name=AWS_S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


def _get_s3_object(bucket: str, key: str) -> bytes:
    """Retrieve an object from S3, or return None if not found."""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ["NoSuchKey", "NoSuchBucket"]:
            return None
        raise


def _get_encryption_key() -> bytes:
    """Retrieve the public encryption key, or fetch and store it if missing."""
    bucket, key = PASSWORD_STORAGE, "slack.slashpass.id_rsa.pub"

    if encryption_key := _get_s3_object(bucket, key):
        return encryption_key

    # Fetch from SLACK_SERVER if not found in S3
    encryption_key_url = f"{SLACK_SERVER}/public_key"
    http = urllib3.PoolManager()

    try:
        response = http.request("GET", encryption_key_url, timeout=5)
        if response.status != 200:
            raise HTTPError(f"Request failed with status {response.status}")
    except (HTTPError, urllib3.exceptions.RequestError) as e:
        raise EncryptionKeyRetrievalError(
            f"Unable to retrieve {key} from {encryption_key_url}: {str(e)}"
        ) from e

    s3.put_object(Bucket=bucket, Body=response.data, Key=key)
    return response.data


def _save_backup_copy(bucket: str, channel: str, key: str) -> bool:
    """Creates a timestamped backup copy of an object in an S3 bucket"""
    path_parts = key.split("/")
    file = path_parts.pop()
    route = "/".join(path_parts) + "/" if path_parts else ""
    backup_key = f"{channel}/{route}.{file}.{int(time.time())}"
    try:
        s3.copy_object(
            Bucket=bucket, CopySource=f"{bucket}/{channel}/{key}", Key=backup_key
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ["NoSuchKey", "NoSuchBucket"]:
            return False
        raise


@server.route("/", methods=["GET"])
def status_page():
    return render_template("status.html")


@server.route("/stats", methods=["GET"])
def stats_page():
    bucket = s3.list_objects(Bucket=PASSWORD_STORAGE)
    channels = set()
    total_secrets = 0
    for obj in bucket["Contents"]:
        if not re.compile(r".+/\.").match(obj["Key"]):
            total_secrets += 1

        if channel := re.compile("^[A-Z0-9]+/").match(obj["Key"]):
            channels.add(channel[0])

    return render_template(
        "admin.html", total_secrets=total_secrets - 1, total_channels=len(channels)
    )


@server.route("/public_key", methods=["GET"])
def get_public_key():
    return public_key


@server.route("/onetime_link", methods=["POST"])
def get_onetime_link():
    cli = OneTimeSecretCli(ONETIMESECRET_USER, ONETIMESECRET_KEY, ONETIMESECRET_REGION)
    try:
        if response := _get_s3_object(PASSWORD_STORAGE, request.form["secret"]):
            secret = decrypt(response, private_key)
            encryption_key = _get_encryption_key()
            # the link is encrypted to be decrypted by the slack server
            return encrypt(cli.create_link(secret), encryption_key)
        abort(404)
    except ClientError:
        abort(500)


@server.route("/list/<prefix>", methods=["POST"])
def list_secrets(prefix):
    output = ""
    chunk_size = 214  # assuming 2048 bits key
    try:
        bucket = s3.list_objects(Bucket=PASSWORD_STORAGE, Prefix=prefix)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchBucket":
            s3.create_bucket(Bucket=PASSWORD_STORAGE)
        else:
            raise
    else:
        if "Contents" in bucket:
            output = "\n".join(
                [
                    x["Key"]
                    for x in bucket["Contents"]
                    if not re.match(r".+\/\.\w+", x["Key"])
                ]
            )

    output_bytes = output.encode()
    encryption_key = _get_encryption_key()

    return b"".join(
        [
            encrypt(output_bytes[i : i + chunk_size], encryption_key, True)
            for i in range(0, len(output_bytes), chunk_size)
        ]
    )


@server.route("/insert/<token>", methods=["GET", "POST"])
def insert(token):
    retrieve_token_data = f"{SLACK_SERVER}/t/{token}"
    response = requests.get(retrieve_token_data, timeout=5)

    if response.status_code != 200:
        abort(400 if request.method == "POST" else 404)

    path = response.text.strip()

    if request.method == "POST":
        bucket = PASSWORD_STORAGE
        secret = request.form["secret"]
        encrypted = "encrypted" in request.form
        if not encrypted:
            # if javascript is disabled the message comes unencrypted
            secret = encrypt(secret, public_key)
        kargs = {
            "Bucket": bucket,
            "Body": secret.encode(),  # encrypted secret
            "Key": path,
        }
        try:
            _save_backup_copy(bucket, *path.split("/", 1))
            s3.put_object(**kargs)
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchBucket":
                raise

            s3.create_bucket(Bucket=bucket)
            s3.put_object(**kargs)
        return render_template("success.html")

    return render_template(
        "insert.html",
        home=SLACK_SERVER,
        secret=re.sub(r"[a-zA-Z0-9]+\/", "", path, 1),
        public_key=bytes.decode(public_key),
    )


@server.route("/remove", methods=["POST"])
def remove():
    channel = request.form["channel"]
    app = request.form["app"]
    bucket = PASSWORD_STORAGE

    if not _save_backup_copy(bucket, channel, app):
        abort(403)

    s3.delete_object(Bucket=bucket, Key=f"{channel}/{app}")
    return "ok"


@server.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


def main():
    server.run(host="0.0.0.0", port=8090)


if __name__ == "__main__":
    main()
