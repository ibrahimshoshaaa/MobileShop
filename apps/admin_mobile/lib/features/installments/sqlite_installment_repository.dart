import 'dart:math';
import '../inventory/local_store.dart';
import '../sales/sale_models.dart' show PaymentMethod, PaymentMethodX;
import '../sync/online_push.dart';
import '../wallets/wallet_models.dart';
import 'installment_models.dart';
import 'installment_repository.dart';

class SqliteInstallmentRepository implements InstallmentRepository {
  SqliteInstallmentRepository._(this._store);
  final LocalStore _store;
  static const _planEntity = 'installment_plan';
  static const _paymentEntity = 'installment_payment';

  static Future<SqliteInstallmentRepository> create() async {
    final store = await LocalStore.open();
    return SqliteInstallmentRepository._(store);
  }

  InstallmentPlan _toPlan(Map<String, dynamic> p) => InstallmentPlan(
        id: p['id'] as String,
        saleId: p['sale_id'] as String?,
        customerId: p['customer_id'] as String,
        customerName: p['customer_name'] as String,
        baseFinanced: (p['base_financed'] as num).toDouble(),
        ratePercent: (p['rate_percent'] as num).toDouble(),
        increase: (p['increase'] as num).toDouble(),
        totalDue: (p['total_due'] as num).toDouble(),
        termMonths: p['term_months'] as int,
        monthlyAmount: (p['monthly_amount'] as num).toDouble(),
        createdAt: DateTime.parse(p['created_at'] as String),
      );

  Map<String, dynamic> _planPayload(InstallmentPlan p) => {
        'id': p.id,
        'sale_id': p.saleId,
        'customer_id': p.customerId,
        'customer_name': p.customerName,
        'base_financed': p.baseFinanced,
        'rate_percent': p.ratePercent,
        'increase': p.increase,
        'total_due': p.totalDue,
        'term_months': p.termMonths,
        'monthly_amount': p.monthlyAmount,
        'created_at': p.createdAt.toIso8601String(),
      };

  InstallmentPaymentRecord _toPayment(Map<String, dynamic> p) => InstallmentPaymentRecord(
        id: p['id'] as String,
        planId: p['plan_id'] as String,
        amount: (p['amount'] as num).toDouble(),
        method: PaymentMethodX.fromWireValue(p['wallet_id'] as String),
        paidAt: DateTime.parse(p['paid_at'] as String),
      );

  Map<String, dynamic> _paymentPayload(InstallmentPaymentRecord p) => {
        'id': p.id,
        'plan_id': p.planId,
        'amount': p.amount,
        'wallet_id': p.method.wireValue,
        'paid_at': p.paidAt.toIso8601String(),
      };

  @override
  Future<List<InstallmentPlan>> listPlans() async {
    final rows = await _store.listRecords(entity: _planEntity);
    final plans = rows.map((r) => _toPlan(r.payload)).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return plans;
  }

  @override
  Future<InstallmentPlan> createPlan({
    String? saleId,
    required String customerId,
    required String customerName,
    required double price,
    required double downPayment,
    required double ratePercent,
    required int termMonths,
  }) async {
    final calc = calculateInstallment(
      price: price,
      downPayment: downPayment,
      ratePercent: ratePercent,
      termMonths: termMonths,
    );
    final plan = InstallmentPlan(
      id: _newId('plan'),
      saleId: saleId,
      customerId: customerId,
      customerName: customerName,
      baseFinanced: calc.baseFinanced,
      ratePercent: ratePercent,
      increase: calc.increase,
      totalDue: calc.totalDue,
      termMonths: termMonths,
      monthlyAmount: calc.monthlyAmount,
      createdAt: DateTime.now(),
    );
    await _store.upsertRecord(entity: _planEntity, recordId: plan.id, payload: _planPayload(plan), expectedVersion: 0);
    // Reuses plan.id as the command id, same reasoning as createSale in
    // sqlite_sale_repository.dart — so a successful online push leaves the
    // server's InstallmentPlan under this same id, which collectPayment
    // below relies on when it later references [planId].
    await _store.queueCommand(
      commandId: plan.id,
      command: 'createInstallmentPlan',
      payload: _planPayload(plan),
    );
    // 4.3: only pushable when both are true —
    //  - saleId != null: create_installment_plan on the server always
    //    looks the sale up (`s=self.sales.get(sale_id)`) and uses it to
    //    validate the receivable and the customer; there is no server-side
    //    concept of a plan with no linked sale, unlike this local model,
    //    which deliberately allows [saleId] to be null for a standalone/
    //    layaway-style plan (see the InstallmentPlan doc comment).
    //  - downPayment == 0: the server takes an explicit
    //    `down_payment_wallet_id` to post the down payment against, and
    //    requires one whenever down_payment > 0 — this local model has no
    //    down-payment-wallet field at all (createPlan's signature has no
    //    [PaymentMethod] parameter for it), so there's nothing correct to
    //    send when a down payment was actually taken.
    if (saleId != null && downPayment == 0) {
      await pushCommandOnline(_store, plan.id, 'createInstallmentPlan', {
        'sale_id': saleId,
        'customer_id': customerId,
        'down_payment': downPayment,
        'rate_percent': ratePercent,
        'term_months': termMonths,
      });
    }
    return plan;
  }

  @override
  Future<List<InstallmentPaymentRecord>> listPayments(String planId) async {
    final rows = await _store.listRecords(entity: _paymentEntity);
    final payments = rows.map((r) => _toPayment(r.payload)).where((p) => p.planId == planId).toList()
      ..sort((a, b) => a.paidAt.compareTo(b.paidAt));
    return payments;
  }

  @override
  Future<double> remaining(String planId) async {
    final planRow = await _store.getRecord(entity: _planEntity, recordId: planId);
    if (planRow == null) throw InstallmentException('خطة التقسيط غير موجودة.');
    final plan = _toPlan(planRow.payload);
    final payments = await listPayments(planId);
    final paid = payments.fold<double>(0, (sum, p) => sum + p.amount);
    final left = plan.totalDue - paid;
    return left < 0 ? 0 : left;
  }

  @override
  Future<InstallmentPaymentRecord> collectPayment({
    required String planId,
    required double amount,
    required PaymentMethod method,
  }) async {
    if (amount <= 0) throw InstallmentException('المبلغ يجب أن يكون أكبر من صفر.');
    final planRow = await _store.getRecord(entity: _planEntity, recordId: planId);
    if (planRow == null) throw InstallmentException('خطة التقسيط غير موجودة.');
    final currentRemaining = await remaining(planId);
    if (amount - currentRemaining > 0.01) {
      throw InstallmentException('المبلغ يتجاوز المتبقي (${currentRemaining.toStringAsFixed(2)} ج.م).');
    }
    final payment = InstallmentPaymentRecord(
      id: _newId('inst-pay'),
      planId: planId,
      amount: amount,
      method: method,
      paidAt: DateTime.now(),
    );
    await _store.upsertRecord(
      entity: _paymentEntity,
      recordId: payment.id,
      payload: _paymentPayload(payment),
      expectedVersion: 0,
    );
    await _store.queueCommand(
      commandId: payment.id,
      command: 'collectInstallment',
      payload: {
        'installment_id': planId,
        'amount': amount,
        'wallet_id': method.wireValue,
      },
    );
    // Same CASH/WALLET-only constraint as sales/expenses above: the server
    // requires a real wallet to post the collection against, and there's
    // none for CARD/CREDIT. Reuses payment.id as the command id, matching
    // createPlan's id-reuse above, though this push only actually lands
    // when the plan itself made it to the server (i.e. it was created with
    // saleId set and no down payment) — otherwise the server 404s on
    // [planId] and this is silently left queued, same as any other
    // best-effort push.
    final walletId = BuiltinWallets.tryFromWireValue(method.wireValue)?.id;
    if (walletId != null) {
      await pushCommandOnline(_store, payment.id, 'collectInstallment', {
        'installment_id': planId,
        'amount': amount,
        'wallet_id': walletId,
      });
    }
    return payment;
  }

  String _newId(String prefix) => '$prefix-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(999999)}';
}
