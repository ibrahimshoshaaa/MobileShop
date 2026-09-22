import 'package:flutter/material.dart';
import '../customers/customer_models.dart';
import '../customers/customer_provider.dart';
import '../customers/customers_page.dart';
import '../inventory/inventory_models.dart';
import '../inventory/inventory_provider.dart';
import '../inventory/inventory_repository.dart';
import 'sale_models.dart';
import 'sale_repository.dart';
import 'sales_provider.dart';

class SalesPage extends StatefulWidget {
  const SalesPage({super.key});

  @override
  State<SalesPage> createState() => _SalesPageState();
}

class _SalesPageState extends State<SalesPage> {
  late Future<SalesRepository> _repositoryFuture;
  Future<List<SaleRecord>>? _salesFuture;
  SalesRepository? _repository;

  @override
  void initState() {
    super.initState();
    _repositoryFuture = getSalesRepository();
  }

  void _reloadSales() {
    final repo = _repository;
    if (repo == null) return;
    setState(() => _salesFuture = repo.listRecentSales());
  }

  Future<void> _openNewSale(SalesRepository repository) async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => NewSaleScreen(repository: repository)),
    );
    if (created == true) _reloadSales();
  }

  Future<void> _openDetail(SalesRepository repository, SaleRecord sale) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => SaleDetailScreen(repository: repository, sale: sale)),
    );
    if (changed == true) _reloadSales();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<SalesRepository>(
      future: _repositoryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('تعذّر تحميل المبيعات\n${snapshot.error}', textAlign: TextAlign.center));
        }
        _repository = snapshot.data!;
        _salesFuture ??= _repository!.listRecentSales();

        return RefreshIndicator(
          onRefresh: () async => _reloadSales(),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              ElevatedButton.icon(
                onPressed: () => _openNewSale(_repository!),
                icon: const Icon(Icons.add),
                label: const Text('فاتورة بيع جديدة'),
              ),
              const SizedBox(height: 20),
              const Text('آخر الفواتير', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              FutureBuilder<List<SaleRecord>>(
                future: _salesFuture,
                builder: (context, salesSnapshot) {
                  if (salesSnapshot.connectionState != ConnectionState.done) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 24),
                      child: Center(child: CircularProgressIndicator()),
                    );
                  }
                  final sales = salesSnapshot.data ?? const [];
                  if (sales.isEmpty) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 24),
                      child: Center(child: Text('لا توجد فواتير بعد')),
                    );
                  }
                  return Column(
                    children: [
                      for (final sale in sales)
                        Card(
                          child: ListTile(
                            leading: Icon(
                              sale.status == 'VOIDED' ? Icons.cancel_outlined : Icons.receipt_long,
                              color: sale.status == 'VOIDED' ? Colors.red : null,
                            ),
                            title: Text('فاتورة #${sale.id.substring(sale.id.length - 6)} • ${sale.items.length} صنف'),
                            subtitle: Text(
                              '${sale.total.toStringAsFixed(2)} ج.م • ${_formatTime(sale.createdAt)}'
                              '${sale.customerName != null ? ' • ${sale.customerName}' : ''}'
                              '${sale.status == 'VOIDED' ? ' • ملغاة' : ''}',
                            ),
                            trailing: const Icon(Icons.chevron_left),
                            onTap: () => _openDetail(_repository!, sale),
                          ),
                        ),
                    ],
                  );
                },
              ),
            ],
          ),
        );
      },
    );
  }

  String _formatTime(DateTime t) =>
      '${t.year}-${t.month.toString().padLeft(2, '0')}-${t.day.toString().padLeft(2, '0')} '
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
}

class _CartLine {
  _CartLine(this.product) : unitPrice = product.sellingPrice;
  final Product product;
  int quantity = 1;
  double unitPrice;
  double get lineTotal => quantity * unitPrice;
}

class _PaymentRow {
  _PaymentRow({required this.method, required double amount}) : amountController = TextEditingController(text: amount.toStringAsFixed(2));
  PaymentMethod method;
  final TextEditingController amountController;
  double get amount => double.tryParse(amountController.text) ?? 0;
  void dispose() => amountController.dispose();
}

class NewSaleScreen extends StatefulWidget {
  const NewSaleScreen({super.key, required this.repository});
  final SalesRepository repository;

  @override
  State<NewSaleScreen> createState() => _NewSaleScreenState();
}

class _NewSaleScreenState extends State<NewSaleScreen> {
  final List<_CartLine> _cart = [];
  final List<_PaymentRow> _payments = [];
  final _discountController = TextEditingController(text: '0');
  Customer? _customer;
  bool _submitting = false;
  String? _error;

  double get _subtotal => _cart.fold(0, (sum, l) => sum + l.lineTotal);
  double get _discount => double.tryParse(_discountController.text) ?? 0;
  double get _total => (_subtotal - _discount).clamp(0, double.infinity);
  double get _paid => _payments.fold(0, (sum, p) => sum + p.amount);
  double get _remaining => _total - _paid;

  Future<void> _addProduct() async {
    final inventoryRepository = await getInventoryRepository();
    if (!mounted) return;
    final product = await Navigator.of(context).push<Product>(
      MaterialPageRoute(builder: (_) => ProductPickerScreen(repository: inventoryRepository)),
    );
    if (product == null) return;
    setState(() {
      final existing = _cart.where((l) => l.product.id == product.id).toList();
      if (existing.isNotEmpty) {
        existing.first.quantity += 1;
      } else {
        _cart.add(_CartLine(product));
      }
    });
  }

  void _addPaymentRow() {
    setState(() {
      _payments.add(_PaymentRow(method: PaymentMethod.cash, amount: _remaining > 0 ? _remaining : 0));
    });
  }

  Future<void> _pickCustomer() async {
    final customerRepository = await getCustomerRepository();
    if (!mounted) return;
    final customer = await Navigator.of(context).push<Customer>(
      MaterialPageRoute(builder: (_) => CustomerPickerScreen(repository: customerRepository)),
    );
    // A null result here means either "بدون عميل" was tapped or the picker
    // was dismissed — both should clear the current selection.
    setState(() => _customer = customer);
  }

  Future<void> _submit() async {
    if (_cart.isEmpty) {
      setState(() => _error = 'أضف صنفًا واحدًا على الأقل.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.repository.createSale(
        items: _cart
            .map((l) => SaleItemRecord(
                  productId: l.product.id,
                  productName: l.product.name,
                  quantity: l.quantity,
                  unitPrice: l.unitPrice,
                  // Placeholder — SqliteSalesRepository.createSale snapshots the
                  // authoritative cost itself right before committing, using
                  // the product's cost at that exact moment (see 1.4).
                  costAtSale: l.product.defaultCost,
                ))
            .toList(),
        payments: _payments.map((p) => PaymentEntry(method: p.method, amount: p.amount)).toList(),
        customerId: _customer?.id,
        customerName: _customer?.name,
        discount: _discount,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('تم إتمام البيع بنجاح')));
        Navigator.of(context).pop(true);
      }
    } on SalesException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = 'حدث خطأ غير متوقع: $e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final remainingOk = _remaining.abs() <= 0.01;
    return Scaffold(
      appBar: AppBar(title: const Text('فاتورة بيع جديدة')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.person_outline),
              title: Text(_customer?.name ?? 'بدون عميل (عميل نقدي)'),
              subtitle: _customer?.phone != null ? Text(_customer!.phone!) : null,
              trailing: const Icon(Icons.chevron_left),
              onTap: _pickCustomer,
            ),
          ),
          const SizedBox(height: 8),
          if (_cart.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(child: Text('لا توجد أصناف في الفاتورة بعد')),
            )
          else
            for (final line in _cart)
              Card(
                child: ListTile(
                  title: Text(line.product.name),
                  subtitle: Text('${line.unitPrice.toStringAsFixed(2)} ج.م × ${line.quantity} = ${line.lineTotal.toStringAsFixed(2)} ج.م'),
                  leading: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.add_circle_outline),
                        onPressed: () => setState(() => line.quantity += 1),
                      ),
                      Text('${line.quantity}'),
                      IconButton(
                        icon: const Icon(Icons.remove_circle_outline),
                        onPressed: () => setState(() {
                          if (line.quantity > 1) {
                            line.quantity -= 1;
                          } else {
                            _cart.remove(line);
                          }
                        }),
                      ),
                    ],
                  ),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => setState(() => _cart.remove(line)),
                  ),
                ),
              ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _addProduct,
            icon: const Icon(Icons.add),
            label: const Text('إضافة منتج'),
          ),
          const Divider(height: 32),
          TextField(
            controller: _discountController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'الخصم'),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          _SummaryRow(label: 'الإجمالي الفرعي', value: _subtotal),
          _SummaryRow(label: 'الخصم', value: -_discount),
          const Divider(),
          _SummaryRow(label: 'الإجمالي', value: _total, bold: true),
          const Divider(height: 32),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('طرق الدفع', style: TextStyle(fontWeight: FontWeight.bold)),
              TextButton.icon(onPressed: _addPaymentRow, icon: const Icon(Icons.add), label: const Text('إضافة دفعة')),
            ],
          ),
          for (final row in _payments)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: DropdownButtonFormField<PaymentMethod>(
                      value: row.method,
                      items: [for (final m in PaymentMethod.values) DropdownMenuItem(value: m, child: Text(m.label))],
                      onChanged: (v) => setState(() => row.method = v ?? row.method),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: row.amountController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(labelText: 'المبلغ'),
                      onChanged: (_) => setState(() {}),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => setState(() {
                      row.dispose();
                      _payments.remove(row);
                    }),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 8),
          Text(
            remainingOk ? 'المدفوع يساوي الإجمالي ✓' : 'المتبقي: ${_remaining.toStringAsFixed(2)} ج.م',
            style: TextStyle(color: remainingOk ? Colors.green.shade700 : Colors.red.shade700, fontWeight: FontWeight.bold),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
          const SizedBox(height: 20),
          FilledButton(
            onPressed: (_submitting || _cart.isEmpty || !remainingOk) ? null : _submit,
            child: _submitting
                ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('إتمام البيع'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _discountController.dispose();
    for (final row in _payments) {
      row.dispose();
    }
    super.dispose();
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({required this.label, required this.value, this.bold = false});
  final String label;
  final double value;
  final bool bold;
  @override
  Widget build(BuildContext context) {
    final style = TextStyle(fontWeight: bold ? FontWeight.bold : FontWeight.normal, fontSize: bold ? 17 : 14);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [Text(label, style: style), Text('${value.toStringAsFixed(2)} ج.م', style: style)],
      ),
    );
  }
}

class ProductPickerScreen extends StatefulWidget {
  const ProductPickerScreen({super.key, required this.repository});
  final InventoryRepository repository;

  @override
  State<ProductPickerScreen> createState() => _ProductPickerScreenState();
}

class _ProductPickerScreenState extends State<ProductPickerScreen> {
  final _searchController = TextEditingController();
  late Future<List<Product>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.repository.listProducts();
  }

  void _reload() => setState(() => _future = widget.repository.listProducts(query: _searchController.text));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('اختيار صنف')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _searchController,
              autofocus: true,
              decoration: InputDecoration(
                hintText: 'ابحث بالاسم أو SKU أو الباركود',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                isDense: true,
              ),
              onChanged: (_) => _reload(),
            ),
          ),
          Expanded(
            child: FutureBuilder<List<Product>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                final products = (snapshot.data ?? const []).where((p) => p.active).toList();
                if (products.isEmpty) {
                  return const Center(child: Text('لا توجد أصناف مطابقة'));
                }
                return ListView.separated(
                  itemCount: products.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final p = products[i];
                    final canSell = p.type == ProductType.service || p.quantity > 0;
                    return ListTile(
                      enabled: canSell,
                      title: Text(p.name),
                      subtitle: Text('${p.sellingPrice.toStringAsFixed(2)} ج.م'
                          '${p.type == ProductType.service ? '' : ' • المتاح: ${p.quantity}'}'),
                      onTap: canSell ? () => Navigator.of(context).pop(p) : null,
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }
}

class SaleDetailScreen extends StatefulWidget {
  const SaleDetailScreen({super.key, required this.repository, required this.sale});
  final SalesRepository repository;
  final SaleRecord sale;

  @override
  State<SaleDetailScreen> createState() => _SaleDetailScreenState();
}

class _SaleDetailScreenState extends State<SaleDetailScreen> {
  bool _submitting = false;
  String? _error;

  Future<void> _void() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.repository.voidSale(widget.sale.id);
      if (mounted) Navigator.of(context).pop(true);
    } on SalesException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sale = widget.sale;
    return Scaffold(
      appBar: AppBar(title: Text('فاتورة #${sale.id.substring(sale.id.length - 6)}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (sale.status == 'VOIDED')
            Container(
              padding: const EdgeInsets.all(10),
              margin: const EdgeInsets.only(bottom: 12),
              decoration: BoxDecoration(color: Colors.red.shade50, borderRadius: BorderRadius.circular(8)),
              child: const Text('هذه الفاتورة ملغاة', style: TextStyle(color: Colors.red)),
            ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.person_outline),
            title: Text(sale.customerName ?? 'بدون عميل (عميل نقدي)'),
          ),
          const Divider(),
          const Text('الأصناف', style: TextStyle(fontWeight: FontWeight.bold)),
          for (final item in sale.items)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(item.productName),
              subtitle: Text('${item.unitPrice.toStringAsFixed(2)} ج.م × ${item.quantity}'),
              trailing: Text('${item.lineTotal.toStringAsFixed(2)} ج.م'),
            ),
          const Divider(),
          _SummaryRow(label: 'الإجمالي الفرعي', value: sale.subtotal),
          _SummaryRow(label: 'الخصم', value: -sale.discount),
          _SummaryRow(label: 'الإجمالي', value: sale.total, bold: true),
          const Divider(height: 32),
          const Text('طرق الدفع', style: TextStyle(fontWeight: FontWeight.bold)),
          for (final payment in sale.payments)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.payments_outlined),
              title: Text(payment.method.label),
              trailing: Text('${payment.amount.toStringAsFixed(2)} ج.م'),
            ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
          if (sale.status != 'VOIDED') ...[
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: _submitting ? null : _void,
              icon: const Icon(Icons.cancel_outlined, color: Colors.red),
              label: Text(_submitting ? 'جاري الإلغاء...' : 'إلغاء الفاتورة', style: const TextStyle(color: Colors.red)),
            ),
          ],
        ],
      ),
    );
  }
}
