"""Generate RS384 keypair for Epic Backend Services authentication"""

import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import base64


def generate_keypair():
    """Generate RSA keypair and output in required formats"""

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )

    # Get private key in PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Get public key in PEM format
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Get public key numbers for JWK
    public_numbers = public_key.public_numbers()

    # Convert to JWK format (for Epic app registration)
    n = base64.urlsafe_b64encode(
        public_numbers.n.to_bytes(
            (public_numbers.n.bit_length() + 7) // 8, byteorder="big"
        )
    ).decode("utf-8").rstrip("=")

    e = base64.urlsafe_b64encode(
        public_numbers.e.to_bytes(
            (public_numbers.e.bit_length() + 7) // 8, byteorder="big"
        )
    ).decode("utf-8").rstrip("=")

    jwk = {
        "kty": "RSA",
        "alg": "RS384",
        "use": "sig",
        "kid": "epic-backend-services-key",
        "n": n,
        "e": e,
    }

    # Save files
    with open("keys/private_key.pem", "wb") as f:
        f.write(private_pem)

    with open("keys/public_key.pem", "wb") as f:
        f.write(public_pem)

    with open("keys/public_key.jwk", "w") as f:
        json.dump(jwk, f, indent=2)

    print("✓ Generated keypair successfully!")
    print("\nFiles created:")
    print("  - keys/private_key.pem (keep this secret!)")
    print("  - keys/public_key.pem")
    print("  - keys/public_key.jwk (upload this to Epic)")
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("\n1. Upload the public key JWK to Epic:")
    print("   - Go to your Epic app configuration")
    print("   - Add the JWK from keys/public_key.jwk")
    print("\n2. The JWK to upload:")
    print(json.dumps(jwk, indent=2))
    print("\n3. Add keys/ to .gitignore to avoid committing secrets")


if __name__ == "__main__":
    generate_keypair()
