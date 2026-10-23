/**
 * Smart Case Selector (محدد وباحث القضايا الذكي)
 * يتيح للمستخدم إما اختيار رقم القضية من القائمة أو كتابة الرقم/العنوان/اسم الموكل.
 * مع كل حرف أو رقم يكتبه تظهر القضايا المطابقة أو القريبة فوراً (Predictive Live Search).
 * عند اختيار القضية، يتم تعبئة كافة الحقول المرتبطة بها في النموذج تلقائياً.
 * يستثنى من ذلك حقل رقم القضية في إدارة القضايا (التوليد التلقائي المغلق).
 */

(function () {
    'use strict';

    // استثناء حقل رقم القضية في فتح قضية جديدة
    function isExceptionField(el) {
        if (!el) return true;
        if (el.id === 'add_case_number_field') return true;
        if (el.closest && el.closest('#addCaseForm') && (el.name === 'case_number' || el.id === 'add_case_number_field')) return true;
        if (el.getAttribute('data-skip-smart-case') === 'true') return true;
        return false;
    }

    // تنظيف النصوص للمقارنة
    function normalizeText(str) {
        if (!str) return '';
        return String(str)
            .toLowerCase()
            .replace(/[\u064B-\u065F]/g, '') // إزالة التشكيل
            .replace(/[أإآ]/g, 'ا')
            .replace(/ة/g, 'ه')
            .replace(/ى/g, 'ي')
            .trim();
    }

    // تقييم قرب النتيجة لترتيب القضايا الأقرب لرقم البحث أولاً
    function getMatchScore(item, query) {
        const q = normalizeText(query);
        if (!q) return 100;
        const num = normalizeText(item.case_number || '');
        const title = normalizeText(item.title || '');
        const client = normalizeText(item.client_name || '');

        // 1. تطابق تام مع رقم القضية
        if (num === q) return 1000;
        // 2. رقم القضية يبدأ بما كتبه المستخدم (مثل 1448 -> 1448/1)
        if (num.startsWith(q)) return 850;
        // 3. الجزء التسلسلي بعد الشرطة يطابق ما كتبه المستخدم (مثل كتابة 1 فيظهر 1448/1)
        const slashIdx = num.indexOf('/');
        if (slashIdx !== -1) {
            const seq = num.substring(slashIdx + 1);
            if (seq === q) return 800;
            if (seq.startsWith(q)) return 750;
            if (seq.includes(q)) return 650;
        }
        // 4. رقم القضية يحتوي على الرقم المكتوب
        if (num.includes(q)) return 600;
        // 5. الموكل أو العنوان يبدأ بعبارة البحث
        if (client.startsWith(q)) return 500;
        if (title.startsWith(q)) return 450;
        if (client.includes(q)) return 350;
        if (title.includes(q)) return 300;
        return 50;
    }

    // تمييز الكلمات المطابقة داخل النص
    function highlightMatch(text, query) {
        if (!text || !query) return escapeHtml(text || '');
        const normText = normalizeText(text);
        const normQuery = normalizeText(query);
        const idx = normText.indexOf(normQuery);
        if (idx === -1) return escapeHtml(text);

        const before = text.substring(0, idx);
        const match = text.substring(idx, idx + query.length);
        const after = text.substring(idx + query.length);
        return `${escapeHtml(before)}<strong style="color: #1d4ed8; background: #dbeafe; padding: 0 3px; border-radius: 4px;">${escapeHtml(match)}</strong>${escapeHtml(after)}`;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // التعبئة التلقائية لكافة الحقول المرتبطة بالقضية
    function autoFillRelatedFields(container, caseData) {
        if (!container || !caseData) return;

        let autoFilledCount = 0;

        // 1. اسم الموكل (طرف أول / صاحب التوكيل)
        const clientNameFields = container.querySelectorAll(
            '#fName, input[name="client_name"], input[name="principal_name"], #principal_name, #add_client_name, input#fPrincipal'
        );
        clientNameFields.forEach(f => {
            if (caseData.client_name) {
                f.value = caseData.client_name;
                flashField(f);
                autoFilledCount++;
            }
        });

        // 2. قائمة الموكلين المنسدلة (client_id)
        if (caseData.client_id) {
            const clientSelects = container.querySelectorAll('select[name="client_id"], #add_client_id, #client_id');
            clientSelects.forEach(s => {
                let opt = s.querySelector(`option[value="${caseData.client_id}"]`);
                if (opt) {
                    s.value = String(caseData.client_id);
                    s.dispatchEvent(new Event('change', { bubbles: true }));
                    flashField(s);
                    autoFilledCount++;
                }
            });
        }

        // 3. المحامي / الوكيل
        const lawyerNameFields = container.querySelectorAll(
            '#fAgent, input[name="lead_lawyer_name"], input[name="agent_name"], #agent_name, #fLawyer'
        );
        lawyerNameFields.forEach(f => {
            if (caseData.lead_lawyer_name) {
                f.value = caseData.lead_lawyer_name;
                flashField(f);
                autoFilledCount++;
            }
        });

        // قائمة المحامين المنسدلة (lead_lawyer_id / assignee_user_id)
        if (caseData.lead_lawyer_id) {
            const lawyerSelects = container.querySelectorAll(
                'select[name="lead_lawyer_id"], select[name="assignee_user_id"], select[name="lawyer_id"]'
            );
            lawyerSelects.forEach(s => {
                let opt = s.querySelector(`option[value="${caseData.lead_lawyer_id}"]`);
                if (opt) {
                    s.value = String(caseData.lead_lawyer_id);
                    s.dispatchEvent(new Event('change', { bubbles: true }));
                    flashField(s);
                    autoFilledCount++;
                }
            });
        }

        // 4. المحكمة أو جهة الاختصاص
        const courtFields = container.querySelectorAll(
            '#addCourtName, input[name="court_name"], #court_name, #fAuth, input[name="entity_name"], #add_entity_name'
        );
        courtFields.forEach(f => {
            if (caseData.court_name) {
                f.value = caseData.court_name;
                flashField(f);
                autoFilledCount++;
            }
        });

        // 5. عنوان القضية
        const titleFields = container.querySelectorAll('#rep_case_title, input[name="case_title"]');
        titleFields.forEach(f => {
            if (caseData.title) {
                f.value = caseData.title;
                flashField(f);
                autoFilledCount++;
            }
        });

        // 6. هاتف الموكل إن وجد
        if (caseData.client_phone) {
            const phoneFields = container.querySelectorAll('input[name="phone"], input[name="client_phone"], #client_phone');
            phoneFields.forEach(f => {
                if (!f.value) {
                    f.value = caseData.client_phone;
                    flashField(f);
                    autoFilledCount++;
                }
            });
        }

        // إشعار مرئي أنيق بتعبئة البيانات تلقائياً
        if (autoFilledCount > 0) {
            showAutoFillBadge(container, caseData.case_number, autoFilledCount);
        }
    }

    // وميض خفيف للحقول التي تم تعبئتها تلقائياً
    function flashField(elem) {
        if (!elem) return;
        const origBorder = elem.style.borderColor;
        const origBg = elem.style.backgroundColor;
        elem.style.transition = 'all 0.3s ease';
        elem.style.borderColor = '#10b981';
        elem.style.backgroundColor = '#ecfdf5';
        setTimeout(() => {
            elem.style.borderColor = origBorder;
            elem.style.backgroundColor = origBg;
        }, 1500);
    }

    // إشعار تأكيد التعبئة التلقائية
    function showAutoFillBadge(container, caseNum, count) {
        let badge = container.querySelector('.smart-case-autofill-notification');
        if (!badge) {
            badge = document.createElement('div');
            badge.className = 'smart-case-autofill-notification';
            badge.style.cssText = `
                margin-top: 6px;
                padding: 6px 12px;
                background: #ecfdf5;
                color: #065f46;
                border: 1px solid #a7f3d0;
                border-radius: 6px;
                font-size: 0.82rem;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 8px;
                animation: fadeIn 0.25s ease;
            `;
            const parent = container.querySelector('.smart-case-container') || container;
            parent.parentNode.insertBefore(badge, parent.nextSibling);
        }
        badge.innerHTML = `<i class="fa-solid fa-circle-check" style="color: #10b981;"></i> تم تعبئة بيانات القضية (${caseNum}) تلقائياً في النموذج`;
        badge.style.display = 'flex';
        setTimeout(() => {
            if (badge) badge.style.display = 'none';
        }, 4000);
    }

    // جلب بيانات تفصيلية إضافية للقضية عند اختيارها
    async function fetchCaseDetails(caseId) {
        try {
            const res = await fetch(`/api/case/${caseId}/details`);
            if (res.ok) {
                const data = await res.json();
                return data.case || null;
            }
        } catch (e) {
            console.error('Error fetching case details:', e);
        }
        return null;
    }

    /**
     * بناء وتهيئة المحدد الذكي لعنصر Select أو Input
     */
    window.initSmartCaseSelector = function (elem, options = {}) {
        if (!elem || elem.dataset.smartCaseInit === 'true') return;
        if (isExceptionField(elem)) return;

        elem.dataset.smartCaseInit = 'true';

        const isSelect = elem.tagName.toLowerCase() === 'select';
        let localCases = [];

        // جمع الحالات الأولية من خيارات الـ Select
        if (isSelect) {
            Array.from(elem.options).forEach(opt => {
                if (!opt.value) return;
                const text = opt.textContent.trim();
                const parts = text.split('-');
                let num = parts[0] ? parts[0].trim() : '';
                let title = parts.slice(1).join('-').trim() || text;

                localCases.push({
                    id: opt.value,
                    case_number: num || opt.value,
                    title: title,
                    text: text,
                    case_type_key: opt.getAttribute('data-case-type') || ''
                });
            });
        }

        // إنشاء واجهة المستخدم للبحث والاختيار الذكي
        const wrapper = document.createElement('div');
        wrapper.className = 'smart-case-container';
        wrapper.style.cssText = 'position: relative; width: 100%; font-family: "Cairo", sans-serif;';

        const inputWrap = document.createElement('div');
        inputWrap.style.cssText = 'position: relative; display: flex; align-items: center; width: 100%;';

        const icon = document.createElement('i');
        icon.className = 'fa-solid fa-folder-open';
        icon.style.cssText = 'position: absolute; right: 12px; color: #64748b; font-size: 0.92rem; pointer-events: none; z-index: 2;';

        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'smart-case-search-input';
        searchInput.placeholder = isSelect ? 'اكتب رقم القضية أو اختر من القائمة...' : 'اكتب أو اختر رقم القضية...';
        searchInput.autocomplete = 'off';
        searchInput.style.cssText = `
            width: 100%;
            padding: 9px 38px 9px 62px;
            border: 1.5px solid #cbd5e1;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.88rem;
            background: #ffffff;
            color: #1e293b;
            outline: none;
            box-sizing: border-box;
            transition: border-color 0.2s, box-shadow 0.2s;
        `;

        const buttonsWrap = document.createElement('div');
        buttonsWrap.style.cssText = 'position: absolute; left: 8px; display: flex; align-items: center; gap: 4px; z-index: 2;';

        const clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.title = 'تفريغ الاختيار';
        clearBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
        clearBtn.style.cssText = 'display: none; background: none; border: none; color: #94a3b8; cursor: pointer; padding: 4px 6px; font-size: 0.85rem; border-radius: 4px;';

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.title = 'عرض كافة القضايا';
        toggleBtn.innerHTML = '<i class="fa-solid fa-chevron-down"></i>';
        toggleBtn.style.cssText = 'background: none; border: none; color: #64748b; cursor: pointer; padding: 4px 6px; font-size: 0.85rem; border-radius: 4px;';

        buttonsWrap.appendChild(clearBtn);
        buttonsWrap.appendChild(toggleBtn);

        inputWrap.appendChild(icon);
        inputWrap.appendChild(searchInput);
        inputWrap.appendChild(buttonsWrap);

        // قائمة النتائج المنسدلة
        const dropdownMenu = document.createElement('div');
        dropdownMenu.className = 'smart-case-dropdown-menu';
        dropdownMenu.style.cssText = `
            display: none;
            position: absolute;
            top: calc(100% + 4px);
            right: 0;
            left: 0;
            background: #ffffff;
            border: 1.5px solid #cbd5e1;
            border-radius: 10px;
            max-height: 290px;
            overflow-y: auto;
            z-index: 9999;
            box-shadow: 0 14px 28px -4px rgba(0,0,0,0.15);
        `;

        wrapper.appendChild(inputWrap);
        wrapper.appendChild(dropdownMenu);

        // إدراج المحدد الذكي بدلاً من العنصر الأصلي
        if (isSelect) {
            elem.style.display = 'none';
            elem.parentNode.insertBefore(wrapper, elem.nextSibling);
        } else {
            elem.parentNode.insertBefore(wrapper, elem);
            wrapper.appendChild(inputWrap);
            wrapper.appendChild(dropdownMenu);
            elem.style.display = 'none';
        }

        // ضبط القيمة المبدئية ومزامنة التحديثات البرمجية
        async function updateDisplayFromCurrentValue() {
            let val = elem.value;
            if (val) {
                if (isSelect) {
                    let selOpt = elem.querySelector(`option[value="${val}"]`);
                    if (selOpt && selOpt.value) {
                        searchInput.value = selOpt.textContent.trim();
                        clearBtn.style.display = 'inline-block';
                    } else {
                        // جلب بيانات القضية إذا لم تكن موجودة في الخيارات الأولية
                        const c = await fetchCaseDetails(val);
                        if (c) {
                            const opt = document.createElement('option');
                            opt.value = c.id;
                            opt.textContent = `${c.case_number} - ${c.title}`;
                            elem.appendChild(opt);
                            elem.value = c.id;
                            searchInput.value = `${c.case_number} - ${c.title}`;
                            clearBtn.style.display = 'inline-block';
                        }
                    }
                } else {
                    searchInput.value = val;
                    clearBtn.style.display = 'inline-block';
                }
            } else {
                searchInput.value = '';
                clearBtn.style.display = 'none';
            }
        }
        updateDisplayFromCurrentValue();

        // ربط خاصية value لمزامنة أي تعديل برمجي من الصفحة
        try {
            const proto = isSelect ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
            const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
            if (descriptor && descriptor.set) {
                Object.defineProperty(elem, 'value', {
                    set: function (val) {
                        descriptor.set.call(this, val);
                        updateDisplayFromCurrentValue();
                    },
                    get: function () {
                        return descriptor.get.call(this);
                    },
                    configurable: true
                });
            }
        } catch (e) {
            // تجاهل إن تعذر اعتراض الخاصية
        }
        elem.addEventListener('change', updateDisplayFromCurrentValue);

        const parentForm = elem.closest('form');
        if (parentForm) {
            parentForm.addEventListener('reset', () => {
                setTimeout(updateDisplayFromCurrentValue, 20);
            });
        }

        // مؤقت تأخير الاستعلام للبحث الحي عبر الخادم
        let debounceTimer = null;
        let activeQuery = '';

        // دالة عرض النتائج مرتبة حسب الأقرب لرقم وعنوان البحث
        function renderItems(items, query = '') {
            dropdownMenu.innerHTML = '';
            if (!items || items.length === 0) {
                dropdownMenu.innerHTML = `
                    <div style="padding: 16px; text-align: center; color: #64748b; font-size: 0.88rem;">
                        <i class="fa-solid fa-folder-open" style="font-size: 1.8rem; margin-bottom: 8px; opacity: 0.4; display: block;"></i>
                        لا توجد قضايا مطابقة لرقم البحث "${escapeHtml(query)}"
                    </div>
                `;
                dropdownMenu.style.display = 'block';
                return;
            }

            // ترتيب النتائج بحيث يظهر الرقم الأقرب والأكثر تطابقاً في البداية دائماً
            const sortedItems = [...items].sort((a, b) => {
                return getMatchScore(b, query) - getMatchScore(a, query);
            });

            sortedItems.forEach((item) => {
                const row = document.createElement('div');
                row.className = 'smart-case-item';
                row.style.cssText = `
                    padding: 10px 14px;
                    border-bottom: 1px solid #f1f5f9;
                    cursor: pointer;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    transition: background 0.15s ease;
                `;
                row.onmouseover = () => { row.style.background = '#f0fdf4'; };
                row.onmouseout = () => { row.style.background = '#ffffff'; };

                const numHtml = highlightMatch(item.case_number, query);
                const titleHtml = highlightMatch(item.title, query);
                const clientHtml = item.client_name ? highlightMatch(item.client_name, query) : '';

                row.innerHTML = `
                    <div style="flex: 1; min-width: 0;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 3px;">
                            <span style="background: #1e293b; color: #f8fafc; font-weight: 800; font-family: monospace; font-size: 0.85rem; padding: 2px 8px; border-radius: 6px;">
                                ${numHtml}
                            </span>
                            <span style="font-weight: 700; color: #0f172a; font-size: 0.9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                ${titleHtml}
                            </span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px; font-size: 0.78rem; color: #64748b;">
                            ${clientHtml ? `<span><i class="fa-solid fa-user" style="color: #0d9488;"></i> الموكل: <strong>${clientHtml}</strong></span>` : ''}
                            ${item.court_name ? `<span><i class="fa-solid fa-landmark" style="color: #6366f1;"></i> ${escapeHtml(item.court_name)}</span>` : ''}
                        </div>
                    </div>
                    <div style="margin-right: 10px;">
                        <span style="color: #10b981; font-size: 0.82rem; font-weight: 700; background: #ecfdf5; padding: 4px 8px; border-radius: 6px;">
                            اختيار <i class="fa-solid fa-check"></i>
                        </span>
                    </div>
                `;

                row.onclick = () => {
                    selectCase(item);
                };

                dropdownMenu.appendChild(row);
            });

            dropdownMenu.style.display = 'block';
        }

        // اختيار قضية
        async function selectCase(caseItem) {
            searchInput.value = `${caseItem.case_number} - ${caseItem.title}`;
            clearBtn.style.display = 'inline-block';
            dropdownMenu.style.display = 'none';

            if (isSelect) {
                let existingOpt = elem.querySelector(`option[value="${caseItem.id}"]`);
                if (!existingOpt) {
                    existingOpt = document.createElement('option');
                    existingOpt.value = caseItem.id;
                    existingOpt.textContent = `${caseItem.case_number} - ${caseItem.title}`;
                    elem.appendChild(existingOpt);
                }
                elem.value = caseItem.id;
            } else {
                elem.value = caseItem.case_number || caseItem.id;
            }

            // إطلاق أحداث التغيير
            elem.dispatchEvent(new Event('change', { bubbles: true }));
            elem.dispatchEvent(new Event('input', { bubbles: true }));

            // جلب البيانات التفصيلية وتعبئة باقي حقول النموذج
            let fullDetails = caseItem;
            if (!caseItem.client_name || !caseItem.court_name || !caseItem.lead_lawyer_name) {
                const fetched = await fetchCaseDetails(caseItem.id);
                if (fetched) {
                    fullDetails = Object.assign({}, caseItem, fetched);
                }
            }

            const formContainer = elem.closest('form') || elem.closest('.modal-content') || elem.closest('.card') || document;
            autoFillRelatedFields(formContainer, fullDetails);

            if (options.onSelect) {
                options.onSelect(fullDetails);
            }
        }

        // تفريغ الاختيار
        function clearSelection() {
            searchInput.value = '';
            elem.value = '';
            clearBtn.style.display = 'none';
            elem.dispatchEvent(new Event('change', { bubbles: true }));
            elem.dispatchEvent(new Event('input', { bubbles: true }));
        }

        // البحث السريع محلياً وفي الخادم
        function performSearch(query) {
            activeQuery = query.trim();

            if (!activeQuery) {
                if (localCases.length > 0) {
                    renderItems(localCases);
                } else {
                    fetchRemoteCases('');
                }
                return;
            }

            // 1. التصفية محلياً بالأرقام والحروف مع احتساب قرب النتيجة
            const normQuery = normalizeText(activeQuery);
            const filteredLocal = localCases.filter(c => {
                const normNum = normalizeText(c.case_number);
                const normTitle = normalizeText(c.title);
                const normClient = normalizeText(c.client_name || '');
                return normNum.includes(normQuery) || normTitle.includes(normQuery) || normClient.includes(normQuery);
            });

            renderItems(filteredLocal, activeQuery);

            // 2. استعلام الخادم عبر API (Debounced) للبحث في كامل قاعدة البيانات
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                fetchRemoteCases(activeQuery);
            }, 250);
        }

        async function fetchRemoteCases(q) {
            try {
                const res = await fetch(`/api/cases/search?q=${encodeURIComponent(q)}&limit=25`);
                if (res.ok) {
                    const data = await res.json();
                    const remoteCases = data.cases || [];
                    if (remoteCases.length > 0) {
                        remoteCases.forEach(rc => {
                            if (!localCases.some(lc => String(lc.id) === String(rc.id))) {
                                localCases.push(rc);
                            }
                        });
                        renderItems(remoteCases, q);
                    } else if (!q && localCases.length > 0) {
                        renderItems(localCases, '');
                    }
                }
            } catch (err) {
                console.error('Error fetching cases:', err);
            }
        }

        // أحداث المدخلات
        searchInput.addEventListener('input', (e) => {
            clearBtn.style.display = e.target.value ? 'inline-block' : 'none';
            performSearch(e.target.value);
        });

        searchInput.addEventListener('focus', () => {
            searchInput.style.borderColor = '#2563eb';
            searchInput.style.boxShadow = '0 0 0 3px rgba(37,99,235,0.15)';
            performSearch(searchInput.value);
        });

        searchInput.addEventListener('blur', () => {
            searchInput.style.borderColor = '#cbd5e1';
            searchInput.style.boxShadow = 'none';
        });

        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (dropdownMenu.style.display === 'block') {
                dropdownMenu.style.display = 'none';
            } else {
                searchInput.focus();
                performSearch('');
            }
        });

        clearBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            clearSelection();
            searchInput.focus();
        });

        // إغلاق القائمة عند النقر خارجها
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target)) {
                dropdownMenu.style.display = 'none';
            }
        });
    };

    /**
     * المسح الشامل والتفعيل التلقائي لكافة حقول القضايا في النظام
     */
    window.autoInitAllCaseSelectors = function () {
        // حقول Select الخاصة برقم/معرف القضية
        const caseSelects = document.querySelectorAll(
            'select[name="case_id"], select#fCaseId, select#addCaseSelect, select#form_case_id, select#addPleadingCaseId, select#add_case_id, select#edit_doc_case'
        );

        caseSelects.forEach(sel => {
            if (!isExceptionField(sel)) {
                window.initSmartCaseSelector(sel);
            }
        });

        // حقول Input الخاصة برقم القضية في شاشات التقارير أو الربط (باستثناء إنشاء قضية جديدة)
        const caseInputs = document.querySelectorAll(
            'input#rep_case_number, input#edit_client_case_number'
        );
        caseInputs.forEach(inp => {
            if (!isExceptionField(inp)) {
                window.initSmartCaseSelector(inp);
            }
        });
    };

    // التفعيل عند اكتمال تحميل الصفحة
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.autoInitAllCaseSelectors);
    } else {
        window.autoInitAllCaseSelectors();
    }

    // مراقبة النوافذ المنبثقة (Modals) لتفعيل الحقول فيها فور فتحها
    const modalObserver = new MutationObserver(() => {
        window.autoInitAllCaseSelectors();
    });
    modalObserver.observe(document.body, { childList: true, subtree: true });

})();
