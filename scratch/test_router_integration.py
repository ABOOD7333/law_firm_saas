import sys
import os

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock pytesseract, pdf2image, chromadb, sentence_transformers, and langchain_text_splitters to prevent import errors
from unittest.mock import MagicMock
sys.modules['pytesseract'] = MagicMock()
sys.modules['pdf2image'] = MagicMock()
sys.modules['chromadb'] = MagicMock()
sys.modules['chromadb.config'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['langchain_text_splitters'] = MagicMock()

from fastapi.testclient import TestClient
from main import app
from dependencies import get_current_user
from database.database import SessionLocal
from database.models import AccessProfiles

db = SessionLocal()
user = db.query(AccessProfiles).filter(AccessProfiles.id == 1).first()
db.close()

# Mock get_current_user dependency
def mock_get_current_user(request = None, db = None):
    user.subscription_expired = False
    user.role = 'مدير'
    return user

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)
client.cookies.set("csrf_token", "test-csrf-token")
client.headers["X-CSRF-Token"] = "test-csrf-token"

def run_tests():
    print("--- Starting AI Assistant Router Integration Tests ---")
    
    # Test 1: Name matching (سحر الهطامي)
    print("Testing Client Name Search ('هل اسم سحر الهطامي هي موكلة')...")
    resp = client.post("/api/ai/chat", json={"question": "هل اسم سحر الهطامي هي موكلة"})
    print(f"Response Status: {resp.status_code}")
    print(f"Response Content: {resp.text}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["success"] is True
    assert "سحر الهطامي" in data["answer"], f"Expected 'سحر الهطامي' in answer, got: {data['answer']}"
    print("✅ Client Name Search passed!")
    
    # Test 2: Document Intent Detection & Form Fields Return
    print("Testing Document Form Fields request ('عقد إيجار')...")
    resp = client.post("/api/ai/chat", json={"question": "صياغة عقد إيجار"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["doc_type"] == "lease_contract"
    assert "landlord_name" in data["form_fields"]
    assert "tenant_name" in data["form_fields"]
    print("✅ Document Form Fields request passed!")
    
    # Test 3: Document Generation
    print("Testing Asynchronous Document Generation...")
    fields = {
        "landlord_name": "عبد الله محمد",
        "landlord_id": "1234567890",
        "tenant_name": "سحر الهطامي",
        "tenant_id": "0987654321",
        "property_address": "صنعاء - شارع حدة",
        "property_description": "شقة سكنية رقم 5",
        "monthly_rent": "150000",
        "start_date": "2026/06/01",
        "end_date": "2027/06/01",
        "deposit": "150000",
        "city": "صنعاء"
    }
    resp = client.post("/api/ai/generate-document", json={"doc_code": "lease_contract", "fields": fields})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "عبد الله محمد" in data["document"]
    assert "سحر الهطامي" in data["document"]
    assert "150000" in data["document"]
    print("✅ Document Generation passed!")
    
    print("\n🎉 ALL AI ASSISTANT INTEGRATION TESTS PASSED SUCCESSFULLY! 🎉")

if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        import traceback
        print("❌ Test failed:")
        traceback.print_exc()
        sys.exit(1)
