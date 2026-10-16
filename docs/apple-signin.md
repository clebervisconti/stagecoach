# Sign in with Apple (D9)

Apple stays **disabled** until all four secrets exist. Never commit the private key.

## Secrets (env / host secret store only)

| Variable | What it is |
|---|---|
| `APPLE_CLIENT_ID` | Services ID (e.g. `com.example.stagecoach.web`) |
| `APPLE_TEAM_ID` | 10-character Apple Team ID |
| `APPLE_KEY_ID` | Key ID of the Sign in with Apple private key |
| `APPLE_PRIVATE_KEY` | PKCS#8 PEM. In env files you may use `\n` for newlines. |
| `APPLE_JWKS_JSON` | **Tests only.** Injected JWKS so CI never calls Apple. |

Optional: `EMAIL_PROVIDER=console` (default) for verification and reset mail.

## Apple Developer setup

1. Identifiers → **Services ID** with Sign in with Apple enabled.
2. Return URLs: `https://<host>/auth/apple/callback` and the local equivalent.
3. Keys → create a Sign in with Apple key. Download the `.p8` once. Set `APPLE_KEY_ID` and paste the PEM into `APPLE_PRIVATE_KEY`.
4. Domains and email sources: verify the app domain if you want non-relay emails. Private Relay (`*@privaterelay.appleid.com`) is a first-class account email; `apple_sub` is the stable subject.

## Protocol

The API builds the authorize URL with `response_type=code`, `code_challenge_method=S256`, and a `nonce`. The callback posts `code` + PKCE verifier + nonce (or a stand-in `id_token`) to `POST /api/v1/auth/apple/finish`. The ID token is checked against Apple's JWKS (`iss=https://appleid.apple.com`, `aud=APPLE_CLIENT_ID`, nonce match).

`GET /api/v1/auth/apple/config` returns `{ "enabled": false }` until the four secrets are set.

## Local / CI

Leave the Apple variables unset. The sign-in page shows that Apple is disabled. Unit tests mint an RSA key, build a JWKS, and sign a fake ID token — no egress to `appleid.apple.com`.
