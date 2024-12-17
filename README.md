# slashpass [Private Server]

[![Build Status](https://travis-ci.org/talpor/password-scale.svg?branch=master)](https://travis-ci.org/talpor/password-scale)

Slashpass is a Slack command designed to facilitate secure password sharing among members of a Slack channel.

This project focuses on enabling communication in environments where mutual trust between parties is not required. Slashpass uses RSA, an asymmetric encryption algorithm, to securely share encrypted information point-to-point. Only the dedicated and independent Password Server for each client has the ability to decrypt and read the stored passwords, ensuring that only authorized participants can access sensitive information.

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

- poetry

### Step-by-step guide

Follow these steps to set up and deploy the Slashpass Private Server.

#### 1. Clone the Repository

Clone the slashpass-private-server project and navigate to the project directory:

```
git clone git@github.com:slashpass/slashpass-private-server.git
cd slashpass-private-server
```

#### 2. Install Dependencies

Install the required dependencies using Poetry:

```
poetry install
```

#### 3. Create the zappa_settings.json File

Copy the example configuration file to create your own zappa_settings.json:

```
cp zappa_settings.example.json zappa_settings.json
```

#### 4. Update the Configuration

Edit the zappa_settings.json file and update the following fields:

s3_bucket: Replace with your own S3 bucket name.
environment_variables: Replace values as needed. See the table below for the required environment variables.

#### 5. Configure AWS CLI Credentials

Ensure your AWS CLI credentials are configured. If needed, refer to the official AWS documentation:

[Configure AWS CLI Credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)

#### 6. Deploy the Server

Deploy the **_server stage_** using Zappa:

```
poetry run zappa deploy server
```

Done! now you will need to configure your server in Slack, using the command `/pass configure <new_server_url>` to retrieve your server URL use the command `poetry run zappa status server` and check the _API Gateway URL_. If you have any error using the command after configuration use `poetry run zappa tail` command to check the server logs.

### Local development environment

To set up your local development environment, follow these steps:

1. Install Dependencies
   To install all necessary dependencies, including development-specific ones, use the following command:

`poetry install --with dev`

2. Start the Server
   When running the server locally, it will load environment variables from the zappa_settings.json file, specifically from the settings section labeled "dev". Modify these variables as needed for local development purposes.

To start the server, use:

`poetry run start-server`

3. Run Tests
   To execute the test suite, run:

`poetry run pytest tests`

### Environment variables table

| Key                             | Description                                                                                                    |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| AWS_ACCESS_KEY_ID               | Your AWS public key with permissions to access S3.                                                             |
| AWS_SECRET_ACCESS_KEY           | Your AWS private key.                                                                                          |
| AWS_S3_REGION (optional)        | The AWS region where the password storage bucket will be created. Defaults to us-east-1.                       |
| ENCRYPTION_KEY_URL (optional)   | URL to retrieve the Slack Server public key. Defaults to https://slack.slashpass.co/public_key.                |
| ONETIMESECRET_KEY (optional)    | API key for your One-Time Secret account.                                                                      |
| ONETIMESECRET_USER (optional)   | Username for your One-Time Secret account.                                                                     |
| ONETIMESECRET_REGION (optional) | Region for your One-Time Secret account, could be `us` or `eu`. Defaults to us.                                |
| PASSWORD_STORAGE                | Unique name for the S3 bucket where passwords will be stored.                                                  |
| BIP39                           | Mnemonic phrase used for generating deterministic keys. You can generate one using: poetry run generate-bip39. |
