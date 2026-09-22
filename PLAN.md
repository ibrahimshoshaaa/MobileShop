# خطة تطوير MobileShop من الوضع الحالي إلى v1.0

> ✅ = تم التنفيذ · ⬜ = لم يبدأ بعد

---

## المرحلة 1 — إنهاء الموبايل كمنتج حقيقي

### 1.1 شاشة التقارير ✅

- [x] إنشاء Module جديد للتقارير (`lib/features/reports/`).
- [x] قراءة البيانات من:
  - [x] Sales Repository
  - [x] Expenses Repository
  - [x] Maintenance Repository
  - [x] Inventory Repository
- [x] إنشاء Date Filter (اليوم / آخر 7 أيام / هذا الشهر / مخصص).
- [x] إنشاء KPIs Cards (صافي الربح، المبيعات، المصروفات، الصيانة، قيمة المخزون، أصناف ناقصة).

**ملاحظة مهمة:** ربح المبيعات في التقرير **تقديري** حاليًا — بيتحسب على تكلفة الصنف *الحالية* من المخزون، مش التكلفة وقت البيع الفعلي، لأن `SaleItemRecord` لسه مفيهوش `costAtSale` (ده موضوع البند 1.4 اللي جاي). لحد ما 1.4 يتنفذ، الرقم ده تقريبي مش نهائي، وده موضّح في الشاشة نفسها بأيقونة معلومة (ⓘ) على الكارت.

**النتيجة:** ✔ صاحب المحل يعرف أرباحه وخسائره (بشكل تقديري حتى تمام 1.4).

---

### 1.2 صفحة الإعدادات ⬜

- [ ] حذف أي Buttons وهمية.
- [ ] إنشاء Export Backup.
- [ ] إنشاء Import Backup.
- [ ] إنشاء About Page.
- [ ] إنشاء قسم Cloud Account.

**المطلوب:** تحديد هل النسخ الاحتياطي SQLite أم JSON.

**النتيجة المتوقعة:** ✔ المستخدم يستطيع حفظ بياناته واستعادتها.

---

### 1.3 مراجعة التطبيق بالكامل ⬜

- [ ] مراجعة: Inventory / Sales / Customers / Suppliers / Installments / Maintenance / Wallets.
- [ ] إزالة أي TODO / Placeholder / Empty Button.
- [ ] تشغيل `flutter analyze`.
- [ ] تشغيل التطبيق وتجربة كل شاشة.

**النتيجة المتوقعة:** ✔ تطبيق نظيف ومستقر.

---

### 1.4 costAtSale ⬜

- [ ] إضافة `costAtSale` داخل `SaleItemRecord`.
- [ ] Migration للبيانات القديمة.

**النتيجة المتوقعة:** ✔ أرباح دقيقة تاريخيًا (وتقرير 1.1 هيبقى دقيق 100% بدل تقديري).

---

## المرحلة 2 — توحيد البيانات مع الباك إند

### 2.1 Wallet Refactor ⬜

- [ ] تحويل `enum WalletId` إلى شكل `{id, name, wallet_type, branch_id}`.

**المطلوب:** مراجعة موديل Wallet في الباك إند.

**النتيجة المتوقعة:** ✔ نفس شكل البيانات في الموبايل والسيرفر.

---

## المرحلة 3 — ربط الحساب السحابي

### 3.1 Desktop Login ⬜
- [ ] شاشة Login + استدعاء API + حفظ tenant_id/account_id/branch_ids.

### 3.2 Mobile Login ⬜
- [ ] شاشة Login + حفظ بيانات الحساب + مؤشر Online/Offline.

**النتيجة المتوقعة:** ✔ الديسكتوب والموبايل متصلين بالسيرفر.

---

## المرحلة 4 — أول اتصال فعلي بالمزامنة

- [ ] 4.1 إنشاء API Client (`api_client.dart`).
- [ ] 4.2 قراءة البيانات (Inventory / Customers / Suppliers / Wallets) من السيرفر.
- [ ] 4.3 رفع البيانات (Sales / Expenses / Maintenance / Installments) للسيرفر.

---

## المرحلة 5 — Sync Engine

- [ ] 5.1 Upload Queue (Outbox + Retry + Failure Handling).
- [ ] 5.2 Download Queue (Cursor Tracking + Changes Fetching).
- [ ] 5.3 Sync Dashboard (Pending Commands / Last Sync / Sync Errors / Conflict Count).

---

## المرحلة 6 — اختبار الأجهزة المتعددة ⬜

- [ ] سيناريو 1: بيع من الديسكتوب يظهر في الموبايل.
- [ ] سيناريو 2: عميل جديد من الموبايل يظهر في الديسكتوب.
- [ ] سيناريو 3: جهازين يعدلان نفس المنتج (تحديد سياسة حل التعارضات).

---

## المرحلة 7 — المستخدمون والصلاحيات ⬜

- [ ] إدارة Users / Roles / Permissions / Branch Access.

---

## المرحلة 8 — الإنتاج ⬜

- [ ] اختبار Backup / Restore / Recovery / Stress Testing / Multi Device Testing.

---

## المرحلة 9 — النسخة النهائية ⬜

- [ ] ربط Barcode Scanner / IMEI Scanner / Receipt Printer.
- [ ] إصدار v1.0.0.

---

## ملفات تم إنشاؤها أو تعديلها لتنفيذ 1.1

**ملفات جديدة:**
- `apps/admin_mobile/lib/features/reports/reports_models.dart`
- `apps/admin_mobile/lib/features/reports/reports_repository.dart`
- `apps/admin_mobile/lib/features/reports/reports_provider.dart`
- `apps/admin_mobile/lib/features/reports/reports_page.dart`

**ملفات معدّلة:**
- `apps/admin_mobile/lib/main.dart` — ربط شاشة `ReportsPage` الحقيقية بدل الـ placeholder في index 8.
- `apps/admin_mobile/lib/features/sales/sale_repository.dart` — إضافة `listSalesInRange` للـ interface والتنفيذ في `InMemorySalesRepository`.
- `apps/admin_mobile/lib/features/sales/sqlite_sale_repository.dart` — تنفيذ `listSalesInRange` في `SqliteSalesRepository`.
- `apps/admin_mobile/lib/features/home/home_page.dart` — تصحيحات `const` (من مهمة `flutter analyze` السابقة).

> ⚠️ تنويه: البيئة اللي بشتغل بيها مفيهاش Flutter SDK ولا اتصال إنترنت، فمقدرتش أشغّل `flutter analyze` أو `flutter run` فعليًا على الكود ده. راجعته بعناية يدويًا، بس الخطوة الطبيعية قبل الدمج إنك تشغّل `flutter pub get && flutter analyze` عندك للتأكد.
