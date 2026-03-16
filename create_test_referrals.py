"""Create test referrals in SMART Health IT"""
import requests
import json

SMART_BASE = "https://launch.smarthealthit.org/v/r4/fhir"
PATIENT_ID = "618b2992-eec7-45c9-8544-12c9f586b78c"

referrals = [
    {
        "resourceType": "ServiceRequest",
        "status": "active",
        "intent": "order",
        "code": {
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": "3457005",
                "display": "Referral to cardiologist"
            }],
            "text": "Cardiology Consultation"
        },
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "authoredOn": "2024-01-15T10:00:00Z",
        "requester": {"display": "Dr. Sarah Johnson"},
        "reasonCode": [{
            "text": "Chest pain and abnormal EKG"
        }]
    },
    {
        "resourceType": "ServiceRequest",
        "status": "active",
        "intent": "order",
        "code": {
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": "306206005",
                "display": "Referral to orthopedic surgeon"
            }],
            "text": "Orthopedic Surgery Consultation"
        },
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "authoredOn": "2024-02-01T14:30:00Z",
        "requester": {"display": "Dr. Michael Chen"},
        "reasonCode": [{
            "text": "Chronic knee pain, possible meniscus tear"
        }]
    },
    {
        "resourceType": "ServiceRequest",
        "status": "completed",
        "intent": "order",
        "code": {
            "coding": [{
                "system": "http://snomed.info/sct",
                "code": "306163007",
                "display": "Referral to physical therapy"
            }],
            "text": "Physical Therapy"
        },
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "authoredOn": "2023-12-10T09:15:00Z",
        "requester": {"display": "Dr. Lisa Martinez"},
        "reasonCode": [{
            "text": "Lower back pain rehabilitation"
        }]
    }
]

print(f"Creating {len(referrals)} test referrals in SMART Health IT...")
created = []
for i, referral in enumerate(referrals, 1):
    try:
        response = requests.post(
            f"{SMART_BASE}/ServiceRequest",
            json=referral,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code in [200, 201]:
            data = response.json()
            ref_id = data.get("id", "unknown")
            created.append(ref_id)
            print(f"✓ Created referral {i}: {referral['code']['text']} (ID: {ref_id})")
        else:
            print(f"✗ Failed to create referral {i}: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Error creating referral {i}: {e}")

print(f"\n✓ Successfully created {len(created)} referrals for patient {PATIENT_ID}")
print(f"  Test with: http://localhost:8000/api/operational/service-requests?patient_id={PATIENT_ID}&server=smart")
