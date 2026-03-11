"""Backend Services (JWT-based) authentication for SMART on FHIR

This module implements the SMART Backend Services specification for
server-to-server authentication using signed JWT assertions.

References:
- http://hl7.org/fhir/smart-app-launch/backend-services.html
- https://datatracker.ietf.org/doc/html/rfc7523
"""

import logging
import time
import uuid
from typing import Optional
import httpx
import jwt

logger = logging.getLogger(__name__)


def normalize_private_key(private_key: str) -> str:
    """
    Normalize a PEM private key by ensuring proper line breaks.

    This fixes keys that have been copy/pasted into environment variables
    where newlines may have been lost.

    Args:
        private_key: PEM-formatted private key (possibly without proper newlines)

    Returns:
        Properly formatted PEM key with correct line breaks
    """
    # Remove any existing whitespace/newlines
    key = private_key.strip().replace('\n', '').replace('\r', '')

    # If key doesn't have the header, it's invalid
    if '-----BEGIN PRIVATE KEY-----' not in key and '-----BEGIN RSA PRIVATE KEY-----' not in key:
        raise ValueError("Invalid private key format: missing BEGIN header")

    # Extract the header, body, and footer
    if '-----BEGIN PRIVATE KEY-----' in key:
        header = '-----BEGIN PRIVATE KEY-----'
        footer = '-----END PRIVATE KEY-----'
    else:
        header = '-----BEGIN RSA PRIVATE KEY-----'
        footer = '-----END RSA PRIVATE KEY-----'

    # Extract the key content between header and footer
    start = key.find(header) + len(header)
    end = key.find(footer)

    if end == -1:
        raise ValueError("Invalid private key format: missing END footer")

    key_content = key[start:end]

    # Rebuild the key with proper line breaks (64 chars per line is PEM standard)
    lines = [header]
    for i in range(0, len(key_content), 64):
        lines.append(key_content[i:i+64])
    lines.append(footer)

    return '\n'.join(lines)


class BackendServicesAuth:
    """SMART Backend Services authentication using JWT"""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        private_key: str,
        key_id: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        algorithm: str = "RS384",
    ):
        """
        Initialize backend services authentication

        Args:
            token_url: OAuth2 token endpoint
            client_id: OAuth2 client ID
            private_key: Private key (PEM format) for signing JWTs
            key_id: Key ID (kid) for JWT header (optional)
            scopes: List of scopes to request (e.g., ["system/*.read"])
            algorithm: JWT signing algorithm (RS256, RS384, or RS512)
        """
        self.token_url = token_url
        self.client_id = client_id
        # Normalize the private key to handle environment variable formatting issues
        self.private_key = normalize_private_key(private_key)
        self.key_id = key_id
        self.scopes = scopes or ["system/*.read"]
        self.algorithm = algorithm
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[float] = None

    def create_jwt_assertion(self) -> str:
        """
        Create a signed JWT assertion for authentication

        Returns:
            Signed JWT string
        """
        now = int(time.time())

        # JWT header
        headers = {"alg": self.algorithm, "typ": "JWT"}
        if self.key_id:
            headers["kid"] = self.key_id

        # JWT claims
        claims = {
            "iss": self.client_id,  # Issuer (client_id)
            "sub": self.client_id,  # Subject (client_id)
            "aud": self.token_url,  # Audience (token endpoint)
            "jti": str(uuid.uuid4()),  # Unique identifier
            "exp": now + 300,  # Expiration (5 minutes)
            "iat": now,  # Issued at
        }

        logger.info(f"Creating JWT assertion with headers: {headers}")
        logger.info(f"JWT claims: iss={claims['iss']}, sub={claims['sub']}, aud={claims['aud']}")
        logger.info(f"JWT timing: iat={claims['iat']}, exp={claims['exp']}")

        # Sign JWT with private key
        token = jwt.encode(
            claims,
            self.private_key,
            algorithm=self.algorithm,
            headers=headers,
        )

        logger.info(f"JWT token created (first 50 chars): {token[:50]}...")
        return token

    async def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Get access token using JWT assertion

        Args:
            force_refresh: Force token refresh even if cached token is valid

        Returns:
            Access token
        """
        # Return cached token if still valid
        if not force_refresh and self.access_token and self.token_expiry:
            if time.time() < self.token_expiry - 60:  # 60 second buffer
                return self.access_token

        # Create JWT assertion
        assertion = self.create_jwt_assertion()

        # Request access token
        request_data = {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
            "scope": " ".join(self.scopes),
        }

        logger.info(f"Requesting access token from: {self.token_url}")
        logger.info(f"Token request scopes: {' '.join(self.scopes)}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.token_url,
                    data=request_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                logger.info(f"Token endpoint response status: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"Token endpoint error response: {response.text}")

                response.raise_for_status()
                token_data = response.json()
                logger.info("Successfully obtained access token")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error during token request: {e}")
                logger.error(f"Response body: {e.response.text}")
                raise

        self.access_token = token_data["access_token"]

        # Calculate token expiry
        expires_in = token_data.get("expires_in", 3600)
        self.token_expiry = time.time() + expires_in

        return self.access_token

    def get_token(self) -> Optional[str]:
        """
        Get current access token (synchronous, returns cached token only)

        Returns:
            Cached access token or None
        """
        return self.access_token


class BackendServicesTokenManager:
    """Token manager that wraps BackendServicesAuth for use with FHIRClient"""

    def __init__(self, backend_auth: BackendServicesAuth):
        """
        Initialize token manager

        Args:
            backend_auth: BackendServicesAuth instance
        """
        self.backend_auth = backend_auth

    def get_token(self) -> Optional[str]:
        """
        Get current access token

        Returns:
            Access token or None
        """
        return self.backend_auth.get_token()

    async def ensure_valid_token(self) -> str:
        """
        Ensure we have a valid access token

        Returns:
            Valid access token
        """
        return await self.backend_auth.get_access_token()
