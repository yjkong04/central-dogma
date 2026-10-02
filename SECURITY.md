# Security Policy

## Reporting a Vulnerability

This is a personal portfolio/research project. If you find a security issue, please report it privately via GitHub's "Report a vulnerability" flow (repo Security tab) rather than opening a public issue.

## Scope

- No production user data is handled. The AWS demo path runs against a small set of curated, publicly available PMC papers.
- Secrets (AWS credentials, API keys, etc.) must never be committed. `.env`-style files are gitignored; use `.env.example` as the template for required variables.

## Supported Versions

This project does not maintain release branches. Security fixes land on `main`.
