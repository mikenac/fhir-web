"""Backend Services (JWT-based) authentication for SMART on FHIR

This module implements the SMART Backend Services specification for
server-to-server authentication using signed JWT assertions.

References:
- http://hl7.org/fhir/smart-app-launch/backend-services.html
- https://datatracker.ietf.org/doc/html/rfc7523
"""

import time
import uuid
from typing import Optional
import httpx
import jwt


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
        self.private_key = private_key
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

        # Sign JWT with private key
        token = jwt.encode(
            claims,
            self.private_key,
            algorithm=self.algorithm,
            headers=headers,
        )

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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": assertion,
                    "scope": " ".join(self.scopes),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

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
