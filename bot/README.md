# bot

> A GitHub App built with [Probot](https://github.com/probot/probot) that This is a github code reviewer bot that suggest the improment ment in the PR and \t  other     sequrity suggestions

## Setup

```sh
# Install dependencies
npm install

# Run the bot
npm start
```

## Docker

```sh
# 1. Build container
docker build -t bot .

# 2. Start container
docker run -e APP_ID=<app-id> -e PRIVATE_KEY=<pem-value> bot
```

## Contributing

If you have suggestions for how bot could be improved, or want to report a bug, open an issue! We'd love all and any contributions.

For more, check out the [Contributing Guide](CONTRIBUTING.md).

## License

[ISC](LICENSE) © 2025 Jagjeevan Kashid
