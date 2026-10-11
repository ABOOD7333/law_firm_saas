import sys

with open('templates/superadmin.html', 'rb') as f:
    content = f.read().decode('utf-8')

# We'll insert the Payment Requests table right after the Offices table container
offices_table_end = """    </div>\n</div>"""

payment_table = """
<!-- Payment Requests -->
<div class="card" style="margin-top: 2rem;">
    <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 15px; border-bottom: 1px solid #e2e8f0;">
        <h3 style="margin: 0; font-size: 1.25rem; color: #1e293b;">طلبات الدفع (الاشتراكات)</h3>
    </div>
    <div class="table-container" style="overflow-x: auto;">
        <table class="data-table" style="width: 100%; text-align: right; border-collapse: collapse;">
            <thead>
                <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                    <th style="padding: 15px; color: #475569;"># ID</th>
                    <th style="padding: 15px; color: #475569;">المكتب</th>
                    <th style="padding: 15px; color: #475569;">إيميل الصاحب</th>
                    <th style="padding: 15px; color: #475569;">الخطة / المبلغ</th>
                    <th style="padding: 15px; color: #475569;">تاريخ الطلب</th>
                    <th style="padding: 15px; color: #475569;">الحالة</th>
                    <th style="padding: 15px; color: #475569;">إجراء</th>
                </tr>
            </thead>
            <tbody>
                {% for pr in payment_requests %}
                <tr style="border-bottom: 1px solid #f1f5f9; transition: background 0.2s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='white'">
                    <td style="padding: 15px; font-weight: bold; color: #64748b;">{{ pr.id }}</td>
                    <td style="padding: 15px; font-weight: 700; color: #0f172a;">{{ pr.office_name }}</td>
                    <td style="padding: 15px; font-size: 0.85rem; color: #64748b;">{{ pr.owner_email }}</td>
                    <td style="padding: 15px;">
                        <span style="font-weight: bold; color: #5c2d91;">{{ "شهري" if pr.plan == "monthly" else "سنوي" }}</span>
                        <br>
                        <span style="font-size: 0.85rem; color: #64748b;">${{ pr.amount }} (Ref: {{ pr.transfer_ref }})</span>
                    </td>
                    <td style="padding: 15px; font-size: 0.9rem; color: #64748b;" dir="ltr">{{ pr.submitted_at[:10] }}</td>
                    <td style="padding: 15px;">
                        {% if pr.status == 'pending' %}
                            <span style="background: #fef3c7; color: #d97706; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;"><i class="fa-solid fa-clock"></i> بانتظار المراجعة</span>
                        {% elif pr.status == 'approved' %}
                            <span style="background: #dcfce7; color: #16a34a; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;"><i class="fa-solid fa-check"></i> مفعل</span>
                        {% else %}
                            <span style="background: #fee2e2; color: #dc2626; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;"><i class="fa-solid fa-times"></i> مرفوض</span>
                        {% endif %}
                    </td>
                    <td style="padding: 15px;">
                        <button onclick="openReceiptModal({{ pr.id }}, '{{ pr.receipt_base64 }}', '{{ pr.status }}')" style="background: #3b82f6; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 0.85rem; cursor: pointer;">
                            <i class="fa-solid fa-eye"></i> عرض السند
                        </button>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
"""

# Insert payment table
if "طلبات الدفع (الاشتراكات)" not in content:
    content = content.replace(offices_table_end, offices_table_end + payment_table, 1)

# Now update the modal to include notes for rejection
old_modal = """<!-- Receipt Modal -->
<div id="receiptModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; justify-content: center; align-items: center;">
    <div style="background: white; border-radius: 12px; width: 90%; max-width: 500px; padding: 20px; text-align: center;">
        <h3 style="margin-top: 0;">مراجعة سند الدفع</h3>
        <div style="width: 100%; max-height: 400px; overflow-y: auto; margin-bottom: 20px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px;">
            <img id="receiptImage" src="" style="max-width: 100%; height: auto; border-radius: 4px;">
        </div>
        <div style="display: flex; gap: 10px; justify-content: center;">
            <button onclick="handleReceiptAction('approve')" style="background: #10b981; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; flex: 1;">تأكيد واعتماد السند</button>
            <button onclick="handleReceiptAction('reject')" style="background: #ef4444; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; flex: 1;">رفض السند</button>
        </div>
        <button onclick="closeReceiptModal()" style="margin-top: 15px; background: none; border: none; color: #64748b; cursor: pointer;">إغلاق النافذة</button>
    </div>
</div>"""

new_modal = """<!-- Receipt Modal -->
<div id="receiptModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; justify-content: center; align-items: center; padding: 20px;">
    <div style="background: white; border-radius: 16px; width: 100%; max-width: 500px; padding: 24px; text-align: center; max-height: 90vh; overflow-y: auto;">
        <h3 style="margin-top: 0; font-size: 1.3rem; margin-bottom: 15px;">مراجعة سند الدفع</h3>
        <div style="width: 100%; max-height: 400px; overflow-y: auto; margin-bottom: 20px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px; background: #f8fafc;">
            <img id="receiptImage" src="" style="max-width: 100%; height: auto; border-radius: 4px;">
        </div>
        
        <div id="rejection-box" style="display: none; text-align: right; margin-bottom: 20px;">
            <label style="display: block; font-size: 0.9rem; font-weight: bold; margin-bottom: 8px;">سبب الرفض (سيتم إرساله للمستخدم):</label>
            <textarea id="rejection-notes" rows="3" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #e2e8f0; font-family: inherit; font-size: 0.9rem;" placeholder="مثال: الصورة غير واضحة، أو المبلغ غير مكتمل..."></textarea>
        </div>

        <div id="modal-actions" style="display: flex; gap: 10px; justify-content: center;">
            <button onclick="handleReceiptAction('approve')" style="background: #10b981; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; flex: 1;">تأكيد واعتماد</button>
            <button onclick="showRejectionBox()" style="background: #ef4444; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; flex: 1;">رفض السند</button>
        </div>
        
        <div id="confirm-reject-actions" style="display: none; gap: 10px; justify-content: center;">
            <button onclick="handleReceiptAction('reject')" style="background: #dc2626; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; flex: 1;">تأكيد الرفض والإرسال</button>
            <button onclick="hideRejectionBox()" style="background: #e2e8f0; color: #475569; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; flex: 1;">تراجع</button>
        </div>
        
        <button onclick="closeReceiptModal()" style="margin-top: 15px; background: none; border: none; color: #64748b; cursor: pointer; font-weight: bold; text-decoration: underline;">إغلاق النافذة</button>
    </div>
</div>"""

if old_modal in content:
    content = content.replace(old_modal, new_modal)


# Update JavaScript functions
js_code_to_replace = """let currentOfficeId = null;

function openReceiptModal(officeId, base64Str) {
    currentOfficeId = officeId;
    document.getElementById('receiptImage').src = base64Str;
    document.getElementById('receiptModal').style.display = 'flex';
}

function closeReceiptModal() {
    document.getElementById('receiptModal').style.display = 'none';
    currentOfficeId = null;
}

async function handleReceiptAction(action) {
    if (!confirm(action === 'approve' ? "هل أنت متأكد من صحة السند وتريد تفعيل الاشتراك؟" : "هل أنت متأكد من رفض السند؟")) return;
    
    try {
        const csrfToken = document.cookie.split('; ').find(r => r.startsWith('csrf_token='))?.split('=')[1] || '';
        const res = await fetch('/api/superadmin/approve-receipt/' + currentOfficeId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
            body: JSON.stringify({ action: action })
        });
        const data = await res.json();
        
        if (data.success) {
            alert(data.message);
            window.location.reload();
        } else {
            alert(data.error || "حدث خطأ غير متوقع");
        }
    } catch(e) {
        alert('خطأ في الاتصال');
    }
}"""

new_js_code = """let currentPaymentId = null;

function openReceiptModal(paymentId, base64Str, status) {
    currentPaymentId = paymentId;
    document.getElementById('receiptImage').src = base64Str;
    document.getElementById('receiptModal').style.display = 'flex';
    
    // Reset state
    hideRejectionBox();
    
    // Hide action buttons if already processed
    if (status !== 'pending') {
        document.getElementById('modal-actions').style.display = 'none';
    } else {
        document.getElementById('modal-actions').style.display = 'flex';
    }
}

function closeReceiptModal() {
    document.getElementById('receiptModal').style.display = 'none';
    currentPaymentId = null;
    hideRejectionBox();
}

function showRejectionBox() {
    document.getElementById('modal-actions').style.display = 'none';
    document.getElementById('rejection-box').style.display = 'block';
    document.getElementById('confirm-reject-actions').style.display = 'flex';
}

function hideRejectionBox() {
    document.getElementById('rejection-box').style.display = 'none';
    document.getElementById('confirm-reject-actions').style.display = 'none';
    document.getElementById('modal-actions').style.display = 'flex';
    document.getElementById('rejection-notes').value = '';
}

async function handleReceiptAction(action) {
    let notes = '';
    if (action === 'approve') {
        if (!confirm("هل أنت متأكد من صحة السند وتريد تفعيل الاشتراك؟")) return;
    } else if (action === 'reject') {
        notes = document.getElementById('rejection-notes').value.trim();
        if (!notes) {
            alert("يرجى كتابة سبب الرفض ليتم إرساله للمستخدم.");
            return;
        }
        if (!confirm("سيتم رفض السند وإرسال إيميل للمستخدم. تأكيد؟")) return;
    }
    
    try {
        const csrfToken = document.cookie.split('; ').find(r => r.startsWith('csrf_token='))?.split('=')[1] || '';
        const res = await fetch('/api/superadmin/approve-payment/' + currentPaymentId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
            body: JSON.stringify({ action: action, notes: notes })
        });
        const data = await res.json();
        
        if (data.success) {
            alert(data.message);
            window.location.reload();
        } else {
            alert(data.error || "حدث خطأ غير متوقع");
        }
    } catch(e) {
        alert('خطأ في الاتصال');
    }
}"""

if js_code_to_replace in content:
    content = content.replace(js_code_to_replace, new_js_code)

with open('templates/superadmin.html', 'wb') as f:
    f.write(content.encode('utf-8'))
print("Successfully patched superadmin.html")
