import 'package:flutter/material.dart';
import '../customers/customer_models.dart';
import '../customers/customer_provider.dart';
import '../customers/customers_page.dart';
import '../inventory/inventory_provider.dart';
import '../sales/sale_models.dart' show PaymentMethod, PaymentMethodX;
import '../sales/sales_page.dart' show ProductPickerScreen;
import 'maintenance_models.dart';
import 'maintenance_provider.dart';
import 'maintenance_repository.dart';

class MaintenancePage extends StatefulWidget {
  const MaintenancePage({super.key});

  @override
  State<MaintenancePage> createState() => _MaintenancePageState();
}

class _MaintenancePageState extends State<MaintenancePage> {
  late Future<MaintenanceRepository> _repositoryFuture;
  MaintenanceRepository? _repository;
  Future<List<MaintenanceTicket>>? _ticketsFuture;

  @override
  void initState() {
    super.initState();
    _repositoryFuture = getMaintenanceRepository();
  }

  void _reload() {
    final repo = _repository;
    if (repo == null) return;
    setState(() => _ticketsFuture = repo.listTickets());
  }

  Future<void> _openNewTicket(MaintenanceRepository repository) async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => NewTicketScreen(repository: repository)),
    );
    if (created == true) _reload();
  }

  Future<void> _openDetail(MaintenanceRepository repository, MaintenanceTicket ticket) async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => TicketDetailScreen(repository: repository, ticket: ticket)),
    );
    _reload();
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'DELIVERED':
        return Colors.green;
      case 'CANCELLED':
        return Colors.red;
      case 'READY':
        return Colors.blue;
      default:
        return Colors.orange;
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<MaintenanceRepository>(
      future: _repositoryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('تعذّر تحميل طلبات الصيانة\n${snapshot.error}', textAlign: TextAlign.center));
        }
        _repository = snapshot.data!;
        _ticketsFuture ??= _repository!.listTickets();

        return Scaffold(
          body: RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                ElevatedButton.icon(
                  onPressed: () => _openNewTicket(_repository!),
                  icon: const Icon(Icons.add),
                  label: const Text('طلب صيانة جديد'),
                ),
                const SizedBox(height: 16),
                FutureBuilder<List<MaintenanceTicket>>(
                  future: _ticketsFuture,
                  builder: (context, ticketsSnapshot) {
                    if (ticketsSnapshot.connectionState != ConnectionState.done) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Center(child: CircularProgressIndicator()),
                      );
                    }
                    final tickets = ticketsSnapshot.data ?? const [];
                    if (tickets.isEmpty) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Center(child: Text('لا توجد طلبات صيانة بعد')),
                      );
                    }
                    return Column(
                      children: [
                        for (final t in tickets)
                          Card(
                            child: ListTile(
                              leading: const Icon(Icons.build_outlined),
                              title: Text('${t.device} • ${t.customerName}'),
                              subtitle: Text(t.problem, maxLines: 1, overflow: TextOverflow.ellipsis),
                              trailing: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: _statusColor(t.status).withOpacity(0.12),
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: Text(
                                  t.statusLabel,
                                  style: TextStyle(color: _statusColor(t.status), fontWeight: FontWeight.bold, fontSize: 12),
                                ),
                              ),
                              onTap: () => _openDetail(_repository!, t),
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

class NewTicketScreen extends StatefulWidget {
  const NewTicketScreen({super.key, required this.repository});
  final MaintenanceRepository repository;

  @override
  State<NewTicketScreen> createState() => _NewTicketScreenState();
}

class _NewTicketScreenState extends State<NewTicketScreen> {
  Customer? _customer;
  final _deviceController = TextEditingController();
  final _imeiController = TextEditingController();
  final _problemController = TextEditingController();
  bool _submitting = false;
  String? _error;

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
      setState(() => _error = 'يجب اختيار عميل.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.repository.createTicket(
        customerId: _customer!.id,
        customerName: _customer!.name,
        device: _deviceController.text,
        imei: _imeiController.text,
        problem: _problemController.text,
      );
      if (mounted) Navigator.of(context).pop(true);
    } on MaintenanceException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = 'حدث خطأ غير متوقع: $e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('طلب صيانة جديد')),
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
          const SizedBox(height: 12),
          TextField(controller: _deviceController, decoration: const InputDecoration(labelText: 'الجهاز (مثال: iPhone 12)')),
          const SizedBox(height: 12),
          TextField(controller: _imeiController, decoration: const InputDecoration(labelText: 'IMEI (اختياري)')),
          const SizedBox(height: 12),
          TextField(
            controller: _problemController,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'وصف المشكلة', alignLabelWithHint: true),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('إنشاء الطلب'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _deviceController.dispose();
    _imeiController.dispose();
    _problemController.dispose();
    super.dispose();
  }
}

class TicketDetailScreen extends StatefulWidget {
  const TicketDetailScreen({super.key, required this.repository, required this.ticket});
  final MaintenanceRepository repository;
  final MaintenanceTicket ticket;

  @override
  State<TicketDetailScreen> createState() => _TicketDetailScreenState();
}

class _TicketDetailScreenState extends State<TicketDetailScreen> {
  late MaintenanceTicket _ticket;
  Future<List<MaintenancePartUsage>>? _partsFuture;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _ticket = widget.ticket;
    _reloadParts();
  }

  void _reloadParts() {
    setState(() => _partsFuture = widget.repository.listPartsUsed(_ticket.id));
  }

  Future<void> _refreshTicket() async {
    final tickets = await widget.repository.listTickets();
    final fresh = tickets.where((t) => t.id == _ticket.id).cast<MaintenanceTicket?>().firstOrNull;
    if (fresh != null && mounted) setState(() => _ticket = fresh);
  }

  Future<void> _advance() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final updated = await widget.repository.advanceStatus(_ticket.id);
      setState(() => _ticket = updated);
    } on MaintenanceException catch (e) {
      setState(() => _error = e.message);
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _cancel() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('تأكيد الإلغاء'),
        content: const Text('هل تريد إلغاء طلب الصيانة هذا؟'),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('تراجع')),
          FilledButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('تأكيد الإلغاء')),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _busy = true);
    try {
      final updated = await widget.repository.cancelTicket(_ticket.id);
      setState(() => _ticket = updated);
    } on MaintenanceException catch (e) {
      setState(() => _error = e.message);
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _addPart() async {
    final inventoryRepository = await getInventoryRepository();
    if (!mounted) return;
    final product = await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ProductPickerScreen(repository: inventoryRepository)),
    );
    if (product == null) return;
    final quantity = await _askQuantity();
    if (quantity == null || quantity <= 0) return;
    setState(() => _busy = true);
    try {
      await widget.repository.usePart(
        ticketId: _ticket.id, productId: product.id, productName: product.name,
        quantity: quantity, cost: product.defaultCost,
      );
      _reloadParts();
      await _refreshTicket();
    } on MaintenanceException catch (e) {
      setState(() => _error = e.message);
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<int?> _askQuantity() {
    final controller = TextEditingController(text: '1');
    return showDialog<int>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('الكمية المستخدمة'),
        content: TextField(controller: controller, keyboardType: TextInputType.number, autofocus: true),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('إلغاء')),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(int.tryParse(controller.text)),
            child: const Text('تأكيد'),
          ),
        ],
      ),
    );
  }

  Future<void> _deliver() async {
    final result = await showDialog<bool>(
      context: context,
      builder: (_) => DeliverDialog(repository: widget.repository, ticket: _ticket),
    );
    if (result == true) await _refreshTicket();
  }

  @override
  Widget build(BuildContext context) {
    final t = _ticket;
    return Scaffold(
      appBar: AppBar(title: Text('صيانة • ${t.device}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.person_outline),
            title: Text(t.customerName),
          ),
          ListTile(contentPadding: EdgeInsets.zero, title: Text('المشكلة: ${t.problem}')),
          if (t.imei != null) ListTile(contentPadding: EdgeInsets.zero, title: Text('IMEI: ${t.imei}')),
          const Divider(),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('الحالة: ${t.statusLabel}', style: const TextStyle(fontWeight: FontWeight.bold)),
              if (t.isOpen && t.nextStatus != null)
                FilledButton(
                  onPressed: _busy ? null : _advance,
                  child: Text('التالي: ${maintenanceStatusLabels[t.nextStatus]}'),
                ),
            ],
          ),
          if (t.isOpen) ...[
            const SizedBox(height: 8),
            OutlinedButton(
              onPressed: _busy ? null : _cancel,
              style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
              child: const Text('إلغاء الطلب'),
            ),
          ],
          const Divider(height: 32),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('القطع المستخدمة', style: TextStyle(fontWeight: FontWeight.bold)),
              if (t.isOpen)
                TextButton.icon(onPressed: _busy ? null : _addPart, icon: const Icon(Icons.add), label: const Text('إضافة قطعة')),
            ],
          ),
          FutureBuilder<List<MaintenancePartUsage>>(
            future: _partsFuture,
            builder: (context, snapshot) {
              final parts = snapshot.data ?? const [];
              if (parts.isEmpty) return const Padding(padding: EdgeInsets.all(8), child: Text('لا توجد قطع مستخدمة بعد'));
              return Column(
                children: [
                  for (final p in parts)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(p.productName),
                      subtitle: Text('${p.cost.toStringAsFixed(2)} ج.م × ${p.quantity}'),
                      trailing: Text('${p.total.toStringAsFixed(2)} ج.م'),
                    ),
                ],
              );
            },
          ),
          Text('إجمالي تكلفة القطع: ${t.partsCost.toStringAsFixed(2)} ج.م', style: const TextStyle(fontWeight: FontWeight.bold)),
          if (t.status == 'DELIVERED') ...[
            const Divider(height: 32),
            Text('السعر النهائي: ${t.finalCost.toStringAsFixed(2)} ج.م'),
            Text('المدفوع: ${t.payment.toStringAsFixed(2)} ج.م'),
          ],
          if (t.status == 'READY') ...[
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: _busy ? null : _deliver,
              icon: const Icon(Icons.check_circle_outline),
              label: const Text('تسليم الجهاز'),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
        ],
      ),
    );
  }
}

class DeliverDialog extends StatefulWidget {
  const DeliverDialog({super.key, required this.repository, required this.ticket});
  final MaintenanceRepository repository;
  final MaintenanceTicket ticket;

  @override
  State<DeliverDialog> createState() => _DeliverDialogState();
}

class _DeliverDialogState extends State<DeliverDialog> {
  final _priceController = TextEditingController();
  final _paymentController = TextEditingController();
  PaymentMethod _method = PaymentMethod.cash;
  bool _submitting = false;
  String? _error;

  Future<void> _submit() async {
    final price = double.tryParse(_priceController.text);
    final payment = double.tryParse(_paymentController.text);
    if (price == null || payment == null) {
      setState(() => _error = 'أدخل أرقامًا صحيحة.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.repository.deliverTicket(
        ticketId: widget.ticket.id, finalPrice: price, payment: payment, method: _method,
      );
      if (mounted) Navigator.of(context).pop(true);
    } on MaintenanceException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('تسليم الجهاز'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('تكلفة القطع المستخدمة: ${widget.ticket.partsCost.toStringAsFixed(2)} ج.م'),
          const SizedBox(height: 12),
          TextField(
            controller: _priceController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'السعر النهائي'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _paymentController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'المبلغ المدفوع الآن'),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<PaymentMethod>(
            value: _method,
            decoration: const InputDecoration(labelText: 'طريقة الدفع'),
            items: [for (final m in PaymentMethod.values) DropdownMenuItem(value: m, child: Text(m.label))],
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
              : const Text('تأكيد التسليم'),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _priceController.dispose();
    _paymentController.dispose();
    super.dispose();
  }
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
