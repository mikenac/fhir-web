"""OAuth2 authentication helpers for FHIR servers"""

import base64
import json
from typing import Any, Optional
from urllib.parse import urlencode, parse_qs, urlparse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

import httpx


class OAuth2TokenManager:
    """Manages OAuth2 tokens for FHIR authentication"""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        """
        Initialize OAuth2 token manager

        Args:
            token_url: OAuth2 token endpoint
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret (for confidential clients)
            redirect_uri: Redirect URI for authorization code flow
        """
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None

    async def get_client_credentials_token(self) -> str:
        """
        Get access token using client credentials flow

        Returns:
            Access token
        """
        if not self.client_secret:
            raise ValueError("Client secret required for client credentials flow")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
            token: str = token_data["access_token"]
            self.access_token = token
            return token

    async def exchange_authorization_code(self, code: str) -> str:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from OAuth2 flow

        Returns:
            Access token
        """
        if not self.redirect_uri:
            raise ValueError("Redirect URI required for authorization code flow")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
        }

        if self.client_secret:
            data["client_secret"] = self.client_secret

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
            token: str = token_data["access_token"]
            self.access_token = token
            self.refresh_token = token_data.get("refresh_token")
            return token

    async def refresh_access_token(self) -> str:
        """
        Refresh access token using refresh token

        Returns:
            New access token
        """
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
        }

        if self.client_secret:
            data["client_secret"] = self.client_secret

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
            token: str = token_data["access_token"]
            self.access_token = token
            if "refresh_token" in token_data:
                self.refresh_token = token_data["refresh_token"]
            return token

    def get_token(self) -> Optional[str]:
        """Get current access token"""
        return self.access_token


class SMARTAuthHelper:
    """Helper for SMART on FHIR authentication flows"""

    def __init__(
        self,
        fhir_base_url: str,
        client_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: str = "http://localhost:8000/callback",
        scope: str = "launch patient/*.read",
    ):
        """
        Initialize SMART auth helper

        Args:
            fhir_base_url: FHIR server base URL
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret (optional for public clients)
            redirect_uri: OAuth2 redirect URI
            scope: SMART scopes (space-separated)
        """
        self.fhir_base_url = fhir_base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.authorization_url: Optional[str] = None
        self.token_url: Optional[str] = None
        self.authorization_code: Optional[str] = None

    async def discover_smart_configuration(self) -> dict[str, Any]:
        """
        Discover SMART configuration from FHIR server

        Returns:
            SMART configuration
        """
        # Try .well-known endpoint
        well_known_url = f"{self.fhir_base_url}/.well-known/smart-configuration"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(well_known_url)
                response.raise_for_status()
                config = response.json()
            except Exception:
                # Fallback to metadata endpoint
                metadata_url = f"{self.fhir_base_url}/metadata"
                response = await client.get(metadata_url)
                response.raise_for_status()
                metadata = response.json()

                # Extract OAuth2 endpoints from CapabilityStatement
                security = None
                for rest in metadata.get("rest", []):
                    if rest.get("mode") == "server":
                        security = rest.get("security")
                        break

                if not security:
                    raise ValueError("No security configuration found in metadata")

                config = {}
                for extension in security.get("extension", []):
                    if "oauth-uris" in extension.get("url", ""):
                        for ext in extension.get("extension", []):
                            url_type = ext.get("url")
                            value = ext.get("valueUri")
                            if url_type == "authorize":
                                config["authorization_endpoint"] = value
                            elif url_type == "token":
                                config["token_endpoint"] = value

        self.authorization_url = config.get("authorization_endpoint")
        self.token_url = config.get("token_endpoint")

        return config

    def get_authorization_url(
        self,
        state: Optional[str] = None,
        launch: Optional[str] = None,
    ) -> str:
        """
        Generate authorization URL for user redirect

        Args:
            state: OAuth2 state parameter
            launch: SMART launch context token

        Returns:
            Authorization URL
        """
        if not self.authorization_url:
            raise ValueError("Must call discover_smart_configuration() first")

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "state": state or "random-state",
            "aud": self.fhir_base_url,
        }

        if launch:
            params["launch"] = launch

        return f"{self.authorization_url}?{urlencode(params)}"

    async def non_interactive_launch(
        self,
        patient_id: Optional[str] = None,
    ) -> str:
        """
        Perform a non-interactive SMART standalone launch for testing.

        Works with SMART Health IT sandbox by encoding skip_login and skip_auth
        flags into the launch parameter, bypassing all browser-based UI steps.
        Requires a specific patient_id to satisfy the patient-standalone login check.

        Args:
            patient_id: FHIR Patient resource ID to launch in context.
                        If None, fetches the first available patient.

        Returns:
            Access token

        Note:
            This flow only works with SMART sandboxes that support skip_login/skip_auth
            simulation flags (e.g., launch.smarthealthit.org).
        """
        # Discover endpoints
        await self.discover_smart_configuration()

        if not self.authorization_url or not self.token_url:
            raise ValueError(
                "token_url/authorization_url not discovered; "
                "call discover_smart_configuration() first"
            )

        # Auto-fetch a patient if none provided
        if not patient_id:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self.fhir_base_url}/Patient",
                    params={"_count": 1},
                    headers={"Accept": "application/fhir+json"},
                )
                r.raise_for_status()
                bundle = r.json()
                entries = bundle.get("entry", [])
                if not entries:
                    raise ValueError("No patients found on FHIR server")
                patient_id = entries[0]["resource"]["id"]

        # Build launch params:
        # [launchTypeIndex, patient, provider, encounter,
        #  skip_login, skip_auth, sim_ehr, scope, redirect_uris,
        #  client_id, client_secret, auth_error, jwks_url, jwks,
        #  clientTypeIndex, pkceIndex, fhir_server]
        #
        # patient-standalone = 3, skip_login = 1 (idx 4), skip_auth = 1 (idx 5)
        launch_params: list[Any] = [
            3,
            patient_id,
            "",
            "",
            1,
            1,
            0,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            0,
            0,
            "",
        ]
        launch = base64.b64encode(
            json.dumps(launch_params, separators=(",", ":")).encode()
        ).decode()

        # Build authorize URL and request the code directly (no browser)
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "state": "non-interactive-test",
            "aud": self.fhir_base_url,
            "launch": launch,
        }

        async with httpx.AsyncClient() as client:
            r = await client.get(
                self.authorization_url,
                params=params,
                follow_redirects=False,
            )

            if r.status_code not in (301, 302, 303, 307, 308):
                raise ValueError(
                    f"Expected redirect from authorize endpoint, got {r.status_code}. "
                    "This server may not support non-interactive skip_login/skip_auth flags."
                )

            location = r.headers.get("location", "")
            parsed = urlparse(location)
            qs = parse_qs(parsed.query)

            if "error" in qs:
                raise ValueError(
                    f"Authorization error: {qs['error'][0]} - "
                    f"{qs.get('error_description', [''])[0]}"
                )

            if "code" not in qs:
                raise ValueError(
                    f"No authorization code in redirect. "
                    f"Final URL path: {parsed.path}. "
                    "The server did not skip login/auth screens as expected."
                )

            code = qs["code"][0]
            self.authorization_code = code

        # Exchange code for token
        token_manager = OAuth2TokenManager(
            token_url=self.token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
        )
        return await token_manager.exchange_authorization_code(code)

    async def standalone_launch(self) -> str:
        """
        Perform standalone launch flow (opens browser for user login)

        Returns:
            Access token
        """
        # Discover endpoints
        await self.discover_smart_configuration()

        # Start local server to receive callback
        server = LocalCallbackServer(port=8000)
        server_thread = threading.Thread(target=server.run)
        server_thread.daemon = True
        server_thread.start()

        # Open browser for authorization
        auth_url = self.get_authorization_url()
        print("Opening browser for authorization...")
        print(f"If browser doesn't open, visit: {auth_url}")
        webbrowser.open(auth_url)

        # Wait for callback
        print("Waiting for authorization callback...")
        server.wait_for_code(timeout=120)

        if server.error:
            raise ValueError(f"Authorization failed: {server.error}")

        if not server.code:
            raise ValueError("No authorization code received")

        self.authorization_code = server.code

        if not self.token_url:
            raise ValueError("token_url not discovered; call discover_smart_configuration() first")

        # Exchange code for token
        token_manager = OAuth2TokenManager(
            token_url=self.token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
        )

        access_token = await token_manager.exchange_authorization_code(server.code)
        return access_token


class LocalCallbackServer:
    """Simple HTTP server to receive OAuth2 callback"""

    def __init__(self, port: int = 8000):
        self.port = port
        self.code: Optional[str] = None
        self.error: Optional[str] = None
        self.server: Optional[HTTPServer] = None
        self._code_received = threading.Event()

    def run(self):
        """Run the callback server"""
        handler = self._make_handler()
        self.server = HTTPServer(("localhost", self.port), handler)
        self.server.timeout = 1
        while not self._code_received.is_set():
            self.server.handle_request()

    def _make_handler(self):
        """Create request handler"""
        callback_server = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                """Suppress logging"""
                pass

            def do_GET(self):
                """Handle GET request"""
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                if "code" in params:
                    callback_server.code = params["code"][0]
                    message = "Authorization successful! You can close this window."
                elif "error" in params:
                    callback_server.error = params["error"][0]
                    message = f"Authorization failed: {callback_server.error}"
                else:
                    message = "Invalid callback"

                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"<html><body><h1>{message}</h1></body></html>".encode())

                callback_server._code_received.set()

        return CallbackHandler

    def wait_for_code(self, timeout: int = 120):
        """Wait for authorization code"""
        self._code_received.wait(timeout=timeout)
