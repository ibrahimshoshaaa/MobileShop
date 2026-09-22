import 'package:flutter/material.dart';
import '../customers/customer_models.dart';
import '../customers/customer_provider.dart';
import '../customers/customers_page.dart';
import '../sales/sale_models.dart' show PaymentMethod, PaymentMethodX;
import 'installment_models.dart';
import 'installment_provider.dart';
import 'installment_repository.dart';

class InstallmentsPage extends StatefulWidget {
  const InstallmentsPage({super.key});

  @override
  State<InstallmentsPage> createState() => _InstallmentsPageState();
}

class _InstallmentsPageState extends State<InstallmentsPage> {
  late Future<InstallmentRepository> _repositoryFuture;
  InstallmentRepository? _repository;
  Future<List<InstallmentPlan>>? _plansFuture;

  @override
  void initState() {
    super.initState();
    _repositoryFuture = getInstallmentRepository();
  }

  void _reload() {
    final repo = _repository;
    if (repo == null) return;
    setState(() => _plansFuture = repo.listPlans());
  }

  Future<void> _openNewPlan(InstallmentRepository repository) async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => NewInstallmentPlanScreen(repository: repository)),
    );
    if (created == true) _reload();
  }

  Future<void> _openDetail(InstallmentRepository repository, InstallmentPlan plan) async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => InstallmentPlanDetailScreen(repository: repository, plan: plan)),
    );
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<InstallmentRepository>(
      future: _repositoryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('تعذّر تحميل خطط التقسيط\n${snapshot.error}', textAlign: TextAlign.center));
        }
        _repository = snapshot.data!;
        _plansFuture ??= _repository!.listPlans();

        return Scaffold(
          body: RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                ElevatedButton.icon(
                  onPressed: () => _openNewPlan(_repository!),
                  icon: const Icon(Icons.add),
                  label: const Text('خطة تقسيط جديدة'),
                ),
                const SizedBox(height: 20),
                FutureBuilder<List<InstallmentPlan>>(
                  future: _plansFuture,
                  builder: (context, plansSnapshot) {
                    if (plansSnapshot.connectionState != ConnectionState.done) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Center(child: CircularProgressIndicator()),
                      );
                    }
                    final plans = plansSnapshot.data ?? const [];
                    if (plans.isEmpty) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Center(child: Text('لا توجد خطط تقسيط بعد')),
                      );
                    }
                    return Column(
                      children: [
                        for (final plan in plans)
                          Card(
                            child: ListTile(
                              leading: const Icon(Icons.payments_outlined),
                              title: Text(plan.customerName),
                              subtitle: Text(
                                'القسط الشهري: ${plan.monthlyAmount.toStringAsFixed(2)} ج.م • '
                                'الإجمالي: ${plan.totalDue.toStringAsFixed(2)} ج.م • ${plan.termMonths} شهر',
                              ),
                              trailing: FutureBuilder<double>(
                                future: _repository!.remaining(plan.id),
                                builder: (context, remSnapshot) {
                                  if (!remSnapshot.hasData) return const SizedBox.shrink();
                                  final remaining = remSnapshot.data!;
                                  final done = remaining <= 0.01;
                                  return Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: (done ? Colors.green : Colors.orange).withOpacity(0.12),
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: Text(
                                      done ? 'مكتمل' : 'متبقي ${remaining.toStringAsFixed(0)}',
                                      style: TextStyle(
                                        color: done ? Colors.green.shade700 : Colors.orange.shade800,
                                        fontWeight: FontWeight.bold,
                                        fontSize: 12,
                                      ),
                                    ),
                                  );
                                },
                              ),
                              onTap: () => _openDetail(_repository!, plan),
                            ),
                          ),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class NewInstallmentPlanScreen extends StatefulWidget {
  const NewInstallmentPlanScreen({super.key, required this.repository});
  final InstallmentRepository repository;

  @override
  State<NewInstallmentPlanScreen> createState() => _NewInstallmentPlanScreenState();
}

class _NewInstallmentPlanScreenState extends State<NewInstallmentPlanScreen> {
  Customer? _customer;
  final _priceController = TextEditingController();
  final _downPaymentController = TextEditingController(text: '0');
  final _rateController = TextEditingController(text: '0');
  final _termController = TextEditingController(text: '6');
  bool _submitting = false;
  String? _error;

  InstallmentCalculation? get _preview {
    final price = double.tryParse(_priceController.text);
    final down = double.tryParse(_downPaymentController.text);
    final rate = double.tryParse(_rateController.text);
    final term = int.tryParse(_termController.text);
    if (price == null || down == null || rate == null || term == null) return null;
    try {
      return calculateInstallment(price: price, downPayment: down, ratePercent: rate, termMonths: term);
    } on InstallmentException {
      return null;
    }
  }

  Future<void> _pickCustomer() async {
    final customerRepository = await getCustomerRepository();
    if (!mounted) return;
    final customer = await Navigator.of(context).push<Customer>(
      MaterialPageRoute(builder: (_) => CustomerPickerScreen(repository: customerRepository)),
    );
    if (customer != null) setState(() => _customer = customer);
  }

  Future<void> _submit() async {
    if (_customer == null) {
      setState(() => _error = 'يجب اختيار عميل لخطة التقسيط.');
      return;
    }
    final price = double.tryParse(_priceController.text);
    final down = double.tryParse(_downPaymentController.text);
    final rate = double.tryParse(_rateController.text);
    final term = int.tryParse(_termController.text);
    if (price == null || down == null || rate == null || term == null) {
      setState(() => _error = 'تأكد من إدخال كل الحقول بأرقام صحيحة.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.repository.createPlan(
        customerId: _customer!.id,
        customerName: _customer!.name,
        price: price,
        downPayment: down,
        ratePercent: rate,
        termMonths: term,
      );
      if (mounted) Navigator.of(context).pop(true);
    } on InstallmentException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = 'حدث خطأ غير متوقع: $e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final preview = _preview;
    return Scaffold(
      appBar: AppBar(title: const Text('خطة تقسيط جديدة')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.person_outline),
              title: Text(_customer?.name ?? 'اختر عميل'),
              subtitle: _customer?.phone != null ? Text(_customer!.phone!) : null,
              trailing: const Icon(Icons.chevron_left),
              onTap: _pickCustomer,
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _priceController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'السعر الإجمالي'),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _downPaymentController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'المقدم'),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _rateController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'نسبة الزيادة %'),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _termController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'عدد الأشهر'),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 20),
          if (preview != null)
            Card(
              color: Colors.indigo.shade50,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('معاينة الخطة', style: TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    _PreviewRow('المبلغ الممول', preview.baseFinanced),
                    _PreviewRow('الزيادة', preview.increase),
                    _PreviewRow('الإجمالي المستحق', preview.totalDue, bold: true),
                    _PreviewRow('القسط الشهري', preview.monthlyAmount, bold: true),
                  ],
                ),
              ),
            ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
          const SizedBox(height: 20),
          FilledButton(
            onPressed: (_submitting || preview == null) ? null : _submit,
            child: _submitting
                ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('إنشاء الخطة'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _priceController.dispose();
    _downPaymentController.dispose();
    _rateController.dispose();
    _termController.dispose();
    super.dispose();
  }
}

class _PreviewRow extends StatelessWidget {
  const _PreviewRow(this.label, this.value, {this.bold = false});
  final String label;
  final double value;
  final bool bold;
  @override
  Widget build(BuildContext context) {
    final style = TextStyle(fontWeight: bold ? FontWeight.bold : FontWeight.normal);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [Text(label, style: style), Text('${value.toStringAsFixed(2)} ج.م', style: style)],
      ),
    );
  }
}

class InstallmentPlanDetailScreen extends StatefulWidget {
  const InstallmentPlanDetailScreen({super.key, required this.repository, required this.plan});
  final InstallmentRepository repository;
  final InstallmentPlan plan;

  @override
  State<InstallmentPlanDetailScreen> createState() => _InstallmentPlanDetailScreenState();
}

class _InstallmentPlanDetailScreenState extends State<InstallmentPlanDetailScreen> {
  late Future<double> _remainingFuture;
  late Future<List<InstallmentPaymentRecord>> _paymentsFuture;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    setState(() {
      _remainingFuture = widget.repository.remaining(widget.plan.id);
      _paymentsFuture = widget.repository.listPayments(widget.plan.id);
    });
  }

  Future<void> _collect(double remaining) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (_) => _CollectPaymentDialog(repository: widget.repository, plan: widget.plan, remaining: remaining),
    );
    if (result == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    final plan = widget.plan;
    return Scaffold(
      appBar: AppBar(title: Text('خطة تقسيط • ${plan.customerName}')),
      body: FutureBuilder(
        future: Future.wait([_remainingFuture, _paymentsFuture]),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          final remaining = snapshot.data![0] as double;
          final payments = snapshot.data![1] as List<InstallmentPaymentRecord>;
          final done = remaining <= 0.01;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _PreviewRow('الإجمالي المستحق', plan.totalDue, bold: true),
                      _PreviewRow('القسط الشهري', plan.monthlyAmount),
                      _PreviewRow('المدة', plan.termMonths.toDouble()),
                      const Divider(),
                      _PreviewRow('المتبقي', remaining, bold: true),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              if (!done)
                ElevatedButton.icon(
                  onPressed: () => _collect(remaining),
                  icon: const Icon(Icons.add),
                  label: const Text('تحصيل قسط'),
                )
              else
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(color: Colors.green.shade50, borderRadius: BorderRadius.circular(8)),
                  child: const Text('تم سداد الخطة بالكامل', style: TextStyle(color: Colors.green)),
                ),
              const SizedBox(height: 20),
              const Text('سجل التحصيل', style: TextStyle(fontWeight: FontWeight.bold)),
              if (payments.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text('لا توجد دفعات محصّلة بعد'),
                )
              else
                for (final p in payments)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.check_circle_outline, color: Colors.green),
                    title: Text('${p.amount.toStringAsFixed(2)} ج.م • ${p.method.label}'),
                    subtitle: Text(_formatTime(p.paidAt)),
                  ),
            ],
          );
        },
      ),
    );
  }

  String _formatTime(DateTime t) =>
      '${t.year}-${t.month.toString().padLeft(2, '0')}-${t.day.toString().padLeft(2, '0')} '
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
}

class _CollectPaymentDialog extends StatefulWidget {
  const _CollectPaymentDialog({required this.repository, required this.plan, required this.remaining});
  final InstallmentRepository repository;
  final InstallmentPlan plan;
  final double remaining;

  @override
  State<_CollectPaymentDialog> createState() => _CollectPaymentDialogState();
}

class _CollectPaymentDialogState extends State<_CollectPaymentDialog> {
  late final TextEditingController _amountController =
      TextEditingController(text: widget.plan.monthlyAmount.clamp(0, widget.remaining).toStringAsFixed(2));
  PaymentMethod _method = PaymentMethod.cash;
  bool _submitting = false;
  String? _error;

  Future<void> _submit() async {
    final amount = double.tryParse(_amountController.text);
    if (amount == null || amount <= 0) {
      setState(() => _error = 'أدخل مبلغًا صحيحًا أكبر من صفر.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.repository.collectPayment(planId: widget.plan.id, amount: amount, method: _method);
      if (mounted) Navigator.of(context).pop(true);
    } on InstallmentException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Credit doesn't make sense when *collecting* money against an
    // installment plan, so it's left out of the picker here.
    const methods = [PaymentMethod.cash, PaymentMethod.wallet, PaymentMethod.card];
    return AlertDialog(
      title: const Text('تحصيل قسط'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('المتبقي: ${widget.remaining.toStringAsFixed(2)} ج.م'),
          const SizedBox(height: 12),
          TextField(
            controller: _amountController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'المبلغ'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<PaymentMethod>(
            value: _method,
            items: [for (final m in methods) DropdownMenuItem(value: m, child: Text(m.label))],
            onChanged: (v) => setState(() => _method = v ?? _method),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('إلغاء')),
        FilledButton(
          onPressed: _submitting ? null : _submit,
          child: _submitting
              ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('تأكيد'),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _amountController.dispose();
    super.dispose();
  }
}
