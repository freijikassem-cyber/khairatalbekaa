# 🌿 خيرات البقاع الاخضر — Shop Manager (Django)

نسخة Django من تطبيق إدارة المحل: **Django + Bootstrap RTL + PostgreSQL (Supabase)**.
نفس مزايا نسخة Apps Script بالكامل: منتجات مع صور، فواتير مع بحث/منتقي منتجات،
مخزون وجرد، تقارير (مبيعات/مخزون/حركات/قائمة أسعار/منيو PDF واتساب)، استيراد Excel،
جدول تعديل سريع، سعر صرف قابل للتغيير — مع تسجيل دخول.

## تشغيل محلي
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```
ثم افتح http://127.0.0.1:8000 — بدون DATABASE_URL يستخدم SQLite محلياً.

مستخدم التجربة المحلي الحالي: `kassem` / `khairat2026` (غيّره قبل النشر).

## ربط Supabase (قاعدة البيانات)
1. سجّل الدخول في https://supabase.com/dashboard وأنشئ Project جديد (اختر كلمة مرور قوية للقاعدة).
2. من **Project Settings → Database → Connection string** انسخ سلسلة **Transaction pooler** (منفذ 6543).
3. ضعها في متغير البيئة `DATABASE_URL` (استبدل `[YOUR-PASSWORD]` بكلمة المرور).
4. شغّل `python manage.py migrate` مرة واحدة عليها.

## نشر مجاني (Render)
1. ارفع هذا المجلد إلى مستودع GitHub.
2. في https://render.com: **New → Blueprint** واختر المستودع (يقرأ render.yaml تلقائياً).
3. عبّئ المتغيرات المطلوبة: `DATABASE_URL` (من Supabase)، `DJANGO_SUPERUSER_PASSWORD`،
   و`CSRF_TRUSTED_ORIGINS` = `https://<اسم-التطبيق>.onrender.com`.
4. بعد أول نشر، افتح الرابط وسجّل الدخول.

ملاحظات:
- صور المنتجات تُخزَّن مضغوطة داخل قاعدة البيانات نفسها (لا حاجة لتخزين ملفات).
- لوحة Django Admin على `/admin/` (زر مباشر داخل ⚙️ الإعدادات).
- الخطة المجانية في Render "تنام" بعد الخمول — أول فتح بعد فترة يأخذ ~30 ثانية.
