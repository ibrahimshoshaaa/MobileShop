import 'package:flutter/material.dart';
import 'inventory_models.dart';
import 'inventory_provider.dart';
import 'inventory_repository.dart';

/// Loads the (SQLite-backed) inventory repository once, then shows the
/// category list. A previous version of this screen used an in-memory
/// repository that reset every app launch — this now persists to disk.
class InventoryPage extends StatefulWidget {
  const InventoryPage({super.key});

  @override
  State<InventoryPage> createState() => _InventoryPageState();
}

class _InventoryPageState extends State<InventoryPage> {
  late Future<InventoryRepository> _repositoryFuture;

  @override
  void initState() {
    super.initState();
    _repositoryFuture = getInventoryRepository();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<InventoryRepository>(
      future: _repositoryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return _ErrorState(
            message: snapshot.error.toString(),
            onRetry: () => setState(() => _repositoryFuture = getInventoryRepository()),
          );
        }
        return _InventoryCategoryList(repository: snapshot.data!);
      },
    );
  }
}

class _InventoryCategoryList extends StatelessWidget {
  const _InventoryCategoryList({required this.repository});

  final InventoryRepository repository;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('أقسام المخزون', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        const Text('اضغط على القسم لعرض الأصناف والكميات، أو استخدم البحث الشامل بالأسفل.',
            style: TextStyle(color: Colors.black54)),
        const SizedBox(height: 12),
        for (final type in ProductType.values)
          Card(
            child: ListTile(
              leading: Icon(type.icon),
              title: Text(type.label),
              subtitle: const Text('عرض الأصناف والكميات وتعديل المخزون'),
              trailing: const Icon(Icons.chevron_left),
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => ProductListScreen(repository: repository, type: type),
              )),
            ),
          ),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          icon: const Icon(Icons.search),
          label: const Text('بحث في كل الأصناف'),
          onPressed: () => Navigator.of(context).push(MaterialPageRoute(
            builder: (_) => ProductListScreen(repository: repository, type: null),
          )),
        ),
      ],
    );
  }
}

class ProductListScreen extends StatefulWidget {
  const ProductListScreen({super.key, required this.repository, required this.type});
  final InventoryRepository repository;
  final ProductType? type;

  @override
  State<ProductListScreen> createState() => _ProductListScreenState();
}

class _ProductListScreenState extends State<ProductListScreen> {
  final _searchController = TextEditingController();
  late Future<List<Product>> _future;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    setState(() {
      _future = widget.repository.listProducts(type: widget.type, query: _searchController.text);
    });
  }

  Future<void> _openForm({Product? existing}) async {
    final result = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => ProductFormSheet(
        repository: widget.repository,
        existing: existing,
        defaultType: widget.type,
      ),
    );
    if (result == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.type?.label ?? 'كل الأصناف';
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _searchController,
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
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return _ErrorState(message: snapshot.error.toString(), onRetry: _reload);
                }
                final products = snapshot.data ?? const [];
                if (products.isEmpty) {
                  return const _EmptyState();
                }
                return RefreshIndicator(
                  onRefresh: () async => _reload(),
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    itemCount: products.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 6),
                    itemBuilder: (context, i) {
                      final p = products[i];
                      return ProductTile(
                        product: p,
                        onTap: () => _openForm(existing: p),
                        onAdjustStock: () async {
                          final changed = await showDialog<bool>(
                            context: context,
                            builder: (_) => StockAdjustDialog(repository: widget.repository, product: p),
                          );
                          if (changed == true) _reload();
                        },
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
        label: const Text('إضافة صنف'),
      ),
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }
}

class ProductTile extends StatelessWidget {
  const ProductTile({super.key, required this.product, required this.onTap, required this.onAdjustStock});
  final Product product;
  final VoidCallback onTap;
  final VoidCallback onAdjustStock;

  @override
  Widget build(BuildContext context) {
    final lowStock = product.isLowStock && product.type != ProductType.service;
    return Card(
      child: ListTile(
        onTap: onTap,
        leading: CircleAvatar(child: Icon(product.type.icon)),
        title: Text(product.name, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(
          'SKU: ${product.sku}'
          '${product.barcode != null ? ' • باركود: ${product.barcode}' : ''}'
          '\n${product.sellingPrice.toStringAsFixed(2)} ج.م',
        ),
        isThreeLine: true,
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: lowStock ? Colors.red.withOpacity(0.12) : Colors.green.withOpacity(0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                'الكمية: ${product.quantity}',
                style: TextStyle(
                  color: lowStock ? Colors.red.shade700 : Colors.green.shade700,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ),
            TextButton(onPressed: onAdjustStock, child: const Text('تعديل الرصيد')),
          ],
        ),
      ),
    );
  }
}

class ProductFormSheet extends StatefulWidget {
  const ProductFormSheet({super.key, required this.repository, this.existing, this.defaultType});
  final InventoryRepository repository;
  final Product? existing;
  final ProductType? defaultType;

  @override
  State<ProductFormSheet> createState() => _ProductFormSheetState();
}

class _ProductFormSheetState extends State<ProductFormSheet> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _sku;
  late final TextEditingController _barcode;
  late final TextEditingController _sellingPrice;
  late final TextEditingController _defaultCost;
  late final TextEditingController _reorderLevel;
  late final TextEditingController _openingQuantity;
  late ProductType _type;
  bool _active = true;
  bool _submitting = false;
  String? _errorText;

  bool get _isEdit => widget.existing != null;

  @override
  void initState() {
    super.initState();
    final p = widget.existing;
    _name = TextEditingController(text: p?.name ?? '');
    _sku = TextEditingController(text: p?.sku ?? '');
    _barcode = TextEditingController(text: p?.barcode ?? '');
    _sellingPrice = TextEditingController(text: p?.sellingPrice.toString() ?? '');
    _defaultCost = TextEditingController(text: p?.defaultCost.toString() ?? '');
    _reorderLevel = TextEditingController(text: (p?.reorderLevel ?? 0).toString());
    _openingQuantity = TextEditingController(text: (p?.quantity ?? 0).toString());
    _type = p?.type ?? widget.defaultType ?? ProductType.phoneNew;
    _active = p?.active ?? true;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _errorText = null;
    });
    try {
      if (_isEdit) {
        // Built explicitly (not via copyWith) so clearing the barcode field
        // actually clears it — copyWith's `??` can't distinguish "leave
        // unchanged" from "set to null".
        final updated = Product(
          id: widget.existing!.id,
          name: _name.text.trim(),
          sku: _sku.text.trim(),
          type: _type,
          barcode: _barcode.text.trim().isEmpty ? null : _barcode.text.trim(),
          sellingPrice: double.parse(_sellingPrice.text),
          defaultCost: double.parse(_defaultCost.text),
          reorderLevel: int.parse(_reorderLevel.text),
          quantity: widget.existing!.quantity,
          active: _active,
        );
        await widget.repository.updateProduct(updated);
      } else {
        await widget.repository.addProduct(
          name: _name.text.trim(),
          sku: _sku.text.trim(),
          type: _type,
          barcode: _barcode.text.trim().isEmpty ? null : _barcode.text.trim(),
          sellingPrice: double.parse(_sellingPrice.text),
          defaultCost: double.parse(_defaultCost.text),
          reorderLevel: int.parse(_reorderLevel.text),
          openingQuantity: int.parse(_openingQuantity.text),
        );
      }
      if (mounted) Navigator.of(context).pop(true);
    } on InventoryException catch (e) {
      setState(() => _errorText = e.message);
    } catch (e) {
      setState(() => _errorText = 'حدث خطأ غير متوقع: $e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: DraggableScrollableSheet(
        initialChildSize: 0.85,
        maxChildSize: 0.95,
        minChildSize: 0.5,
        expand: false,
        builder: (context, scrollController) => Form(
          key: _formKey,
          child: ListView(
            controller: scrollController,
            padding: const EdgeInsets.all(20),
            children: [
              Text(_isEdit ? 'تعديل صنف' : 'إضافة صنف جديد',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              DropdownButtonFormField<ProductType>(
                value: _type,
                decoration: const InputDecoration(labelText: 'نوع الصنف'),
                items: [
                  for (final t in ProductType.values) DropdownMenuItem(value: t, child: Text(t.label)),
                ],
                onChanged: (v) => setState(() => _type = v ?? _type),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'اسم الصنف'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'اسم الصنف مطلوب' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _sku,
                decoration: const InputDecoration(labelText: 'رمز الصنف (SKU)'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'رمز الصنف مطلوب' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _barcode,
                decoration: const InputDecoration(labelText: 'الباركود (اختياري)'),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _sellingPrice,
                      decoration: const InputDecoration(labelText: 'سعر البيع'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      validator: _numberValidator,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _defaultCost,
                      decoration: const InputDecoration(labelText: 'التكلفة'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      validator: _numberValidator,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _reorderLevel,
                      decoration: const InputDecoration(labelText: 'حد إعادة الطلب'),
                      keyboardType: TextInputType.number,
                      validator: _intValidator,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _openingQuantity,
                      enabled: !_isEdit,
                      decoration: InputDecoration(
                        labelText: _isEdit ? 'الكمية (عدّلها من "تعديل الرصيد")' : 'الكمية الافتتاحية',
                      ),
                      keyboardType: TextInputType.number,
                      validator: _intValidator,
                    ),
                  ),
                ],
              ),
              if (_isEdit) ...[
                const SizedBox(height: 8),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: _active,
                  onChanged: (v) => setState(() => _active = v),
                  title: const Text('الصنف مفعّل'),
                ),
              ],
              if (_errorText != null) ...[
                const SizedBox(height: 8),
                Text(_errorText!, style: const TextStyle(color: Colors.red)),
              ],
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _submitting ? null : _submit,
                child: _submitting
                    ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : Text(_isEdit ? 'حفظ التعديلات' : 'إضافة الصنف'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String? _numberValidator(String? v) {
    if (v == null || v.trim().isEmpty) return 'مطلوب';
    if (double.tryParse(v) == null) return 'رقم غير صحيح';
    if (double.parse(v) < 0) return 'لا يمكن أن يكون سالبًا';
    return null;
  }

  String? _intValidator(String? v) {
    if (v == null || v.trim().isEmpty) return 'مطلوب';
    if (int.tryParse(v) == null) return 'رقم صحيح مطلوب';
    if (int.parse(v) < 0) return 'لا يمكن أن يكون سالبًا';
    return null;
  }

  @override
  void dispose() {
    _name.dispose();
    _sku.dispose();
    _barcode.dispose();
    _sellingPrice.dispose();
    _defaultCost.dispose();
    _reorderLevel.dispose();
    _openingQuantity.dispose();
    super.dispose();
  }
}

class StockAdjustDialog extends StatefulWidget {
  const StockAdjustDialog({super.key, required this.repository, required this.product});
  final InventoryRepository repository;
  final Product product;

  @override
  State<StockAdjustDialog> createState() => _StockAdjustDialogState();
}

class _StockAdjustDialogState extends State<StockAdjustDialog> {
  final _qtyController = TextEditingController(text: '1');
  final _reasonController = TextEditingController();
  bool _isAddition = true;
  bool _submitting = false;
  String? _error;

  Future<void> _submit() async {
    final qty = int.tryParse(_qtyController.text);
    if (qty == null || qty <= 0) {
      setState(() => _error = 'أدخل كمية صحيحة أكبر من صفر');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.repository.adjustStock(
        widget.product.id,
        _isAddition ? qty : -qty,
        _reasonController.text.trim(),
      );
      if (mounted) Navigator.of(context).pop(true);
    } on InventoryException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('تعديل رصيد: ${widget.product.name}'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('الرصيد الحالي: ${widget.product.quantity}'),
          const SizedBox(height: 12),
          SegmentedButton<bool>(
            segments: const [
              ButtonSegment(value: true, label: Text('إضافة'), icon: Icon(Icons.add)),
              ButtonSegment(value: false, label: Text('صرف'), icon: Icon(Icons.remove)),
            ],
            selected: {_isAddition},
            onSelectionChanged: (s) => setState(() => _isAddition = s.first),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _qtyController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'الكمية'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _reasonController,
            decoration: const InputDecoration(labelText: 'سبب الحركة (جرد، تالف، توريد يدوي...)'),
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
    _qtyController.dispose();
    _reasonController.dispose();
    super.dispose();
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.inventory_2_outlined, size: 56, color: Colors.grey.shade400),
          const SizedBox(height: 12),
          const Text('لا توجد أصناف مطابقة'),
          const Text('جرّب تغيير كلمة البحث أو أضف صنفًا جديدًا', style: TextStyle(color: Colors.black54)),
        ],
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 56, color: Colors.red.shade300),
          const SizedBox(height: 12),
          Text('تعذّر تحميل الأصناف\n$message', textAlign: TextAlign.center),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: onRetry, child: const Text('إعادة المحاولة')),
        ],
      ),
    );
  }
}
