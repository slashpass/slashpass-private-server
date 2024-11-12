# slashpass [Private Server]

[![Build Status](https://travis-ci.org/talpor/password-scale.svg?branch=master)](https://travis-ci.org/talpor/password-scale)

slashpass is a Slack command to manage shared passwords between the members of a channel in Slack.

This project was build focused in establishing a communication where the trustness between parties is not required, using the asymmetric algorithm RSA to share encrypted information point to point and where the only participant allowed to read the stored passwords is the _Password Server_, who is different and independent for each client.

## Commands

- `/pass` or `/pass list` list the available passwords in the channel.
- `/pass <secret>` or `/pass show <secret>` retrieve a one time use link with the secret content, this link expires in 15 minutes.
- `/pass insert <secret>` retrieve a link with an editor to create a secret, this link expires in 15 minutes.
- `/pass remove <secret>` make unreachable the secret, to complete deletion in necessary doing it manually from the s3 password storage.
- `/pass configure <password_server_url>` this is the command used for the initial setup, it is only necessary to execute it once.

[![button](https://platform.slack-edge.com/img/add_to_slack.png)](https://slack.com/oauth/v2/authorize?client_id=2554558892.385841792964&scope=commands)

## How to deploy

In order to be efficient with the resource management and facilitate the deploy process this guide shows the process to put in producction a serverless infracstructure using AWS Lambda plus API Gateway using [Zappa](https://github.com/zappa/Zappa)

### Requirements

#### Required accounts

- AWS account (https://aws.amazon.com/)
- One-Time Secret account (https://onetimesecret.com/)

#### Installed software

- pipenv

### Step-by-step guide

- Clone _slashpass-private-server_ project `git clone git@github.com:slashpass/slashpass-private-server.git` and do `cd slashpass-private-server`
- Install requirements `poetry install`
- Create _zappa_settings.json_ file based on _zappa_settings.example.json_ `cp zappa_settings.example.json zappa_settings.json`
- Modify _"s3_bucket"_ and _"environment_variables"_ variables in the new _zappa_settings.json_ file, replacing each value for your owns (for the _"environment_variables"_ see the table below)
- Configure the awscli credential if necessary (https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- Deploy the server `poetry run zappa deploy`

Done! now you will need to configure your server in Slack, using the command `/pass configure <new_server_url>` to retrieve your server URL use the command `zappa status` and check the _API Gateway URL_. If you have any error using the command after configuration use `zappa tail` command to check the server logs.

### Local run

poetry run start-server

### Environment variables table

| Key                           | Description                                                                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| AWS_ACCESS_KEY_ID             | Your AWS public key, this key only needs permission to use S3                                                                  |
| AWS_SECRET_ACCESS_KEY         | Your AWS private key                                                                                                           |
| AWS_S3_REGION (optional)      | The AWS region where the password storage bucket will be created, the default value is `us-east-1`                             |
| ENCRYPTION_KEY_URL (optional) | This is the url to retrieve the _Slack Server_ public key, the default value is `https://slack.slashpass.co/public_key`        |
| ONETIMESECRET_KEY             | Your One-Time Secret API key                                                                                                   |
| ONETIMESECRET_USER            | Your One-Time Secret user name                                                                                                 |
| PASSWORD_STORAGE              | Unique name for your password storage bucket                                                                                   |
| BIP39                         | Mnemonic code for generating deterministic keys, specification: https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki |
