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

### 1.2 صفحة الإعدادات ✅

- [x] حذف أي Buttons وهمية (شيلنا الـ `SwitchListTile` والـ `ListTile`s اللي مالهاش أي `onTap` فعلي من `main.dart`).
- [x] إنشاء Export Backup.
- [x] إنشاء Import Backup.
- [x] إنشاء About Page.
- [x] إنشاء قسم Cloud Account (Informational فقط — مش Login فعلي، لأن ده موضوع 3.2).

**القرار:** النسخ الاحتياطي **JSON** مش SQLite خام. السبب: جدول `records` في `LocalStore` أصلاً generic (`entity/record_id/payload/version`) بيغطي كل الكيانات، فـ JSON dump ليه بيبقى نسخة كاملة وكافية بدون أي هيكل علائقي تاني تحتاج تتحفظ. JSON كمان قابل للقراءة/الفحص، وميعتمدش على توافق نسخة sqflite/SQLite بين جهازين زي ما ممكن يحصل لو نسخنا ملف `.db` خام، وشكله قريب من شكل البيانات اللي بروتوكول المزامنة (مرحلة 4/5) هيحتاجه أصلاً (record + version).

**اللي اتعمل فعليًا:**
- Export: بيجمع كل الـ records من `LocalStore` في ملف `.json` (في `backups/` جوه Documents directory)، وبيفتح مباشرة Share Sheet (`share_plus`) عشان المستخدم يحفظه فين ما هو عايز (Drive، ملفات، واتساب...).
- Import: بيفتح File Picker (`file_picker`) لاختيار ملف `.json`، بيتحقق إن الملف صالح، بيوريه Dialog تأكيد إنه هيستبدل كل البيانات الحالية (مفيش رجوع بعد كده)، وبعد الاستيراد بيقوله يعيد فتح التطبيق عشان كل الشاشات تحمّل البيانات المستعادة من جديد.
- About Page: اسم التطبيق، رقم الإصدار (يدوي دلوقتي، لازم يتزوّد بيه لما `pubspec.yaml` يتغير)، طريقة تخزين البيانات (SQLite محلي)، ووضع الاتصال (Offline).
- Cloud Account: كارت معلوماتي بس (مش زرار وهمي) — بيوضح إن الميزة قيد التطوير ولسه مفعّلتش، وده بيتماشى مع إن الـ Login الفعلي (3.2) لسه ما اتعملش.

**Dependencies جديدة في `pubspec.yaml`:** `path_provider`, `file_picker`, `share_plus` — لازم `flutter pub get` قبل التشغيل.

**النتيجة:** ✔ المستخدم يستطيع حفظ بياناته واستعادتها، وصفحة الإعدادات بقت حقيقية 100% من غير أي زرار وهمي.

---

### 1.3 مراجعة التطبيق بالكامل ✅

- [x] مراجعة: Inventory / Sales / Customers / Suppliers / Installments / Maintenance / Wallets.
- [x] إزالة أي TODO / Placeholder / Empty Button.
- [ ] تشغيل `flutter analyze` — **مقدرش فعليًا** (نفس القيد اللي في 1.1 و1.2: مفيش Flutter SDK ولا إنترنت في البيئة دي). عملت مراجعة يدوية بدلها (تفاصيل تحت).
- [ ] تشغيل التطبيق وتجربة كل شاشة — **مقدرش فعليًا** لنفس السبب. راجعت الكود بدل التشغيل الفعلي.

**اللي اتعمل فعليًا (مراجعة يدوية شاملة):**
- عملت `grep` على كل المشروع (12 ملف صفحة/feature) على أي `TODO` / `FIXME` / `Placeholder` / `onPressed: () {}` / `onTap: () {}` / نصوص زي "قريبًا"/"dummy"/"fake"/`print(`. النتيجة: 3 أماكن فعلية فيها فرق بين الشكل والمضمون، كلهم في `main.dart` (باقي الـ 8 modules – Inventory/Sales/Customers/Suppliers/Installments/Maintenance/Wallets/Expenses – كل زرار فيهم متوصل فعليًا بمنطق حقيقي، مفيش زرار وهمي فيهم أصلاً):
  1. زرار "Sync" في الـ AppBar (كل الشاشات غير الرئيسية) — كان `onPressed: () {}`. اتشال، لأن المزامنة الفعلية لسه ماتعملتش (مرحلة 4/5)، وزرار بيتظاهر إنه بيزامن وهو مش بيعمل حاجة ده بالظبط نوع الـ "Empty Button" المطلوب نشيله.
  2. زرار "Notifications" في نفس الـ AppBar — نفس الموضوع، اتشال لحد ما يبقى فيه نظام إشعارات حقيقي.
  3. زرار "إضافة جديد" في `GenericPage` (شاشة "الفروع والمستخدمون"، مرحلة 7 مستقبلًا) — كان `onPressed: () {}` وتحته نص بيقول "هذه الوحدة جاهزة للربط بطبقة البيانات" وهو كلام مش دقيق لحد دلوقتي. استبدلته بنص صريح إنها "قيد التطوير" من غير أي زرار.
- راجعت كل الـ Repository providers (`get*Repository()` في كل feature) وأكدت إنهم كلهم متوصلين فعليًا بـ Sqlite Repository الحقيقي (مش In-Memory)، والـ In-Memory implementations الموجودة متسيبة عمدًا للاختبارات فقط (`resetXRepositoryForTesting`)، مش كود ميت.
- عملت فحص توازن الأقواس `{}`/`()` على كل ملفات `lib/**/*.dart` (سكريبت Python) للتأكد من عدم وجود أخطاء syntax واضحة بعد التعديلات، بالإضافة لفحص الـ imports غير المستخدمة يدويًا.

**النتيجة:** ✔ تطبيق نظيف من أي Placeholder/Empty Button معروف. الاستقرار الكامل (تشغيل فعلي + `flutter analyze`) محتاج تتأكد منه أنت بتشغيل:
```
cd apps/admin_mobile
flutter pub get
flutter analyze
flutter run
```
خصوصًا إن 1.2 ضايف 3 مكتبات جديدة (`path_provider`, `file_picker`, `share_plus`) لازم تتحمّل، وإن ده أول تشغيل فعلي للكود من أساسه في البيئة دي.

---

### 1.4 costAtSale ✅

- [x] إضافة `costAtSale` داخل `SaleItemRecord`.
- [x] Migration للبيانات القديمة.

**اللي اتعمل فعليًا:**
- `SaleItemRecord` بقى فيه حقلين جداد: `costAtSale` (تكلفة الصنف وقت البيع فعليًا) و`costIsEstimated` (`false` لأي بيع جديد من دلوقتي، و`true` بس للبيانات القديمة اللي اتعملها Migration).
- `SqliteSalesRepository.createSale` بقى بياخد تكلفة كل صنف من نفس الاستعلام اللي أصلًا بيتحقق بيه من توفر الكمية (`_inventory.listProducts()`) لحظة إتمام البيع، ويحفظها جوه الفاتورة — يعني التكلفة بقت Snapshot حقيقي وقت البيع، مش قيمة بتتقرأ من المخزون الحالي وقت عمل التقرير زي ما كان بيحصل قبل كده.
- **Migration** (`_migrateLegacyCostAtSale`, بتتنفذ تلقائيًا مرة واحدة كل ما `SqliteSalesRepository.create()` بيتنادى): بتدور على أي فاتورة قديمة (اتعملت قبل 1.4) وبنودها لسه ملهاش `cost_at_sale`، وبتملأها بتكلفة الصنف *الحالية وقت الـ Migration* (أحسن تقدير متاح، لأن التكلفة الحقيقية وقت البيع القديم مش متسجلة)، وبتحطلها Flag `cost_is_estimated: true`. المهم إن ده بيحصل *مرة واحدة* ويتكتب على الـ DB، مش بيتحسب من جديد كل مرة — يعني لو تكلفة الصنف اتغيرت بعد كده، تقرير فترة قديمة مش هيتغير معاها.
- **التقارير (1.1)** بقت بتاخد `estimatedCogs` من `item.lineCost` (= `costAtSale × quantity`) بدل ما تجيب تكلفة المنتج الحالية، فبقت **دقيقة 100%** لأي بيع بعد 1.4. `ReportSummary` بقى فيه حقل جديد `hasEstimatedCosts` بيبقى `true` بس لو فيه فاتورة قديمة اتعملها Migration داخلة في الفترة المختارة — وشاشة التقارير بتستخدمه عشان تفرق بين "ربح المبيعات" (لما كل حاجة دقيقة) و"ربح المبيعات (تقديري جزئيًا)" (لما لسه فيه فواتير قديمة مش دقيقة 100%)، بدل ما تقول "تقديري" على طول زي الأول.

**النتيجة:** ✔ أرباح دقيقة تاريخيًا لأي بيع جديد، وتقرير 1.1 بقى دقيق 100% تلقائيًا كل ما البيانات القديمة تتغطي بمرور الوقت (بيع جديد = دقيق دايمًا). المرحلة 1 خلصت بالكامل (1.1 → 1.4 كلهم ✅).

---

## المرحلة 2 — توحيد البيانات مع الباك إند

### 2.1 Wallet Refactor ✅

- [x] تحويل `enum WalletId` إلى شكل `{id, name, wallet_type, branch_id}`.

**اللي اتعمل فعليًا:**
- `WalletId` (enum قديم بقيمتين ثابتتين `cash`/`wallet`) اتشال، ومكانه كلاس `Wallet` (`immutable`) بنفس شكل موديل الباك إند (`shared/models/erp.py`): `id`, `branchId`, `name`, `walletType`, `active`. الـ `branchId` بياخد قيمته من `LocalStore.defaultBranchId` نفسه المستخدم في باقي الكيانات.
- `wireValue` (اللي بيربط `PaymentMethod.CASH/WALLET` بمحفظته) بقى getter على `Wallet` بيرجّع `walletType` — نفس الفكرة القديمة بالظبط، غير إن مفيش enum ثابت دلوقتي.
- كلاس جديد `BuiltinWallets` فيه الاتنين محفظة اللي التطبيق بيشتغل بيهم دلوقتي (`cash`, `wallet`) كـ `const Wallet` objects، بالإضافة لـ helpers: `all`, `byId(id)`, `fromWireValue(value)`, `tryFromWireValue(value)` — بنفس سلوك الـ static methods القديمة على `WalletIdX` بالظبط، بس بترجع `Wallet` بدل enum value.
- `WalletTransaction.walletId` بقى `String` (يحمل `Wallet.id`) بدل `WalletId` enum، عشان الـ interface يقدر يتوسع لمحافظ تانية غير الاتنين built-in لما الـ sync يجيب المحافظ الحقيقية من السيرفر (مرحلة 4/5) من غير ما يتغير تاني.
- `WalletRepository` (والتنفيذ `SqliteWalletRepository`): كل الـ methods (`getBalances`, `listTransactions`, `deposit`, `withdraw`, `postAuto`) بقت بتاخد/بترجع `String walletId` / `Map<String, double>` بدل `WalletId`.
- الأماكن اللي كانت بتنادي `WalletIdX.tryFromWireValue(...)` (expenses/maintenance/sales repositories) اتحدثت لـ `BuiltinWallets.tryFromWireValue(...)?.id`.
- `wallets_page.dart` و`home_page.dart`: كل استخدام لـ `WalletId.cash`/`WalletId.wallet`/`WalletId.values` اتبدل بـ `BuiltinWallets.cash`/`BuiltinWallets.wallet`/`BuiltinWallets.all`، والـ UI (بطاقات الرصيد، الـ `SegmentedButton`) بقت بتلف على `BuiltinWallets.all` بدل الـ enum.
- اتعمل فحص شامل (`grep`) على المشروع كله للتأكد إن مفيش أي استخدام متبقي لـ `WalletId` في الكود (الاسم موجود بس في تعليقات توضيحية بتشرح إيه اللي اتغيّر)، وفحص توازن الأقواس على كل ملف اتعدّل.

**ملفات معدّلة:**
- `apps/admin_mobile/lib/features/wallets/wallet_models.dart` — `Wallet` + `BuiltinWallets` بدل `WalletId` enum.
- `apps/admin_mobile/lib/features/wallets/wallet_repository.dart` — الـ interface بقى `String walletId`.
- `apps/admin_mobile/lib/features/wallets/sqlite_wallet_repository.dart` — التنفيذ بقى `String walletId`.
- `apps/admin_mobile/lib/features/wallets/wallets_page.dart` — الـ UI بيلف على `BuiltinWallets.all`.
- `apps/admin_mobile/lib/features/expenses/sqlite_expense_repository.dart`, `apps/admin_mobile/lib/features/maintenance/sqlite_maintenance_repository.dart`, `apps/admin_mobile/lib/features/sales/sqlite_sale_repository.dart` — `BuiltinWallets.tryFromWireValue(...)?.id` بدل `WalletIdX.tryFromWireValue(...)`.
- `apps/admin_mobile/lib/features/home/home_page.dart` — `balances[BuiltinWallets.cash.id]`/`balances[BuiltinWallets.wallet.id]` بدل `WalletId.cash`/`WalletId.wallet`.

> ⚠️ نفس تنويه المرحلة 1: مفيش Flutter SDK ولا إنترنت في البيئة دي، فمقدرتش أشغّل `flutter pub get`/`flutter analyze`/`flutter run` فعليًا. عملت مراجعة يدوية كاملة (grep على كل استخدامات `WalletId` القديمة، فحص توازن الأقواس على كل ملف اتعدّل) بدل التشغيل الفعلي. لازم تتأكد بـ:
> ```
> cd apps/admin_mobile
> flutter pub get
> flutter analyze
> flutter run
> ```

**ملاحظة للمستقبل:** الريفاكتور ده بيوحّد *الشكل* بس (client-side) — لسه مفيش اتصال فعلي بالباك إند لقراءة/كتابة المحافظ (ده موضوع مرحلة 4). فلسه المحافظ في الموبايل محدودة بالاتنين built-in (`cash`/`wallet`)؛ أي محفظة إضافية هتتضاف فعليًا لما الـ sync يجيب قائمة المحافظ الحقيقية من الباك إند.

**النتيجة:** ✔ نفس شكل البيانات في الموبايل والسيرفر (`{id, branch_id, name, wallet_type, active}`)، والكود بقى جاهز يستقبل محافظ حقيقية من السيرفر من غير ما يحتاج تغيير في الـ interface. **المرحلة 2 خلصت (2.1 ✅ — وهي كانت البند الوحيد فيها).**

---

## المرحلة 3 — ربط الحساب السحابي

### 3.2 Mobile Login ✅
- [x] شاشة Login + حفظ بيانات الحساب + مؤشر Online/Offline.

**النتيجة المتوقعة:** ✔ الموبايل متصل بالسيرفر.

---

## المرحلة 4 — أول اتصال فعلي بالمزامنة

### 4.1 إنشاء API Client ✅

- [x] إنشاء `api_client.dart`.

**اللي اتعمل فعليًا:**
- ملف جديد `apps/admin_mobile/lib/features/sync/api_client.dart` — نظير `apps/desktop/api_client.py` في الموبايل، بنفس فلسفته (مفيش أي مكتبة HTTP خارجية، استخدام `dart:io HttpClient` القياسي بنفس أسلوب `AuthService._get`/`_post` الموجود أصلاً في 3.2).
- كلاس `ApiClient` بياخد `baseUrl` / `token` / `branchId`، وفيه factory `ApiClient.fromSession(session)` بيبنيه مباشرة من الجلسة اللي `AuthService.instance.currentSession` بترجعها بعد تسجيل الدخول — يعني مفيش تكرار لمنطق حفظ التوكن أو الجلسة، ده لسه مسؤولية `AuthService` بس.
- **قراءة:** `getEntity(entity)` عام لأي كيان من اللي السيرفر بيوفرها في `/query/{entity}` (products/customers/suppliers/sales/wallets/... إلخ)، بالإضافة لـ helpers مباشرة (`getProducts`, `getCustomers`, `getSuppliers`, `getWallets`)، و`getSales()` (نقطة `/sales` المخصصة)، و`getReports(start, end)` (نقطة `/reports`).
- **كتابة:** `command(commandId, commandName, payload)` بينادي `POST /command` بنفس شكل envelope اللي `backend/functions/api/http.py` بيتوقعه، و`syncUpload(commands)` و`syncChanges(cursor, limit)` بينادوا `/sync/upload` و`/sync/changes` — الاتنين دول لسه مش متصلين بأي حاجة، ومحضّرين بس عشان طابور الرفع (5.1) وطابور التنزيل (5.2) يستخدموهم زي ما هما.
- **معالجة الأخطاء:** كل استجابة بتتفك عبر `_unwrap()` واحدة بتقرا شكل `{"ok": true, "data": ...}` / `{"ok": false, "error": {code, message}}` اللي `backend/api_server/main.py` بيرجعه دايمًا، وبترمي `ApiException` (فيها `message` جاهز للعرض بالعربي و`code` لو الطالب عايز يتصرف بناءً عليه زي `BRANCH_ACCESS_DENIED`/`FORBIDDEN`). الفرق عن `AuthException` في 3.2: 401 هنا معناها إن التوكن المحفوظ بقى غير صالح (مش خطأ بيانات دخول)، فرسالته مختلفة عمدًا.
- اتعمل فحص توازن الأقواس على الملف الجديد، وتتبع كل الـ endpoints مقابل الموجود فعليًا في `backend/api_server/main.py` (`/query/{entity}`, `/sales`, `/reports`, `/command`, `/sync/upload`, `/sync/changes`) للتأكد إن الشكل مطابق تمامًا (query params، أسماء الحقول، الـ envelope).

**ملفات جديدة:**
- `apps/admin_mobile/lib/features/sync/api_client.dart`

> ⚠️ نفس التنويه المتكرر: مفيش Flutter SDK ولا إنترنت في البيئة دي، فمقدرتش أشغّل `flutter analyze` فعليًا على الملف الجديد ولا أعمل طلب حقيقي على السيرفر. عملت مراجعة يدوية (توازن الأقواس، مطابقة كل endpoint وshape بالكود مقابل `backend/api_server/main.py` سطر سطر) بدل التشغيل الفعلي. الملف لسه **مش مستخدم من أي حاجة تانية في التطبيق** — 4.2 هو اللي هيوصّله فعليًا بالـ Repositories عشان القراءة تبقى من السيرفر.

**النتيجة:** ✔ في مكان واحد بيعرف يكلم `backend/api_server` بكل أشكاله (قراءة/كتابة/مزامنة)، جاهز يتستخدم من 4.2 و4.3 من غير ما يحتاج أي تعديل في شكله.

---

### 4.2 قراءة البيانات (Inventory / Customers / Suppliers / Wallets) من السيرفر ✅

- [x] Inventory — القراءة من `GET /query/products`.
- [x] Customers — القراءة من `GET /query/customers`.
- [x] Suppliers — القراءة من `GET /query/suppliers`.
- [x] Wallets — الأرصدة والحركات من `GET /query/ledger`.

**القرار الأهم في الخطوة دي:** الكتابة (إضافة/تعديل صنف، عميل، مورد، إيداع/سحب محفظة) **لسه محلية دايمًا** — مش جزء من 4.2 ولا 4.3 (اللي بيتحدد فيها الكتابة أونلاين هي Sales/Expenses/Maintenance/Installments بس). السبب الأهم: `WalletRepository.postAuto` بتتنادى داخليًا من `SqliteSalesRepository`/`SqliteExpenseRepository`/`SqliteMaintenanceRepository` لحظة إتمام أي عملية بيع/مصروف/صيانة محليًا — لو استبدلنا `getWalletRepository()` بنسخة أونلاين بيانها للقراءة بس، كل عملية بيع كانت هتفشل فورًا لحظة محاولة تسجيل حركة المحفظة. الحل: كل Repository أونلاين (`ApiXRepository`) بيولّي القراءة للسيرفر، لكن بيوكّل كل عمليات الكتابة لنفس الـ `SqliteXRepository` المحلي القديم من غير أي تغيير في سلوكه.

**اللي اتعمل فعليًا:**
- 4 كلاسات جديدة `ApiInventoryRepository` / `ApiCustomerRepository` / `ApiSupplierRepository` / `ApiWalletRepository`، كل واحد `implements` الـ Repository interface بتاعه بالظبط، بياخد `ApiClient` + الـ Repository المحلي (`SqliteXRepository`) في الـ constructor.
  - **Inventory**: `listProducts()` بتجيب `GET /query/products` (حد أقصى 500)، بتحوّل كل صف لـ `Product` (`product_type` عبر `ProductTypeX.fromWireValue`, الأرقام بـ `double.tryParse` لأن السيرفر بيرجعها كـ string لأنها `Decimal`)، وبتفلتر بالنوع/البحث محليًا زي ما كان بيحصل قبل كده. `addProduct`/`updateProduct`/`adjustStock` بتتوكل للـ Repository المحلي.
  - **Customers**: نفس الفكرة مع `GET /query/customers`. مفيش endpoint لعميل واحد على السيرفر، فـ `getCustomer(id)` بتجيب القائمة وتدور فيها بدل ما تعمل نداء مخصص.
  - **Suppliers**: نفس الفكرة مع `GET /query/suppliers`. حقل `branch_ids` اللي السيرفر بيرجعه بيتقرا ويتجاهل — بالظبط زي ما موديل Supplier المحلي أصلاً موثّق إنه بيعمل (مفيش شاشة اختيار فروع لسه).
  - **Wallets (الأعقد في الخطوة دي)**: السيرفر مفهوش جدول "حركات محفظة" بنفس شكل الموبايل — كل حركة فلوس هناك سطر Ledger مزدوج القيد (`account_id`, `debit`, `credit`). فـ:
    - `getBalances()` بتطبّق **نفس معادلة السيرفر بالظبط** (`AccountingService.balance()` في `backend/functions/accounting/service.py`: `sum(debit - credit)`) على كل سطور الـ Ledger اللي `account_id` بتاعها بادئ بـ `wallet:` (نفس الـ prefix اللي `backend/functions/services/completion.py` بيستخدمه لكل حركة محفظة).
    - `listTransactions()` بتحوّل كل سطر Ledger مطابق لـ `WalletTransaction`. بس نوعين بس من الـ `entry_type` اللي بيوصل للمحفظة ليهم مقابل حقيقي في `WalletTxType` المحلي: `SALE_PAYMENT` → بيع، `MAINTENANCE_PAYMENT` → صيانة. أي نوع تاني (`PURCHASE_PAYMENT`, `CUSTOMER_PAYMENT`, `CUSTOMER_TRANSFER_IN/OUT`) — مفيهوش فيتشر مقابل في الموبايل لسه (مشتريات، تحصيل عميل مستقل، تحويل بين محافظ) — بيتحط كـ "تسوية" (`adjustment`) مع الاحتفاظ بنوع السيرفر الأصلي في الملاحظة بدل ما نلصق عليه تصنيف غلط.
    - `deposit`/`withdraw`/`postAuto` بتتوكل للـ Repository المحلي زي باقي الكلاسات.
- الأربع Providers (`inventory_provider.dart`, `customer_provider.dart`, `supplier_provider.dart`, `wallet_provider.dart`) اتعدّلوا: كل واحد بيتحقق من `AuthService.instance.currentSession` **في كل نداء** (مش وقت أول إنشاء بس) — لو فيه جلسة شغالة يرجّع `ApiXRepository`، ولو لأ يرجّع نفس `SqliteXRepository` القديم. يعني تسجيل الدخول/الخروج بيأثر على القراءة من أول نداء تالي من غير ما تحتاج تعيد فتح التطبيق، ومفيش أي كسر لأي استدعاء قديم لأن كل الأماكن اللي بتستخدم الدوال دي أصلاً بتعمل `await` عليها.

**ملفات جديدة:**
- `apps/admin_mobile/lib/features/inventory/api_inventory_repository.dart`
- `apps/admin_mobile/lib/features/customers/api_customer_repository.dart`
- `apps/admin_mobile/lib/features/suppliers/api_supplier_repository.dart`
- `apps/admin_mobile/lib/features/wallets/api_wallet_repository.dart`

**ملفات معدّلة:**
- `apps/admin_mobile/lib/features/inventory/inventory_provider.dart`
- `apps/admin_mobile/lib/features/customers/customer_provider.dart`
- `apps/admin_mobile/lib/features/suppliers/supplier_provider.dart`
- `apps/admin_mobile/lib/features/wallets/wallet_provider.dart`

> ⚠️ نفس التنويه المتكرر: مفيش Flutter SDK ولا إنترنت في البيئة دي، فمقدرتش أشغّل `flutter analyze` ولا أعمل نداء حقيقي على السيرفر (خصوصًا `/query/ledger` — معادلة الرصيد اتأكدت منها بمراجعة كود `AccountingService.balance()` وكل الأماكن اللي بتكتب `LedgerEntry` بـ `wallet:` prefix في `completion.py`، مش بتجربة فعلية). عملت فحص توازن الأقواس على كل ملف جديد/معدّل، وتتبعت كل استدعاء قديم لـ `getInventoryRepository`/`getCustomerRepository`/`getSupplierRepository`/`getWalletRepository` في المشروع كله للتأكد إن التوقيع الجديد (لسه `Future<T>` وبيتـ`await` زي الأول) مايكسرش حاجة. لازم تتأكد بـ `flutter pub get && flutter analyze && flutter run`، وتشغيل السيرفر فعليًا (`uvicorn backend.api_server.main:app`) وتسجيل دخول حقيقي عشان تتأكد إن أرصدة المحافظ ظاهرة صح.

**النتيجة:** ✔ شاشات المخزون/العملاء/الموردين/المحافظ بتعرض بيانات السيرفر تلقائيًا لأي مستخدم مسجّل دخول، من غير ما أي عملية بيع/مصروف/صيانة محلية تتأثر أو تتكسر.

---

- [ ] 4.3 رفع البيانات (Sales / Expenses / Maintenance / Installments) للسيرفر.

---

## المرحلة 5 — Sync Engine

- [ ] 5.1 Upload Queue (Outbox + Retry + Failure Handling).
- [ ] 5.2 Download Queue (Cursor Tracking + Changes Fetching).
- [ ] 5.3 Sync Dashboard (Pending Commands / Last Sync / Sync Errors / Conflict Count).

---

## المرحلة 6 — اختبار الأجهزة المتعددة ⬜

- [ ] سيناريو 1: بيع من جهاز موبايل يظهر على جهاز موبايل تاني.
- [ ] سيناريو 2: عميل جديد من فرع يظهر في الفروع التانية.
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

---

## ملفات تم إنشاؤها أو تعديلها لتنفيذ 1.2

**ملفات جديدة:**
- `apps/admin_mobile/lib/features/settings/backup_service.dart` — منطق Export/Import (بناء وقراءة ملف الـ JSON).
- `apps/admin_mobile/lib/features/settings/settings_page.dart` — صفحة الإعدادات الحقيقية (Cloud Account info / Export / Import / About).
- `apps/admin_mobile/lib/features/settings/about_page.dart` — صفحة "عن التطبيق".

**ملفات معدّلة:**
- `apps/admin_mobile/lib/main.dart` — شيل الـ `SettingsPage` الوهمية القديمة (الكلاس نفسه) وربط `index 10` بالصفحة الحقيقية من `features/settings/settings_page.dart`.
- `apps/admin_mobile/lib/features/inventory/local_store.dart` — إضافة `exportAllRecords()`, `restoreRecord(...)`, `clearAllRecords()` لدعم النسخ الاحتياطي الكامل.
- `apps/admin_mobile/pubspec.yaml` — إضافة `path_provider`, `file_picker`, `share_plus`.

---

## ملفات تم تعديلها لتنفيذ 1.3

**ملفات معدّلة:**
- `apps/admin_mobile/lib/main.dart`:
  - شيل زراري "Sync" و"Notifications" الوهميين من الـ `AppBar` (كانوا `onPressed: () {}`).
  - شيل زرار "إضافة جديد" الوهمي من `GenericPage` واستبدال النص المضلل تحته بنص صريح إن الوحدة "قيد التطوير".

> ⚠️ تنويه: نفس القيد اللي في 1.1 و1.2 — البيئة هنا من غير Flutter SDK ولا إنترنت، فمقدرتش أشغّل `flutter pub get` ولا `flutter analyze` ولا `flutter run` فعليًا. عملت مراجعة يدوية شاملة بدلها (grep على كل الـ callbacks/TODOs، فحص توازن الأقواس، تتبع كل `get*Repository()`) وده موضّح بالتفصيل في قسم 1.3 فوق. الخطوة اللي لازم تعملها إنت: `flutter pub get && flutter analyze && flutter run` قبل أي دمج نهائي.

---

## ملفات تم تعديلها لتنفيذ 1.4

**ملفات معدّلة:**
- `apps/admin_mobile/lib/features/sales/sale_models.dart` — إضافة `costAtSale` و`costIsEstimated` لـ `SaleItemRecord`، وgetter جديد `lineCost`.
- `apps/admin_mobile/lib/features/sales/sqlite_sale_repository.dart` — تخزين/قراءة `cost_at_sale`/`cost_is_estimated` في الـ payload، سناب-شوت التكلفة الحقيقية وقت `createSale`، وإضافة `_migrateLegacyCostAtSale()` تتنفذ تلقائيًا في `create()`.
- `apps/admin_mobile/lib/features/sales/sales_page.dart` — تمرير `costAtSale` عند بناء `SaleItemRecord` من الـ Cart (قيمة مبدئية، الـ Repository بيستبدلها بالتكلفة الحقيقية وقت الحفظ).
- `apps/admin_mobile/lib/features/reports/reports_models.dart` — إضافة `hasEstimatedCosts` لـ `ReportSummary` وتحديث التعليقات التوضيحية.
- `apps/admin_mobile/lib/features/reports/reports_repository.dart` — حساب `estimatedCogs` من `item.lineCost` بدل تكلفة المخزون الحالية، وحساب `hasEstimatedCosts`.
- `apps/admin_mobile/lib/features/reports/reports_page.dart` — تسمية الكروت بقت شرطية ("ربح المبيعات" أو "ربح المبيعات (تقديري جزئيًا)") حسب `hasEstimatedCosts`.

> ⚠️ نفس التنويه: مقدرتش أشغّل `flutter analyze`/`flutter run` فعليًا هنا. راجعت الكود يدويًا (توازن الأقواس، كل الأماكن اللي بتبني `SaleItemRecord`/`ReportSummary` في المشروع كله) للتأكد إن مفيش مكان تاني اتكسر بسبب إضافة حقول مطلوبة (`required`) للكلاسين دول. لازم تتأكد بـ `flutter pub get && flutter analyze && flutter run` قبل الدمج.
