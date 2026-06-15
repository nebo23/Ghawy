# Ghawy Project Audit Report

## 🔴 Critical Issues (لازم تتحل قبل Launch)

- [ ] **Issue 1: Unprotected Critical Endpoints (Security)**
  - **الملف:** `backend/main.py`
  - **السطر:** 494, 503 (`delete_user`, `delete_payment`)
  - **وصف المشكلة:** الـ endpoints دي مش بتستخدم `Depends(get_current_admin_user)` أو أي نوع من الـ authentication. أي حد يقدر يبعت Request ويمسح أي User أو Payment من غير ما يكون Admin.
  - **الحل المقترح:** إضافة `current_user: User = Depends(get_current_admin_user)` للـ function parameters لحمايتها.

- [ ] **Issue 2: Kashier Webhook Signature Bypass (Payment Security)**
  - **الملف:** `backend/app/routers/webhooks.py`
  - **السطر:** 39-40
  - **وصف المشكلة:** الـ code بيعمل verify للـ Kashier signature، بس لو الـ verification فشل بيعمل `logger.warning` وبيكمل الـ execution عادي ويفعل الاشتراك! ده معناه إن أي حد ممكن يعمل payment confirmation مزيف لنفسه.
  - **الحل المقترح:** إضافة `raise HTTPException(status_code=400, detail="Invalid signature")` لو الـ signature مش مطابق، عشان نـ block الـ request فوراً.

- [ ] **Issue 3: Missing .env from .gitignore (Sensitive Data)**
  - **الملف:** `.gitignore`
  - **وصف المشكلة:** ملف الـ `.env` مش موجود في الـ `.gitignore`، وده بيعرض الـ Secrets والـ API Keys إنها تتعمل لها Commit بالغلط على GitHub.
  - **الحل المقترح:** إضافة `.env` لملف الـ `.gitignore`.

- [ ] **Issue 4: Broken Alembic Migration Tree (Data Integrity)**
  - **الملف:** `backend/alembic/`
  - **وصف المشكلة:** تشغيل `alembic check` بيطلع error `Can't locate revision identified by '8f370e02e750'`. شجرة الـ migrations مكسورة، وده هيمنع تطبيق الـ migrations الجديدة في المستقبل أو في الـ production.
  - **الحل المقترح:** مراجعة مجلد `alembic/versions` وإصلاح الـ `down_revision` المكسور أو مسح الـ version اللي مش موجود من الـ database `alembic_version` table.

## 🟡 Important Issues (مهمة بس مش blocking)

- [ ] **Issue 1: N+1 Query Problems (Performance)**
  - **الملف:** `backend/app/routers/` (أكثر من ملف زي `courses.py`, `chat.py`, `ws.py`, `live.py`)
  - **وصف المشكلة:** الـ endpoints بتستخدم `.all()` لعمل fetch لـ data كبيرة زي الـ courses و users، ولما بيتم الوصول لـ relationships بعدها بيعمل N+1 queries.
  - **الحل المقترح:** استخدام `joinedload` للـ relationships اللي هتحتاجها، وإضافة pagination (limit/offset) على الـ queries اللي ممكن ترجع داتا كبيرة جداً.

- [ ] **Issue 2: Native window.alert & window.confirm (UX/Consistency)**
  - **الملف:** `frontend/src/js/onboarding.js`, `team.js`, `course-detail.html`, وغيرها.
  - **وصف المشكلة:** استخدام `window.alert` و `window.confirm` في أماكن كتير جداً في الـ Frontend، وده بيخالف قاعدة المشروع الثابتة (لا window.alert أو window.confirm — المفروض showToast).
  - **الحل المقترح:** استبدال كل الـ native alerts بـ `showToast` والـ custom confirmation modals.

- [ ] **Issue 3: Production CORS Configuration (Deployment Readiness)**
  - **الملف:** `backend/main.py`
  - **السطر:** 447
  - **وصف المشكلة:** الـ CORS مضبوط فقط على `localhost:5500` و `127.0.0.1:5500`. في الـ production الـ Frontend مش هيقدر يكلم الـ Backend.
  - **الحل المقترح:** قراءة الـ `allow_origins` من الـ `.env` عشان يدعم الـ production domain.

## 🟢 Minor Issues (تحسينات)

- [ ] **Issue 1: استخدام لون ممنوع (#84cc16) (Consistency)**
  - **الملف:** `goh.css`, `team.css`, `dashboard.css`, `team.js`
  - **وصف المشكلة:** اللون `#84cc16` مستخدم كـ hardcoded color في أكثر من 15 مكان في الـ CSS والـ JS، بالرغم من إن قواعد المشروع بتنص على استخدام `#3f8ff9` فقط ومنع `#84cc16`.
  - **الحل المقترح:** عمل Find & Replace وتغيير كل `#84cc16` إلى `#3f8ff9`.

- [ ] **Issue 2: Skeleton Loading & Empty States (UX)**
  - **الملف:** أغلب الـ JS files
  - **وصف المشكلة:** بعض القوائم في الـ Frontend بتعمل render للبيانات من غير Skeleton loading في الأول، ومش بتعرض Empty state واضح لو القائمة فاضية (قاعدة ثابتة في المشروع).
  - **الحل المقترح:** مراجعة دوال الـ `renderLists` وإضافة Skeleton UI قبل الـ Fetch و Empty UI لو الـ response فاضي.

## ✅ What's Working Well
- **API Structure:** الـ FastAPI routers متقسمة بشكل ممتاز جداً ومنظم.
- **Auto Migrations (SQLite fallback):** فكرة الـ `apply_sqlite_compat_migrations` لحل مشاكل SQLite ممتازة وبتخلي التطوير المحلي سريع.
- **Seeding:** دالة `seed_defaults` بتضمن إن الـ Database دايماً جاهزة للاستخدام من غير Setup معقد.
- **Modular Services:** فصل الـ logic لـ `services` (زي `kashier_manager.py`) بيخلي الكود أنظف.

## 📊 Summary
- Critical: 4 issues
- Important: 3 issues  
- Minor: 2 issues
- Estimated fix time: 3-5 hours
