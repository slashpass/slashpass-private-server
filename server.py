import os
import re
import time

import boto3
import requests
from botocore.exceptions import ClientError
from flask import Flask, abort, render_template, request
from onetimesecret import OneTimeSecretCli
from rsa import decrypt, encrypt, generate_key

server = Flask(__name__)

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_S3_REGION = os.environ.get("AWS_S3_REGION", "us-east-1")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
ONETIMESECRET_KEY = os.environ.get("ONETIMESECRET_KEY")
ONETIMESECRET_USER = os.environ.get("ONETIMESECRET_USER")
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


def _get_encryption_key():
    bucket = PASSWORD_STORAGE
    key = "slack.slashpass.id_rsa.pub"
    encryption_key_url = "{}/public_key".format(SLACK_SERVER)
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            r = requests.get(encryption_key_url)
            if r.status_code != requests.codes.ok:
                raise Exception(
                    "Unable to retrieve {} from {}".format(key, encryption_key_url)
                )
            s3.put_object(Bucket=bucket, Body=str.encode(r.text), Key=key)
            return r.text
        else:
            raise e
    return response["Body"].read()


def _save_backup_copy(bucket, channel, key):
    path = key.split("/")
    file = path.pop()
    route = "/".join(path) + "/" if path else ""
    new_key = "{}/{}.{}.{}".format(channel, route, file, int(time.time()))
    try:
        s3.copy_object(
            Bucket=bucket,
            CopySource="{}/{}/{}".format(bucket, channel, key),
            Key=new_key,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] in ["NoSuchKey", "NoSuchBucket"]:
            return False
        else:
            raise e
    return True


@server.route("/public_key", methods=["GET"])
def get_public_key():
    return public_key


@server.route("/onetime_link", methods=["POST"])
def get_onetime_link():
    cli = OneTimeSecretCli(ONETIMESECRET_USER, ONETIMESECRET_KEY)
    try:
        response = s3.get_object(Bucket=PASSWORD_STORAGE, Key=request.form["secret"])
    except ClientError as e:
        if e.response["Error"]["Code"] in ["NoSuchKey", "NoSuchBucket"]:
            abort(404)
        else:
            raise e

    secret = decrypt(response["Body"].read(), private_key)
    encryption_key = _get_encryption_key()
    # the link is encrypted to be decrypted by the slack server
    return encrypt(cli.create_link(secret), encryption_key)


@server.route("/list/<prefix>", methods=["POST"])
def list(prefix):
    output = ""
    chunk_size = 214  # assuming 2048 bits key
    try:
        bucket = s3.list_objects(Bucket=PASSWORD_STORAGE, Prefix=prefix)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchBucket":
            s3.create_bucket(Bucket=PASSWORD_STORAGE)
        else:
            raise e
    else:
        if "Contents" in bucket:
            output = "\n".join(
                [
                    x["Key"]
                    for x in bucket["Contents"]
                    if not re.match(".+\/\.\w+", x["Key"])
                ]
            )

    output = str.encode(output)
    encryption_key = _get_encryption_key()

    return b"".join(
        [
            encrypt(output[i : i + chunk_size], encryption_key, True)
            for i in range(0, len(output), chunk_size)
        ]
    )


@server.route("/insert/<token>", methods=["GET", "POST"])
def insert(token):
    retrieve_token_data = "{}/t/{}".format(SLACK_SERVER, token)
    response = requests.get(retrieve_token_data)

    if response.status_code != 200:
        abort(400 if request.method == "POST" else 404)

    path = bytes.decode(response.content)

    if request.method == "POST":
        bucket = PASSWORD_STORAGE
        secret = request.form["secret"]
        encrypted = "encrypted" in request.form
        if not encrypted:
            # if javascript is disabled the message comes unencrypted
            secret = encrypt(secret, public_key)
        kargs = {
            "Bucket": bucket,
            "Body": str.encode(secret),  # encrypted secret
            "Key": path,
        }
        try:
            _save_backup_copy(bucket, *path.split("/", 1))
            s3.put_object(**kargs)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchBucket":
                s3.create_bucket(Bucket=bucket)
                s3.put_object(**kargs)
            else:
                raise e

        return render_template("success.html")

    return render_template(
        "insert.html",
        home=SLACK_SERVER,
        secret=re.sub("[a-zA-Z0-9]+\/", "", path, 1),
        public_key=bytes.decode(public_key),
    )


@server.route("/remove", methods=["POST"])
def remove():
    channel = request.form["channel"]
    app = request.form["app"]
    bucket = PASSWORD_STORAGE

    if not _save_backup_copy(bucket, channel, app):
        abort(403)

    s3.delete_object(Bucket=bucket, Key="{}/{}".format(channel, app))
    return "ok"


@server.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8090)
