import 'package:flutter/material.dart';
import '../sales/sale_models.dart' show PaymentMethod, PaymentMethodX;
import 'expense_models.dart';
import 'expense_provider.dart';
import 'expense_repository.dart';

class ExpensesPage extends StatefulWidget {
  const ExpensesPage({super.key});

  @override
  State<ExpensesPage> createState() => _ExpensesPageState();
}

class _ExpensesPageState extends State<ExpensesPage> {
  late Future<ExpenseRepository> _repositoryFuture;
  ExpenseRepository? _repository;
  Future<List<Expense>>? _expensesFuture;
  Future<double>? _todayTotalFuture;

  @override
  void initState() {
    super.initState();
    _repositoryFuture = getExpenseRepository();
  }

  void _reload() {
    final repo = _repository;
    if (repo == null) return;
    setState(() {
      _expensesFuture = repo.listExpenses();
      _todayTotalFuture = repo.totalForToday();
    });
  }

  Future<void> _addExpense(ExpenseRepository repository) async {
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => ExpenseFormSheet(repository: repository),
    );
    if (added == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<ExpenseRepository>(
      future: _repositoryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('تعذّر تحميل المصروفات\n${snapshot.error}', textAlign: TextAlign.center));
        }
        _repository = snapshot.data!;
        _expensesFuture ??= _repository!.listExpenses();
        _todayTotalFuture ??= _repository!.totalForToday();

        return Scaffold(
          body: RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Card(
                  color: Colors.deepOrange.shade50,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: FutureBuilder<double>(
                      future: _todayTotalFuture,
                      builder: (context, totalSnapshot) {
                        final total = totalSnapshot.data ?? 0;
                        return Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('إجمالي مصروفات اليوم', style: TextStyle(fontWeight: FontWeight.bold)),
                            Text('${total.toStringAsFixed(2)} ج.م',
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                          ],
                        );
                      },
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                ElevatedButton.icon(
                  onPressed: () => _addExpense(_repository!),
                  icon: const Icon(Icons.add),
                  label: const Text('إضافة مصروف'),
                ),
                const SizedBox(height: 16),
                const Text('سجل المصروفات', style: TextStyle(fontWeight: FontWeight.bold)),
                FutureBuilder<List<Expense>>(
                  future: _expensesFuture,
                  builder: (context, expSnapshot) {
                    if (expSnapshot.connectionState != ConnectionState.done) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Center(child: CircularProgressIndicator()),
                      );
                    }
                    final expenses = expSnapshot.data ?? const [];
                    if (expenses.isEmpty) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Center(child: Text('لا توجد مصروفات مسجّلة بعد')),
                      );
                    }
                    return Column(
                      children: [
                        for (final e in expenses)
                          Card(
                            child: ListTile(
                              leading: const Icon(Icons.receipt_long),
                              title: Text('${e.category} • ${e.amount.toStringAsFixed(2)} ج.م'),
                              subtitle: Text(
                                '${e.method.label} • ${_formatTime(e.createdAt)}'
                                '${e.note != null ? '\n${e.note}' : ''}',
                              ),
                              isThreeLine: e.note != null,
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

  String _formatTime(DateTime t) =>
      '${t.year}-${t.month.toString().padLeft(2, '0')}-${t.day.toString().padLeft(2, '0')} '
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
}

class ExpenseFormSheet extends StatefulWidget {
  const ExpenseFormSheet({super.key, required this.repository});
  final ExpenseRepository repository;

  @override
  State<ExpenseFormSheet> createState() => _ExpenseFormSheetState();
}

class _ExpenseFormSheetState extends State<ExpenseFormSheet> {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _noteController = TextEditingController();
  String _category = expenseCategories.first;
  PaymentMethod _method = PaymentMethod.cash;
  bool _submitting = false;
  String? _error;

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.repository.addExpense(
        amount: double.parse(_amountController.text),
        category: _category,
        method: _method,
        note: _noteController.text,
      );
      if (mounted) Navigator.of(context).pop(true);
    } on ExpenseException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = 'حدث خطأ غير متوقع: $e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Form(
        key: _formKey,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('إضافة مصروف', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _category,
                decoration: const InputDecoration(labelText: 'التصنيف'),
                items: [for (final c in expenseCategories) DropdownMenuItem(value: c, child: Text(c))],
                onChanged: (v) => setState(() => _category = v ?? _category),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _amountController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'المبلغ'),
                validator: (v) {
                  final n = double.tryParse(v ?? '');
                  if (n == null || n <= 0) return 'أدخل مبلغًا صحيحًا أكبر من صفر';
                  return null;
                },
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<PaymentMethod>(
                value: _method,
                decoration: const InputDecoration(labelText: 'دُفع من'),
                items: [for (final m in PaymentMethod.values) DropdownMenuItem(value: m, child: Text(m.label))],
                onChanged: (v) => setState(() => _method = v ?? _method),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _noteController,
                decoration: const InputDecoration(labelText: 'ملاحظة (اختياري)'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _submitting ? null : _submit,
                child: _submitting
                    ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('إضافة'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _amountController.dispose();
    _noteController.dispose();
    super.dispose();
  }
}
