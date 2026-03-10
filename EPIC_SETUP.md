# Epic FHIR Integration Setup

This guide explains how to connect your FHIR Web Service to Epic's FHIR server using Backend Services authentication.

## Overview

Epic Backend Services uses JWT-based authentication (SMART Backend Services) for server-to-server communication. This is ideal for applications that don't require user login.

## Prerequisites

- Epic app registration with client ID: `f42e0c16-8c32-4e38-850b-a2bfd4172c62`
- Access to Epic's app configuration portal
- Generated RSA keypair (done automatically below)

## Setup Steps

### 1. Generate Keypair (Already Done!)

The keypair has been generated in the `keys/` directory:
- `keys/private_key.pem` - Keep this secret! Used to sign JWTs
- `keys/public_key.pem` - Public key (PEM format)
- `keys/public_key.jwk` - Public key (JWK format) - **Upload this to Epic**

### 2. Upload Public Key to Epic

You need to upload the public key JWK to your Epic app configuration:

1. Log in to Epic's app management portal
2. Find your app (Client ID: `f42e0c16-8c32-4e38-850b-a2bfd4172c62`)
3. Navigate to the "Public Keys" or "JWKS" section
4. Upload the JWK from `keys/public_key.jwk`

The JWK looks like this:
```json
{
  "kty": "RSA",
  "alg": "RS384",
  "use": "sig",
  "kid": "epic-backend-services-key",
  "n": "...",
  "e": "AQAB"
}
```

### 3. Configure Environment Variables

Create a `.env` file in the project root with Epic configuration:

```bash
# Copy the example file
cp .env.epic.example .env
```

Then edit `.env` with your settings:

```env
# Enable Epic Backend Services
EPIC_BACKEND_SERVICES_ENABLED=true

# Epic FHIR Server
FHIR_BASE_URL=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/

# Epic OAuth2 Configuration
EPIC_CLIENT_ID=f42e0c16-8c32-4e38-850b-a2bfd4172c62
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
EPIC_PRIVATE_KEY_PATH=./keys/private_key.pem
EPIC_KEY_ID=epic-backend-services-key

# Scopes (adjust based on your app's permissions)
EPIC_SCOPES=system/Patient.read system/Encounter.read system/ServiceRequest.read system/MedicationRequest.read

# JWT Algorithm (Epic supports RS384)
EPIC_JWT_ALGORITHM=RS384
```

### 4. Restart the Backend

Kill the existing backend process and restart it:

```bash
# Kill old processes
pkill -f uvicorn

# Start the backend with new configuration
source .venv/bin/activate
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. Test the Connection

Try searching for patients to verify the connection works:

```bash
curl http://localhost:8000/api/patients/?family_name=Smith&given_name=
```

## How It Works

1. **JWT Creation**: When a request comes in, the backend creates a signed JWT using your private key
2. **Token Exchange**: The JWT is sent to Epic's token endpoint to get an access token
3. **FHIR Requests**: The access token is used to authenticate requests to Epic's FHIR server
4. **Token Caching**: Access tokens are cached and automatically refreshed when needed

## Authentication Flow

```
┌─────────────┐                                    ┌──────────────┐
│             │  1. Create & sign JWT assertion    │              │
│  Your App   │──────────────────────────────────> │  Epic OAuth  │
│             │                                    │   Server     │
│             │  2. Return access token            │              │
│             │ <──────────────────────────────────│              │
└─────────────┘                                    └──────────────┘
       │
       │ 3. Use access token for FHIR requests
       ▼
┌─────────────┐
│             │
│ Epic FHIR   │
│  Server     │
│             │
└─────────────┘
```

## Scopes

Common scopes for backend services:

- `system/Patient.read` - Read all patients
- `system/Encounter.read` - Read all encounters
- `system/ServiceRequest.read` - Read all service requests (orders)
- `system/MedicationRequest.read` - Read all medication requests
- `system/*.read` - Read all resources (use cautiously)

## Troubleshooting

### "Invalid client assertion" error
- Verify the public key was uploaded correctly to Epic
- Check that the `kid` in your JWK matches `EPIC_KEY_ID` in `.env`
- Ensure the JWT algorithm (`RS384`) matches what Epic expects

### "Unauthorized" or "403" errors
- Check that your app has the requested scopes enabled in Epic
- Verify the client ID is correct
- Ensure the token URL is correct

### "Token expired" errors
- Access tokens are automatically refreshed, but check system clock sync
- Verify the private key file path is correct

## Security Notes

- **Never commit** `keys/private_key.pem` to version control
- The `keys/` directory is already in `.gitignore`
- Store private keys securely in production (use secrets management)
- Rotate keys periodically and update Epic configuration

## References

- [SMART Backend Services Specification](http://hl7.org/fhir/smart-app-launch/backend-services.html)
- [Epic FHIR Documentation](https://fhir.epic.com/Documentation)
- [JWT Bearer Token Profile (RFC 7523)](https://datatracker.ietf.org/doc/html/rfc7523)
