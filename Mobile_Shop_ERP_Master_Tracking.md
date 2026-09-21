# Mobile Shop ERP — الملف الأم (تتبّع كل الفيتشرز والخطوات)

**آخر تحديث:** 2026-09-21 — تم تنفيذ إصلاح atomic sync، وربط Desktop Sales بالـAPI مع endpoint مخصص للمبيعات، وإصلاح صلاحيات القراءة ووحدة إدخال الدفع، وإغلاق آخر تحذير Flutter const. التحقق النهائي على فرع الإصلاح ما زال منتظرًا عبر PR/CI.

> هذا الملف هو **المرجع الوحيد** لحالة المشروع: ما تم إنجازه، وما هو قيد التنفيذ، وما يجب إكماله قبل اعتبار النسخة Production-ready.
>
> **قاعدة التتبع:** أي PR يغيّر نطاق ما يتتبعه هذا الملف يجب أن يحدّثه في نفس الـPR؛ لا يتم دمج تغيير في الـscope بدون تحديث هذا الملف.

---

## 1. الباكيند (Backend)

### محرك الأوامر (Command Engine)
- ✅ محرك أوامر كامل موجود من الأصل (`erp_engine.py` + `completion.py`) — مبيعات، مشتريات، تحويلات، أقساط، صيانة، رواتب، دفتر أستاذ، صلاحيات، تدقيق، معاملات atomic.
- ✅ حدود HTTP جاهزة (`backend/functions/api/http.py` + `dispatch.py`).
- ✅ إصلاح أوامر `createProduct` / `createCustomer` / `createSupplier` عبر HTTP.
- ✅ أمر `createWallet` مع الصلاحية وحماية الفرع ومنع تكرار الاسم.
- ✅ أمر `updateProduct`.
- ✅ نقطة قراءة حقيقية `GET /products`.
- ⬜ أوامر تعديل/تعطيل محفظة عبر HTTP.
- ⬜ أمر `updateSupplier` متصل بالسيرفر.
- ⬜ مراجعة شاملة لباقي الأوامر غير المغطاة عبر HTTP.

### الأمان والهوية
- ✅ إضافة `tenant_id` إلى `CommandContext`.
- ✅ Idempotency أصبحت معزولة حسب الـ Tenant عبر مفتاح `tenant_id:command_id`.
- ✅ سجلات التدقيق أصبحت Tenant-scoped.
- ✅ تمرير `tenant_id` من الـ claims الموثقة إلى طبقة الأوامر.
- ✅ إضافة Production Auth boundary لـ Firebase ID tokens.
- ✅ Firebase production verification يستخدم revocation checking.
- ✅ اختيار صريح بين `AUTH_PROVIDER=dev` و `AUTH_PROVIDER=firebase`.
- ✅ منع تشغيل `AUTH_PROVIDER=dev` عندما `APP_ENV=production`.
- ✅ production claims تتطلب `tenant_id` ولا يوجد fallback في HTTP boundary.
- ✅ server-side branch membership + command permissions مطبقة عند حدود الأوامر.
- ✅ request body ممنوع من override للـ tenant/user/permissions.
- ✅ Firebase verification يستخدم revocation checking؛ اختبارات boundary أضيفت، وتبقى اختبارات staging بتوكنات حقيقية.

### التحقق من ملكية البيانات
- ✅ التحقق من وجود Supplier قبل استخدامه في التدفقات المناسبة.
- ✅ التحقق من صلاحية الوصول للفرع الخاص بالـ Supplier.
- ✅ التحقق من وجود Customer في التدفقات التي تعتمد عليه.
- ✅ Regression test لعزل Idempotency بين Tenant مختلف.
- ✅ إضافة `tenant_id` إلى نماذج foundation وERP.
- ✅ repository reads/writes أصبحت tenant-scoped عند وجود auth scope.
- ✅ cross-tenant tests للعملاء/الموردين/المنتجات + sync.
- ✅ الاستعلامات HTTP أصبحت tenant/branch-scoped.
- ⬜ مراجعة ERP-specific لكل foreign-key/reference تحتاج إكمالاً في P1/accounting.

### خادم API المحلي للتطوير
- ✅ FastAPI حقيقي شغّال (`/health`, `/command`).
- ✅ Dev tokens للتطوير والاختبارات فقط.
- ✅ Seed data للتجربة.
- ✅ Idempotency.
- 🟡 Query endpoints موجودة ومحمية؛ تمت إضافة endpoints صريحة لـsales/customers/wallets لاستخدام الـdesktop Online mode.
- ⬜ Error contract موحد وآمن.
- ⬜ Request schema validation كاملة.
- ⬜ branch + permission checks على كل endpoint.

---

## 2. الاستمرارية (Durability / Persistence)

- ✅ طبقة SQLite حقيقية (`DurableERPCommandEngine`).
- ✅ Idempotency محفوظة بعد إعادة تشغيل السيرفر.
- ✅ Transaction أصبح يربط transaction الخاصة بالـ DB مع transaction الذاكرة.
- ✅ عند فشل الحفظ يتم rollback للـ DB واسترجاع حالة الذاكرة.
- ✅ حذف السجلات يتم حفظه في persistence.
- ✅ حذف سجلات processed/idempotency يتم حفظه.
- ✅ Turso/libSQL production adapter مضاف ويُفعل عند `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN`.
- ✅ production startup يرفض العمل بدون Turso credentials.
- ✅ في Turso mode يتم refresh من SQL المركزي داخل transaction قبل تنفيذ الأمر.
- ⬜ اختبار network/DB failure على Turso الحقيقي.
- ✅ local SQLite backup/restore drill + integrity verification مضاف.
- 🟡 تنفيذ backup/restore drill فعلي على حساب Turso الإنتاجي — automation محلية جاهزة، لكن إثبات managed-Turso يحتاج حساب Turso وصلاحية إنشاء restore target.
- ✅ sync protocol يستخدم central SQL idempotency/cursor model؛ تبقى مراجعة تشغيلية فعلية على عدة workers.

---

## 3. الاختبارات و DevOps

- 🟡 الاختبارات الأصلية 101؛ آخر CI مكتمل للـPR كان **122 passed / 10 failed** بعد تغييرات مالية، ثم أضيفت إصلاحات الاختبارات والمنطق ويجب انتظار CI جديد.
- ✅ Python compile check ناجح.
- ✅ GitHub Actions CI مضاف.
- ✅ CI يعمل على `main` و `production-hardening/**` و Pull Requests.
- ✅ pytest داخل CI.
- ✅ Bandit داخل CI.
- ✅ pip-audit داخل CI.
- ✅ Dependabot للإصدارات.
- ✅ `.env.example` لمتطلبات الإنتاج.
- ✅ `SECURITY.md`.
- ✅ `docs/PRODUCTION_RELEASE_PLAN.md`.
- ✅ آخر CI أخضر قبل حزمة ERP regression كان ناجحاً؛ ثم أضافت المراجعة اختبارات ERP جديدة كشفت 5 إخفاقات، وتم إصلاح أسبابها/تهيئة الاختبارات. تشغيل CI على الـHEAD الحالي ما زال قيد التنفيذ.
- ✅ اختبارات concurrency/multi-device sync أضيفت.
- ✅ staging smoke script + manual GitHub workflow أضيفا.
- 🟡 Staging smoke — آخر تشغيل على `main` فشل عند `GET /products` بـ401؛ تم تعديل الـworkflow في فرع الإصلاح بحيث لا يعمل مع كل Push على `main`، ويظل يدويًا وعلى فروع الـrelease. إعادة التحقق الفعلي على staging ما زالت مطلوبة.
- ⬜ production smoke tests.
- 🟡 build/release artifact verification — client validation أضيفت إلى CI، وما زال artifact/E2E proof مطلوباً.

---

## 4. تطبيق الموبايل (Flutter)

| الفيتشر | الحالة | ملاحظات |
|---|---|---|
| المخزون | ✅ | قائمة، بحث، فلتر نوع، إضافة/تعديل صنف، تعديل رصيد، SQLite |
| المبيعات | ✅ | سلة، خصم، دفع مختلط، ربط بالمخزون، إلغاء فاتورة |
| العملاء | ✅ | قائمة، بحث، إضافة/تعديل، ربط بالمبيعات والأقساط |
| الأقساط | ✅ | حساب حي، إنشاء خطة، تحصيل، منع تجاوز المتبقي |
| المصروفات | ✅ | تصنيفات، إجمالي اليوم، سجل |
| الموردون | ✅ | قائمة، بحث، إضافة/تعديل |
| الصيانة | ✅ | دورة الاستلام → الفحص → الإصلاح → الجاهزية → التسليم |
| التقارير | ⬜ | Placeholder |
| الفروع والمستخدمون | ⬜ | Placeholder |
| الإعدادات / ربط الحساب / Online mode | ⬜ | Placeholder |

### نطاق v1.0.0 للموبايل

> **Offline-only:** الإصدار v1.0.0 لا يتصل بالسيرفر. Online mode مؤجل لإصدار لاحق وسيتم تتبعه كمرحلة مستقلة.

### حدود الموبايل
- ⬜ لا يوجد Barcode/IMEI scanner حقيقي.
- ⬜ لا توجد طباعة إيصال.
- ⬜ لا توجد واجهة صلاحيات مستخدمين مكتملة.
- 🟡 الموبايل **Offline-only في v1.0.0 عن قصد**؛ لا يوجد server connectivity في هذا الإصدار. Online mode مخطط لإصدار لاحق. CI الآن يتحقق من Flutter analysis، لكن E2E الحقيقي ما زال مطلوباً.
- ⬜ بروتوكول offline sync الحقيقي غير مكتمل.
- ⬜ أرصدة المحافظ ليست دورة مالية مركزية كاملة.
- ⬜ الحسابات المالية تحتاج مراجعة لاستخدام Decimal/دقة مالية مناسبة.

---

## 5. تطبيق الديسكتوب (Tkinter)

| الفيتشر | الحالة | ملاحظات |
|---|---|---|
| المخزون | ✅ | متصل بالـ API الحقيقي في Online mode |
| المبيعات | 🟡 | متصلة بالـAPI في Online mode؛ Offline mode ما زال محليًا |
| العملاء | ✅ | منطق محلي |
| الأقساط | ✅ | منطق محلي |
| المصروفات | ✅ | منطق محلي |
| الموردون | ✅ | منطق محلي |
| الصيانة | ✅ | منطق محلي |
| التقارير | ⬜ | Placeholder |
| الفروع والمستخدمون | ⬜ | Placeholder |
| الإعدادات | ⬜ | Placeholder |

### حدود الديسكتوب
- ✅ يستخدم نفس `SQLiteRepository` في الباكيند.
- ✅ المخزون تم اختباره عبر HTTP حقيقي مع uvicorn.
- 🟡 باقي التبويبات تحتاج API read/write حقيقي قبل اعتبار desktop workflow كاملاً؛ **Sales أصبح أول سطح إضافي متصل بالـAPI**.
- ⬜ الواجهة الرسومية نفسها لم تُختبر في بيئة تحتوي Tkinter.
- ⬜ لا توجد طباعة/سكانر hardware integration.
- ⬜ لا توجد صلاحيات مستخدمين مكتملة.

---

## 6. بروتوكول المزامنة (Offline / Multi-device Sync)

- ✅ server upload protocol.
- ✅ download cursor protocol.
- ✅ conflict detection/reconciliation عبر `STALE_VERSION` وscope conflicts.
- ✅ retry + exponential backoff على الجهاز للحالات transient.
- ✅ idempotent sync operations.
- ✅ multi-device concurrency tests.
- ✅ append-only sync event/audit trail مع cursor.
- ⬜ UI visibility كاملة لحالات Online / Offline / Syncing / Failed.

---

## 7. الـ ERP correctness والعمليات المالية

- 🟡 sales / returns / refunds accounting matrix: قيود void/return + settlement-safe refunds + credit returns أضيفت؛ يلزم استكمال mixed-payment matrix بعد نتيجة CI.
- 🟡 purchases / supplier payments accounting matrix: تحقق المورد/الفرع/عدم تجاوز الرصيد أضيف؛ يلزم regression matrix كاملة.
- 🟡 wallet / ledger invariants واختبارات الرصيد: commission والتحقق من رصيد المصدر مضافان؛ يلزم تثبيت نتيجة CI ثم توسيع closing/concurrency.
- 🟡 installments accounting end-to-end: principal/interest posting أضيف مع regression test؛ يلزم اختبار حالات التقسيط المتعددة/الـrounding.
- ⬜ IMEI lifecycle كامل.
- ⬜ branch transfer lifecycle.
- ⬜ day closing / reopening rules.
- ⬜ duplicate-command / concurrent-command tests على السيناريوهات المالية.
- ⬜ تقارير مالية متسقة مع مصدر SQL المركزي.

---

## 8. Hardware / Release

- ⬜ Barcode scanner integration.
- ⬜ IMEI scanner workflow.
- ⬜ Thermal printer integration.
- ⬜ Cash drawer integration.
- ⬜ staging deployment.
- ⬜ production deployment.
- ⬜ HTTPS + secrets configuration.
- ⬜ monitoring / logging / alerting.
- ⬜ final backup + restore verification.

---

## 9. ترتيب التنفيذ قبل Production

### P0 — لا يتم اعتبار النسخة Production-ready قبل إغلاقها
1. 🟢 Tenant isolation code path — تم التنفيذ، مع بقاء مراجعة foreign-key النهائية.
2. 🟢 Firebase production auth boundary — تم التنفيذ؛ يلزم staging verification.
3. 🟢 Turso/libSQL persistence path — تم التنفيذ؛ يلزم اختبار فشل DB/network فعلي.
4. 🟢 Secured query/command/sync API — تم التنفيذ للسطح الحالي؛ أوامر الإدارة المتبقية في P1.
5. 🟢 Offline sync protocol — تم التنفيذ؛ يلزم اختبار end-to-end على أجهزة فعلية.
6. 🟢 Multi-device concurrency/conflict coverage — تم التنفيذ برمجياً؛ يلزم staging multi-worker run.
7. 🟡 Backup/restore — drill محلي جاهز، يلزم drill فعلي على Turso.
8. 🟡 Staging smoke — automation جاهزة، التشغيل الفعلي يحتاج secrets + staging URL.

### P1 — CI verification

- 🟡 الـworkflows التالية موجودة في `.github/workflows/`: `staging-client-e2e.yml`, `staging-smoke.yml`, `turso-integration.yml`, `turso-deep-integration.yml`, `turso-recovery-drill.yml`, `production-audit.yml`, `mobile-release.yml`.
- 🟡 آخر تشغيل معروف على `main`: CI كان `139 passed / 1 failed` بسبب توقع اختبار concurrency لحالة `PROCESSING` بينما التنفيذ الحالي يعيد `RETRYABLE`، وتم تحديث الاختبار في فرع الإصلاح. Turso Integration نجح، بينما Turso Deep Integration فشل بسبب interactive transaction على Turso تم rollback له بعد idle timeout أثناء تزامن عاملين. Mobile Release فشل على Flutter analyzer في commit أقدم قبل إصلاحات const الأخيرة. Staging smoke فشل بـ401 في `/products`. لا تُعتبر أي من هذه بوابة Production خضراء حتى تشغيل CI جديد على فرع الإصلاح.

### P1
- ⬜ إكمال ERP accounting invariants.
- ⬜ إكمال mobile/desktop online workflows.
- ⬜ التقارير.
- ⬜ الفروع والمستخدمون والصلاحيات UI.
- ⬜ الإعدادات والـ account linking.
- ⬜ hardware integrations.

### P2
- ⬜ release artifacts.
- ⬜ monitoring/alerting.
- ⬜ تحسينات الأداء والتنظيف النهائي.

---

## 10. قاعدة الدمج

> **لا يتم Merge لفرع `production-hardening/rc3` إلى `main` لمجرد أن CI أخضر.**
>
> الـ CI الأخضر يثبت أن الاختبارات الحالية ناجحة، لكنه لا يثبت اكتمال P0 أو جاهزية النظام للإنتاج.
>
> يتم الدمج بعد إغلاق بنود P0، وتشغيل staging smoke test، والتحقق من الـ persistence والـ auth والـ tenant isolation والـ sync على بيئة قريبة من الإنتاج.

---

## الحالة الحالية

**Branch:** `fix/ci-staging-smoke-trigger`  
**CI:** 🟡 pending — سيتم التحقق عبر Pull Request إلى `main`  
**Tests:** 🟡 آخر run معروف: 139 passed / 1 failed؛ تم إصلاح توقع concurrency وإضافة اختبار Online Sales endpoint، ولم يُثبت CI الجديد بعد  
**Bandit:** 🟢 آخر run معروف passed  
**pip-audit:** 🟢 آخر run معروف passed  
**Production-ready:** ⬜ لا — يلزم CI جديد + staging/Turso operational verification  
**Main:** لم يتم تعديله ضمن هذه الجولة.
