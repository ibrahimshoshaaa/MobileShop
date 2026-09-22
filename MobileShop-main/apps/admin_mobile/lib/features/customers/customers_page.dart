import 'package:flutter/material.dart';
import 'customer_models.dart';
import 'customer_provider.dart';
import 'customer_repository.dart';

class CustomersPage extends StatefulWidget {
  const CustomersPage({super.key});

  @override
  State<CustomersPage> createState() => _CustomersPageState();
}

class _CustomersPageState extends State<CustomersPage> {
  late Future<CustomerRepository> _repositoryFuture;
  CustomerRepository? _repository;
  final _searchController = TextEditingController();
  Future<List<Customer>>? _customersFuture;

  @override
  void initState() {
    super.initState();
    _repositoryFuture = getCustomerRepository();
  }

  void _reload() {
    final repo = _repository;
    if (repo == null) return;
    setState(() => _customersFuture = repo.listCustomers(query: _searchController.text));
  }

  Future<void> _openForm({Customer? existing}) async {
    final repo = _repository;
    if (repo == null) return;
    final result = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => CustomerFormSheet(repository: repo, existing: existing),
    );
    if (result == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<CustomerRepository>(
      future: _repositoryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('تعذّر تحميل العملاء\n${snapshot.error}', textAlign: TextAlign.center));
        }
        _repository = snapshot.data!;
        _customersFuture ??= _repository!.listCustomers();

        return Scaffold(
          body: Column(
            children: [
              Padding(
                padding: const EdgeInsets.all(12),
                child: TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'ابحث بالاسم أو رقم الهاتف',
                    prefixIcon: const Icon(Icons.search),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    isDense: true,
                  ),
                  onChanged: (_) => _reload(),
                ),
              ),
              Expanded(
                child: FutureBuilder<List<Customer>>(
                  future: _customersFuture,
                  builder: (context, custSnapshot) {
                    if (custSnapshot.connectionState != ConnectionState.done) {
                      return const Center(child: CircularProgressIndicator());
                    }
                    final customers = custSnapshot.data ?? const [];
                    if (customers.isEmpty) {
                      return const Center(child: Text('لا يوجد عملاء بعد'));
                    }
                    return RefreshIndicator(
                      onRefresh: () async => _reload(),
                      child: ListView.separated(
                        itemCount: customers.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (context, i) {
                          final c = customers[i];
                          return ListTile(
                            leading: const CircleAvatar(child: Icon(Icons.person_outline)),
                            title: Text(c.name),
                            subtitle: Text(c.phone ?? 'بدون رقم هاتف'),
                            trailing: c.active ? null : const Icon(Icons.block, color: Colors.grey, size: 18),
                            onTap: () => _openForm(existing: c),
                          );
                        },
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
          floatingActionButton: FloatingActionButton.extended(
            onPressed: () => _openForm(),
            icon: const Icon(Icons.add),
            label: const Text('إضافة عميل'),
          ),
        );
      },
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }
}

class CustomerFormSheet extends StatefulWidget {
  const CustomerFormSheet({super.key, required this.repository, this.existing});
  final CustomerRepository repository;
  final Customer? existing;

  @override
  State<CustomerFormSheet> createState() => _CustomerFormSheetState();
}

class _CustomerFormSheetState extends State<CustomerFormSheet> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _phone;
  bool _active = true;
  bool _submitting = false;
  String? _error;

  bool get _isEdit => widget.existing != null;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.existing?.name ?? '');
    _phone = TextEditingController(text: widget.existing?.phone ?? '');
    _active = widget.existing?.active ?? true;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      if (_isEdit) {
        final updated = Customer(
          id: widget.existing!.id,
          name: _name.text.trim(),
          phone: _phone.text.trim().isEmpty ? null : _phone.text.trim(),
          active: _active,
        );
        await widget.repository.updateCustomer(updated);
      } else {
        await widget.repository.addCustomer(
          name: _name.text.trim(),
          phone: _phone.text.trim().isEmpty ? null : _phone.text.trim(),
        );
      }
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      setState(() => _error = e.toString());
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
              Text(_isEdit ? 'تعديل عميل' : 'إضافة عميل جديد', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              TextFormField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'اسم العميل'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'اسم العميل مطلوب' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _phone,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(labelText: 'رقم الهاتف (اختياري)'),
              ),
              if (_isEdit) ...[
                const SizedBox(height: 8),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: _active,
                  onChanged: (v) => setState(() => _active = v),
                  title: const Text('العميل مفعّل'),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _submitting ? null : _submit,
                child: _submitting
                    ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : Text(_isEdit ? 'حفظ التعديلات' : 'إضافة العميل'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    super.dispose();
  }
}

/// Lightweight picker used from the sales flow. Returns the selected
/// [Customer], or `null` via the "بدون عميل" action for a walk-in sale.
class CustomerPickerScreen extends StatefulWidget {
  const CustomerPickerScreen({super.key, required this.repository});
  final CustomerRepository repository;

  @override
  State<CustomerPickerScreen> createState() => _CustomerPickerScreenState();
}

class _CustomerPickerScreenState extends State<CustomerPickerScreen> {
  final _searchController = TextEditingController();
  late Future<List<Customer>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.repository.listCustomers();
  }

  void _reload() => setState(() => _future = widget.repository.listCustomers(query: _searchController.text));

  Future<void> _addNew() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => CustomerFormSheet(repository: widget.repository),
    );
    if (created == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('اختيار عميل')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _searchController,
                    autofocus: true,
                    decoration: InputDecoration(
                      hintText: 'ابحث بالاسم أو رقم الهاتف',
                      prefixIcon: const Icon(Icons.search),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      isDense: true,
                    ),
                    onChanged: (_) => _reload(),
                  ),
                ),
                IconButton(onPressed: _addNew, icon: const Icon(Icons.person_add_alt)),
              ],
            ),
          ),
          ListTile(
            leading: const Icon(Icons.person_off_outlined),
            title: const Text('بدون عميل (عميل نقدي)'),
            onTap: () => Navigator.of(context).pop(),
          ),
          const Divider(height: 1),
          Expanded(
            child: FutureBuilder<List<Customer>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                final customers = (snapshot.data ?? const []).where((c) => c.active).toList();
                if (customers.isEmpty) {
                  return const Center(child: Text('لا يوجد عملاء مطابقين'));
                }
                return ListView.separated(
                  itemCount: customers.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final c = customers[i];
                    return ListTile(
                      leading: const CircleAvatar(child: Icon(Icons.person_outline)),
                      title: Text(c.name),
                      subtitle: Text(c.phone ?? ''),
                      onTap: () => Navigator.of(context).pop(c),
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
