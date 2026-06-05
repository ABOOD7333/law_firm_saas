"""
قوالب المستندات القانونية اليمنية
15 قالباً جاهزاً للمستندات القانونية الأكثر استخداماً في المكاتب اليمنية
"""

# ===================================================
# 1. صحيفة الدعوى المدنية
# ===================================================
CIVIL_LAWSUIT = {
    "name": "صحيفة الدعوى المدنية",
    "code": "civil_lawsuit",
    "description": "صحيفة رفع دعوى مدنية أمام المحاكم اليمنية",
    "required_fields": ["plaintiff_name", "plaintiff_id", "plaintiff_address",
                        "defendant_name", "defendant_id", "defendant_address",
                        "court_name", "claim_amount", "claim_details",
                        "lawyer_name", "date"],
    "template": """
بسم الله الرحمن الرحيم
جمهورية اليمن
وزارة العدل
محكمة: {court_name}

صحيفة دعوى مدنية
=================

المدعي:
الاسم: {plaintiff_name}
رقم الهوية: {plaintiff_id}
العنوان: {plaintiff_address}

المدعى عليه:
الاسم: {defendant_name}
رقم الهوية: {defendant_id}
العنوان: {defendant_address}

موضوع الدعوى:
{claim_details}

قيمة المطالبة: {claim_amount} ريال يمني

الطلبات:
1. قبول الدعوى شكلاً
2. الحكم للمدعي بـ {claim_details}
3. إلزام المدعى عليه بالمصاريف وأتعاب المحاماة

وكيل المدعي:
المحامي/ {lawyer_name}

التاريخ: {date}

"""
}

# ===================================================
# 2. مذكرة الدفاع
# ===================================================
DEFENSE_MEMO = {
    "name": "مذكرة دفاع",
    "code": "defense_memo",
    "description": "مذكرة دفاع عن المتهم أو المدعى عليه",
    "required_fields": ["case_number", "court_name", "client_name",
                        "opponent_name", "defense_points", "lawyer_name", "date"],
    "template": """
بسم الله الرحمن الرحيم
جمهورية اليمن
وزارة العدل

مذكرة دفاع
==========

إلى المحكمة الموقرة: {court_name}
في القضية رقم: {case_number}

المدعى عليه / المتهم: {client_name}
المدعي / المدعي العام: {opponent_name}

أولاً: في الوقائع
{facts}

ثانياً: في القانون
{defense_points}

ثالثاً: الطلبات
1. الحكم ببراءة موكلنا / رفض الدعوى
2. إلزام المدعي بالمصاريف والأتعاب

المحامي/ {lawyer_name}
التاريخ: {date}
"""
}

# ===================================================
# 3. عقد البيع
# ===================================================
SALE_CONTRACT = {
    "name": "عقد بيع",
    "code": "sale_contract",
    "description": "عقد بيع عقار أو منقول",
    "required_fields": ["seller_name", "seller_id", "buyer_name", "buyer_id",
                        "property_description", "price", "payment_method",
                        "delivery_date", "city", "date"],
    "template": """
بسم الله الرحمن الرحيم

عقد بيع
========

إنه في يوم {date} بمدينة {city}، اتفق كل من:

البائع: {seller_name}
رقم الهوية: {seller_id}

والمشتري: {buyer_name}
رقم الهوية: {buyer_id}

على إبرام هذا العقد وفق الشروط الآتية:

البند الأول: موضوع العقد
باع البائع وملّك المشتري ما يأتي: {property_description}

البند الثاني: الثمن
اتفق الطرفان على ثمن مقداره: {price} ريال يمني
طريقة الدفع: {payment_method}

البند الثالث: التسليم
يلتزم البائع بتسليم المبيع بتاريخ: {delivery_date}

البند الرابع: الضمان
يضمن البائع للمشتري خلو المبيع من أي عيوب خفية

البند الخامس: النزاعات
تختص محاكم {city} بالنظر في أي نزاع ينشأ عن هذا العقد

البائع                          المشتري
{seller_name}                   {buyer_name}
التوقيع: ___________            التوقيع: ___________
"""
}

# ===================================================
# 4. عقد الإيجار
# ===================================================
LEASE_CONTRACT = {
    "name": "عقد إيجار",
    "code": "lease_contract",
    "description": "عقد إيجار عقار سكني أو تجاري",
    "required_fields": ["landlord_name", "landlord_id", "tenant_name", "tenant_id",
                        "property_address", "property_description", "monthly_rent",
                        "start_date", "end_date", "deposit", "city", "date"],
    "template": """
بسم الله الرحمن الرحيم

عقد إيجار
==========

إنه في يوم {date}، اتفق كل من:

المؤجر: {landlord_name}
رقم الهوية: {landlord_id}

المستأجر: {tenant_name}
رقم الهوية: {tenant_id}

على إبرام هذا العقد وفق الشروط الآتية:

البند الأول: محل الإيجار
{property_description}
العنوان: {property_address}

البند الثاني: مدة الإيجار
تبدأ من: {start_date}  وتنتهي في: {end_date}

البند الثالث: الأجرة
الأجرة الشهرية: {monthly_rent} ريال يمني
تُسدَّد في اليوم الأول من كل شهر

البند الرابع: التأمين
يدفع المستأجر مبلغ {deposit} ريال تأميناً

البند الخامس: التزامات المستأجر
1. المحافظة على العقار وصيانته
2. عدم التأجير من الباطن إلا بإذن كتابي
3. إخلاء العقار فور انتهاء المدة

البند السادس: النزاعات
تختص محاكم {city} بالنظر في أي نزاع ينشأ عن هذا العقد

المؤجر                          المستأجر
{landlord_name}                 {tenant_name}
التوقيع: ___________            التوقيع: ___________
"""
}

# ===================================================
# 5. عقد الشراكة التجارية
# ===================================================
PARTNERSHIP_CONTRACT = {
    "name": "عقد شراكة تجارية",
    "code": "partnership_contract",
    "description": "عقد تأسيس شراكة تجارية بين طرفين أو أكثر",
    "required_fields": ["partner1_name", "partner1_id", "partner1_share",
                        "partner2_name", "partner2_id", "partner2_share",
                        "business_name", "business_type", "capital",
                        "start_date", "city", "date"],
    "template": """
بسم الله الرحمن الرحيم

عقد شراكة تجارية
=================

إنه في يوم {date} بمدينة {city}، اتفق كل من:

الشريك الأول: {partner1_name}  - رقم الهوية: {partner1_id}
الشريك الثاني: {partner2_name} - رقم الهوية: {partner2_id}

على تأسيس شراكة تجارية وفق الشروط الآتية:

البند الأول: الاسم التجاري
{business_name}

البند الثاني: النشاط التجاري
{business_type}

البند الثالث: رأس المال
إجمالي رأس المال: {capital} ريال يمني
حصة {partner1_name}: {partner1_share}%
حصة {partner2_name}: {partner2_share}%

البند الرابع: توزيع الأرباح والخسائر
تُوزع الأرباح والخسائر بنسبة حصص الشركاء

البند الخامس: مدة الشراكة
تبدأ من {start_date} وتستمر لحين اتفاق الطرفين على الإنهاء

البند السادس: إنهاء الشراكة
لا يحق لأي شريك إنهاء الشراكة إلا بإشعار كتابي مسبق مدته 60 يوماً

{partner1_name}                 {partner2_name}
التوقيع: ___________            التوقيع: ___________
"""
}

# ===================================================
# 6. الوكالة القانونية
# ===================================================
POWER_OF_ATTORNEY = {
    "name": "وكالة قانونية",
    "code": "power_of_attorney",
    "description": "وكالة قانونية لمحامٍ للتقاضي أو الإجراءات",
    "required_fields": ["client_name", "client_id", "client_address",
                        "lawyer_name", "lawyer_license", "case_description",
                        "powers", "city", "date"],
    "template": """
بسم الله الرحمن الرحيم

وكالة قانونية
=============

أنا الموقع أدناه:
الاسم: {client_name}
رقم الهوية: {client_id}
العنوان: {client_address}

أُوكِّل وأُنيب عني السيد/ {lawyer_name}
رقم الترخيص المهني: {lawyer_license}
المحامي المرخص بمزاولة مهنة المحاماة أمام كافة المحاكم اليمنية

في الدفاع عني وتمثيلي في: {case_description}

وله في سبيل ذلك الصلاحيات الآتية:
{powers}

وهذه الوكالة {is_general} وتسري حتى انتهاء الغرض منها.

الموكِّل: {client_name}
الهوية رقم: {client_id}
التوقيع: ___________
التاريخ: {date}
المدينة: {city}

تمت المصادقة على هذه الوكالة أمام:
"""
}

# ===================================================
# 7. الإنذار القانوني
# ===================================================
LEGAL_WARNING = {
    "name": "إنذار قانوني",
    "code": "legal_warning",
    "description": "إنذار قانوني رسمي",
    "required_fields": ["sender_name", "sender_id", "receiver_name", "receiver_address",
                        "warning_subject", "warning_details", "deadline",
                        "lawyer_name", "date"],
    "template": """
بسم الله الرحمن الرحيم

إنذار قانوني
============

إلى السيد/ {receiver_name}
العنوان: {receiver_address}

تحية طيبة وبعد،

بالنيابة عن موكلي السيد/ {sender_name}
رقم الهوية: {sender_id}

يُنذركم موكلي بما يلي:
{warning_details}

وإذا لم تقوموا بـ {required_action} خلال {deadline} من تاريخ استلام هذا الإنذار، فإن موكلي سيلجأ إلى القضاء للمطالبة بحقوقه كاملة مع المصاريف والأتعاب.

وعليكم العلم والمسؤولية.

المحامي/ {lawyer_name}
التاريخ: {date}
"""
}

# ===================================================
# 8. طعن الاستئناف
# ===================================================
APPEAL = {
    "name": "طعن استئناف",
    "code": "appeal",
    "description": "طعن بالاستئناف على حكم ابتدائي",
    "required_fields": ["case_number", "judgment_date", "court_name",
                        "appellant_name", "appellee_name",
                        "appeal_grounds", "requests", "lawyer_name", "date"],
    "template": """
بسم الله الرحمن الرحيم
جمهورية اليمن
محكمة الاستئناف

استئناف
=======

إلى محكمة الاستئناف الموقرة

يتقدم {appellant_name} بموجب وكيله المحامي/ {lawyer_name}
بالطعن بالاستئناف على الحكم الصادر في القضية رقم {case_number}
بتاريخ {judgment_date} من محكمة {court_name}
في مواجهة: {appellee_name}

أسباب الاستئناف:
================
{appeal_grounds}

الطلبات:
========
{requests}

المستأنف/ {appellant_name}
بواسطة وكيله المحامي/ {lawyer_name}
التاريخ: {date}
"""
}

# ===================================================
# 9. طلب تنفيذ حكم
# ===================================================
EXECUTION_REQUEST = {
    "name": "طلب تنفيذ حكم",
    "code": "execution_request",
    "description": "طلب تنفيذ حكم قضائي نهائي",
    "required_fields": ["court_name", "case_number", "judgment_date",
                        "judgment_details", "debtor_name", "debtor_address",
                        "creditor_name", "execution_amount", "lawyer_name", "date"],
    "template": """
بسم الله الرحمن الرحيم

طلب تنفيذ
==========

إلى قاضي التنفيذ في محكمة: {court_name}

يتشرف {creditor_name} بواسطة وكيله المحامي/ {lawyer_name}
بتقديم طلب تنفيذ الحكم الصادر في القضية رقم: {case_number}
بتاريخ: {judgment_date}

ومضمون الحكم: {judgment_details}
المبلغ المطلوب تنفيذه: {execution_amount} ريال يمني

في مواجهة المنفذ ضده: {debtor_name}
العنوان: {debtor_address}

لذلك يلتمس الطالب من قاضي التنفيذ اتخاذ الإجراءات اللازمة لتنفيذ الحكم المذكور.

الطالب/ {creditor_name}
المحامي/ {lawyer_name}
التاريخ: {date}
"""
}

# ===================================================
# 10. عقد العمل
# ===================================================
EMPLOYMENT_CONTRACT = {
    "name": "عقد عمل",
    "code": "employment_contract",
    "description": "عقد عمل بين صاحب العمل والموظف",
    "required_fields": ["employer_name", "employer_id", "employee_name", "employee_id",
                        "job_title", "salary", "start_date", "contract_duration",
                        "work_hours", "city", "date"],
    "template": """
بسم الله الرحمن الرحيم

عقد عمل
========

إنه في يوم {date} بمدينة {city}، اتفق كل من:

صاحب العمل: {employer_name}  - رقم السجل: {employer_id}
العامل: {employee_name}       - رقم الهوية: {employee_id}

على إبرام هذا العقد وفق أحكام قانون العمل اليمني رقم (5) لسنة 1995م والشروط الآتية:

البند الأول: المسمى الوظيفي
{job_title}

البند الثاني: الأجر
الأجر الشهري: {salary} ريال يمني
يُصرف في نهاية كل شهر

البند الثالث: مدة العقد
يبدأ من {start_date} لمدة {contract_duration}

البند الرابع: ساعات العمل
{work_hours} ساعة يومياً - 6 أيام في الأسبوع

البند الخامس: الإجازات
- الإجازة السنوية: 30 يوماً بأجر كامل
- إجازة الأعياد الرسمية
- الإجازة المرضية وفق القانون

البند السادس: إنهاء العقد
يجوز لأي طرف إنهاء العقد بإشعار مسبق مدته 30 يوماً

صاحب العمل                     العامل
{employer_name}                 {employee_name}
التوقيع: ___________            التوقيع: ___________
"""
}

# ===================================================
# 11. إقرار بدين
# ===================================================
DEBT_ACKNOWLEDGMENT = {
    "name": "إقرار بدين",
    "code": "debt_acknowledgment",
    "description": "إقرار بوجود دين ومديونية",
    "required_fields": ["debtor_name", "debtor_id", "creditor_name",
                        "debt_amount", "debt_reason", "payment_deadline",
                        "witnesses", "city", "date"],
    "template": """
بسم الله الرحمن الرحيم

إقرار بدين
===========

أنا الموقع أدناه:
المُقِر: {debtor_name}
رقم الهوية: {debtor_id}

أُقِر وأعترف بأن في ذمتي لصالح السيد/ {creditor_name}
مبلغاً مالياً قدره: {debt_amount} ريال يمني ({debt_amount_words})

وذلك بسبب: {debt_reason}

وأتعهد بسداد هذا المبلغ كاملاً بتاريخ: {payment_deadline}

وإذا تأخرت عن السداد يحق للدائن اتخاذ كافة الإجراءات القانونية.

المُقِر: {debtor_name}
التوقيع: ___________
التاريخ: {date}
المدينة: {city}

الشهود:
1. {witness1}
2. {witness2}
"""
}

# ===================================================
# 12. اتفاقية تسوية ودية
# ===================================================
SETTLEMENT_AGREEMENT = {
    "name": "اتفاقية تسوية ودية",
    "code": "settlement_agreement",
    "description": "اتفاقية تسوية ودية لإنهاء نزاع",
    "required_fields": ["party1_name", "party1_id", "party2_name", "party2_id",
                        "dispute_description", "settlement_terms",
                        "settlement_amount", "city", "date"],
    "template": """
بسم الله الرحمن الرحيم

اتفاقية تسوية ودية
==================

إنه في يوم {date} بمدينة {city}، اتفق كل من:

الطرف الأول: {party1_name}  - رقم الهوية: {party1_id}
الطرف الثاني: {party2_name} - رقم الهوية: {party2_id}

على إنهاء النزاع المتعلق بـ: {dispute_description}

بالشروط الآتية:
{settlement_terms}

وقبل الطرفان بهذه التسوية كاملةً وصرّحا بانتهاء النزاع بينهما نهائياً ولا تثريب عليه من بعد ذلك.

الطرف الأول                    الطرف الثاني
{party1_name}                   {party2_name}
التوقيع: ___________            التوقيع: ___________
"""
}

# ===================================================
# 13. طلب تأجيل جلسة
# ===================================================
HEARING_POSTPONEMENT = {
    "name": "طلب تأجيل جلسة",
    "code": "hearing_postponement",
    "description": "طلب تأجيل موعد جلسة قضائية",
    "required_fields": ["court_name", "case_number", "hearing_date",
                        "client_name", "postponement_reason",
                        "lawyer_name", "date"],
    "template": """
بسم الله الرحمن الرحيم

طلب تأجيل جلسة
===============

إلى المحكمة الموقرة: {court_name}

الموضوع: طلب تأجيل الجلسة المحددة في القضية رقم: {case_number}

بتاريخ {date}، يتقدم {client_name} بواسطة وكيله المحامي/ {lawyer_name}
بطلب تأجيل الجلسة المقررة في: {hearing_date}

للأسباب الآتية:
{postponement_reason}

لذلك يلتمس الطالب من المحكمة الموقرة الأمر بتأجيل الجلسة المذكورة.

وتفضلوا بقبول فائق الاحترام

المحامي/ {lawyer_name}
التاريخ: {date}
"""
}

# ===================================================
# 14. فاتورة أتعاب المحاماة
# ===================================================
LEGAL_INVOICE = {
    "name": "فاتورة أتعاب محاماة",
    "code": "legal_invoice",
    "description": "فاتورة أتعاب محاماة للموكل",
    "required_fields": ["lawyer_name", "lawyer_license", "office_name",
                        "client_name", "case_number", "services",
                        "total_amount", "date"],
    "template": """
بسم الله الرحمن الرحيم

فاتورة أتعاب محاماة
==================

مكتب: {office_name}
المحامي: {lawyer_name}
رقم الترخيص: {lawyer_license}

إلى: {client_name}
في القضية رقم: {case_number}

الخدمات القانونية المقدمة:
============================
{services}

============================
المجموع الإجمالي: {total_amount} ريال يمني

ملاحظة: الأتعاب تشمل جميع الخدمات القانونية المذكورة أعلاه.
دُفع / لم يُدفع

التاريخ: {date}
توقيع المحامي: ___________
"""
}

# ===================================================
# 15. طلب كشف حساب قضية
# ===================================================
CASE_STATEMENT_REQUEST = {
    "name": "طلب كشف حساب قضية",
    "code": "case_statement",
    "description": "طلب كشف حساب وملخص قضية",
    "required_fields": ["case_number", "client_name", "court_name",
                        "case_type", "start_date", "current_status",
                        "key_dates", "lawyer_name", "date"],
    "template": """
بسم الله الرحمن الرحيم

ملخص وكشف حساب القضية
=======================

القضية رقم: {case_number}
الموكل: {client_name}
المحكمة: {court_name}
نوع القضية: {case_type}
تاريخ التعاقد: {start_date}

الحالة الراهنة: {current_status}

أهم المواعيد والإجراءات:
=========================
{key_dates}

ملاحظات المحامي:
================
{lawyer_notes}

المحامي/ {lawyer_name}
التاريخ: {date}
"""
}

# ===================================================
# فهرس جميع القوالب
# ===================================================
ALL_TEMPLATES = {
    "civil_lawsuit": CIVIL_LAWSUIT,
    "defense_memo": DEFENSE_MEMO,
    "sale_contract": SALE_CONTRACT,
    "lease_contract": LEASE_CONTRACT,
    "partnership_contract": PARTNERSHIP_CONTRACT,
    "power_of_attorney": POWER_OF_ATTORNEY,
    "legal_warning": LEGAL_WARNING,
    "appeal": APPEAL,
    "execution_request": EXECUTION_REQUEST,
    "employment_contract": EMPLOYMENT_CONTRACT,
    "debt_acknowledgment": DEBT_ACKNOWLEDGMENT,
    "settlement_agreement": SETTLEMENT_AGREEMENT,
    "hearing_postponement": HEARING_POSTPONEMENT,
    "legal_invoice": LEGAL_INVOICE,
    "case_statement": CASE_STATEMENT_REQUEST,
}

# فهرس البحث بالكلمات المفتاحية
TEMPLATE_KEYWORDS = {
    "صحيفة دعوى": "civil_lawsuit",
    "دعوى مدنية": "civil_lawsuit",
    "رفع دعوى": "civil_lawsuit",
    "مذكرة دفاع": "defense_memo",
    "دفاع": "defense_memo",
    "مرافعة": "defense_memo",
    "عقد بيع": "sale_contract",
    "بيع عقار": "sale_contract",
    "بيع": "sale_contract",
    "عقد إيجار": "lease_contract",
    "إيجار": "lease_contract",
    "تأجير": "lease_contract",
    "شراكة": "partnership_contract",
    "عقد شراكة": "partnership_contract",
    "شركة": "partnership_contract",
    "وكالة": "power_of_attorney",
    "توكيل": "power_of_attorney",
    "وكالة قانونية": "power_of_attorney",
    "إنذار": "legal_warning",
    "إخطار": "legal_warning",
    "تحذير": "legal_warning",
    "استئناف": "appeal",
    "طعن": "appeal",
    "تنفيذ": "execution_request",
    "طلب تنفيذ": "execution_request",
    "عقد عمل": "employment_contract",
    "توظيف": "employment_contract",
    "راتب": "employment_contract",
    "إقرار دين": "debt_acknowledgment",
    "مديونية": "debt_acknowledgment",
    "تسوية": "settlement_agreement",
    "صلح": "settlement_agreement",
    "اتفاقية": "settlement_agreement",
    "تأجيل جلسة": "hearing_postponement",
    "تأجيل": "hearing_postponement",
    "فاتورة": "legal_invoice",
    "أتعاب": "legal_invoice",
    "كشف حساب": "case_statement",
    "ملخص قضية": "case_statement",
}
