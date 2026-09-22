import 'package:flutter/material.dart';
import 'supplier_models.dart';
import 'supplier_provider.dart';
import 'supplier_repository.dart';

class SuppliersPage extends StatefulWidget {
  const SuppliersPage({super.key});

  @override
  State<SuppliersPage> createState() => _SuppliersPageState();
}

class _SuppliersPageState extends State<SuppliersPage> {
  late Future<SupplierRepository> _repositoryFuture;
  SupplierRepository? _repository;
  final _searchController = TextEditingController();
  Future<List<Supplier>>? _suppliersFuture;

  @override
  void initState() {
    super.initState();
    _repositoryFuture = getSupplierRepository();
  }

  void _reload() {
    final repo = _repository;
    if (repo == null) return;
    setState(() => _suppliersFuture = repo.listSuppliers(query: _searchController.text));
  }

  Future<void> _openForm({Supplier? existing}) async {
    final repo = _repository;
    if (repo == null) return;
    final result = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => SupplierFormSheet(repository: repo, existing: existing),
    );
    if (result == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<SupplierRepository>(
      future: _repositoryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('تعذّر تحميل الموردين\n${snapshot.error}', textAlign: TextAlign.center));
        }
        _repository = snapshot.data!;
        _suppliersFuture ??= _repository!.listSuppliers();

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
                child: FutureBuilder<List<Supplier>>(
                  future: _suppliersFuture,
                  builder: (context, supSnapshot) {
                    if (supSnapshot.connectionState != ConnectionState.done) {
                      return const Center(child: CircularProgressIndicator());
                    }
                    final suppliers = supSnapshot.data ?? const [];
                    if (suppliers.isEmpty) {
                      return const Center(child: Text('لا يوجد موردون بعد'));
                    }
                    return RefreshIndicator(
                      onRefresh: () async => _reload(),
                      child: ListView.separated(
                        itemCount: suppliers.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (context, i) {
                          final s = suppliers[i];
                          return ListTile(
                            leading: const CircleAvatar(child: Icon(Icons.local_shipping_outlined)),
                            title: Text(s.name),
                            subtitle: Text(s.phone ?? 'بدون رقم هاتف'),
                            trailing: s.active ? null : const Icon(Icons.block, color: Colors.grey, size: 18),
                            onTap: () => _openForm(existing: s),
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
            label: const Text('إضافة مورد'),
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

class SupplierFormSheet extends StatefulWidget {
  const SupplierFormSheet({super.key, required this.repository, this.existing});
  final SupplierRepository repository;
  final Supplier? existing;

  @override
  State<SupplierFormSheet> createState() => _SupplierFormSheetState();
}

class _SupplierFormSheetState extends State<SupplierFormSheet> {
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
        final updated = Supplier(
          id: widget.existing!.id,
          name: _name.text.trim(),
          phone: _phone.text.trim().isEmpty ? null : _phone.text.trim(),
          active: _active,
        );
        await widget.repository.updateSupplier(updated);
      } else {
        await widget.repository.addSupplier(name: _name.text.trim(), phone: _phone.text.trim());
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
              Text(_isEdit ? 'تعديل مورد' : 'إضافة مورد جديد', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              TextFormField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'اسم المورد'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'اسم المورد مطلوب' : null,
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
                  title: const Text('المورد مفعّل'),
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
                    : Text(_isEdit ? 'حفظ التعديلات' : 'إضافة المورد'),
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
