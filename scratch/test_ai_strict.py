import os
import sys

# Add the project root to python path
sys.path.append(os.path.abspath('.'))

from database.database import SessionLocal
from database.models import AccessProfiles
from routers.ai_assistant import _unified_assistant_search, _format_unified_search_response
from ai_engine.intent_detector import IntentDetector

db = SessionLocal()
try:
    user = db.query(AccessProfiles).filter(AccessProfiles.id == 1).first()
    office_id = user.office_id if user else 1
    
    detector = IntentDetector()
    
    test_queries = [
        "كيف اضيف قضية جديدة",
        "المادة 30 من قانون العمل اليمني",
        "طريقة عمل كبسة اللحم",
        "من هو مخترع الطائرة؟"
    ]
    
    print("=" * 60)
    print("تبدأ محاكاة فحص المساعد الذكي القانوني المحلي وتطبيق الفلترة الصارمة")
    print("=" * 60)
    
    for idx, query in enumerate(test_queries, 1):
        print(f"\n{idx}. السؤال: \"{query}\"")
        
        # 1. كشف النية
        intent = detector.detect(query)
        print(f"   النية المكتشفة: {intent.type} (الثقة: {intent.confidence})")
        
        # 2. البحث الموحد
        results = _unified_assistant_search(db, office_id, query)
        
        # 3. صياغة الرد
        response = _format_unified_search_response(results, query)
        
        print("   الرد المولد:")
        print("-" * 50)
        print(response)
        print("-" * 50)
        
        # 4. التدقيق
        if query == "طريقة عمل كبسة اللحم" or query == "من هو مخترع الطائرة؟":
            assert "لا يمكنني الإجابة" in response or "عذراً" in response, "فشل فحص حظر الأسئلة الخارجية!"
            print("   ✅ نجح فحص حظر الأسئلة الخارجية ومنع التخمين.")
        elif query == "كيف اضيف قضية جديدة":
            assert "دليل المنصة" in response or "إضافة قضية" in response, "فشل فحص إرشاد النظام!"
            print("   ✅ نجح فحص دليل تشغيل واستخدام النظام.")
        elif "المادة 30" in query:
            assert "قانون العمل" in response or "ثماني ساعات" in response, "فشل فحص القوانين اليمنية!"
            print("   ✅ نجح فحص القوانين اليمنية المدمجة.")

    print("\n" + "=" * 60)
    print("✅ نجحت جميع فحوصات دقة المساعد الذكي والفلترة بنسبة 100%!")
    print("=" * 60)

except Exception as e:
    import traceback
    print("حدث خطأ أثناء الفحص:")
    print(traceback.format_exc())
finally:
    db.close()
