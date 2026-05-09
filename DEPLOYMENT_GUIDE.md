# دليل إطلاق نظام LawSaaS على السيرفر الفعلي (Production Deployment Guide)

هذا الدليل مخصص لمهندس السيرفرات (DevOps / SysAdmin) لرفع وتشغيل نظام **LawSaaS** المبني على إطار عمل (FastAPI / Python) وقواعد بيانات (PostgreSQL).

---

## 1. المتطلبات الأساسية للسيرفر (Prerequisites)
* **نظام التشغيل:** Ubuntu 22.04 LTS (أو أحدث).
* **بيئة التشغيل:** Python 3.10+ مع `venv`.
* **قاعدة البيانات:** PostgreSQL 14+ (أو استخدام خدمة سحابية مثل Supabase).
* **الخادم الوكيل (Reverse Proxy):** Nginx.
* **إدارة العمليات:** Systemd و Gunicorn.

---

## 2. نقل الملفات وتجهيز البيئة (Setup)

1. قم برفع مجلد المشروع `law_firm1` إلى السيرفر في مسار مثل `/var/www/law_firm1`.
2. ادخل إلى المجلد وقم بإنشاء بيئة بايثون افتراضية:
   ```bash
   cd /var/www/law_firm1
   python3 -m venv venv
   source venv/bin/activate
   ```
3. قم بتثبيت المكتبات اللازمة، وتأكد من تثبيت خادم الإنتاج `gunicorn`:
   ```bash
   pip install -r requirements.txt
   pip install gunicorn uvicorn
   ```

---

## 3. إعداد متغيرات البيئة (.env)
قم بإنشاء ملف `.env` في المسار الرئيسي للمشروع، وضع فيه الإعدادات الإنتاجية لمنع تسريب الأخطاء وتأمين النظام:

```ini
# /var/www/law_firm1/.env
APP_ENV=production
SECRET_KEY=ضع_مفتاح_سري_طويل_ومعقد_هنا
DATABASE_URL=postgresql://user:password@localhost/lawsaas_db
```

---

## 4. إعداد خدمة Gunicorn (Systemd Service)
لكي يعمل النظام بشكل دائم ولا يتوقف عند إغلاق الشاشة الشاشة السوداء (Terminal)، يجب إنشاء خدمة (Service) في نظام تشغيل السيرفر.

1. قم بإنشاء ملف الخدمة:
   ```bash
   sudo nano /etc/systemd/system/lawsaas.service
   ```
2. ضع فيه الكود التالي (تأكد من تعديل المسارات حسب سيرفرك):
   ```ini
   [Unit]
   Description=Gunicorn instance to serve LawSaaS
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/law_firm1
   Environment="PATH=/var/www/law_firm1/venv/bin"
   # تشغيل النظام بـ 4 عمال (Workers) لتحمل الضغط
   ExecStart=/var/www/law_firm1/venv/bin/gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000

   [Install]
   WantedBy=multi-user.target
   ```
3. قم بتفعيل وتشغيل الخدمة:
   ```bash
   sudo systemctl start lawsaas
   sudo systemctl enable lawsaas
   ```

---

## 5. إعداد Nginx (الخادم الوكيل والـ SSL)
النظام يعمل الآن داخلياً على المنفذ `8000`. سنقوم بإعداد `Nginx` لاستقبال طلبات الإنترنت من الدومين وتوجيهها للنظام مع تفعيل الأمان.

1. قم بإنشاء ملف إعدادات Nginx:
   ```bash
   sudo nano /etc/nginx/sites-available/lawsaas
   ```
2. ضع فيه الإعداد التالي (استبدل `your-domain.com` برابط موقعك الفعلي):
   ```nginx
   server {
       listen 80;
       server_name your-domain.com www.your-domain.com;

       # زيادة الحد الأقصى لرفع الملفات (للمستندات القانونية)
       client_max_body_size 50M;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       # مسار الملفات الثابتة (CSS, JS, Images, Uploads) لتسريع الأداء
       location /static/ {
           alias /var/www/law_firm1/static/;
           expires 30d;
           add_header Cache-Control "public, max-age=2592000";
       }
   }
   ```
3. قم بتفعيل الإعداد وإعادة تشغيل Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/lawsaas /etc/nginx/sites-enabled
   sudo nginx -t
   sudo systemctl restart nginx
   ```

---

## 6. تفعيل شهادة الأمان (HTTPS / Let's Encrypt)
لحماية الجلسات وكلمات المرور، يجب تفعيل القفل الأخضر (SSL) باستخدام `Certbot`:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

---

## 7. إعطاء الصلاحيات لملفات الرفع (Uploads Permission)
نظامنا يقوم بحفظ المستندات في مجلد `static/uploads`. يجب إعطاء السيرفر صلاحية الكتابة داخله لتجنب خطأ `500 Permission Denied` عند رفع المحامين للمستندات:
```bash
sudo chown -R www-data:www-data /var/www/law_firm1/static/uploads
sudo chmod -R 755 /var/www/law_firm1/static/uploads
```

**الآن نظام LawSaaS يعمل باحترافية، محمي بشهادة SSL، ويتحمل ضغط المكاتب والمحامين! 🎉**
