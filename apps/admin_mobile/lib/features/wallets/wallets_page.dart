import 'package:flutter/material.dart';
import 'wallet_models.dart';
import 'wallet_provider.dart';
import 'wallet_repository.dart';

class WalletsPage extends StatefulWidget {
  const WalletsPage({super.key});

  @override
  State<WalletsPage> createState() => _WalletsPageState();
}

class _WalletsPageState extends State<WalletsPage> {
  late Future<WalletRepository> _repositoryFuture;
  WalletRepository? _repository;
  Future<Map<WalletId, double>>? _balancesFuture;
  Future<List<WalletTransaction>>? _txFuture;

  @override
  void initState() {
    super.initState();
    _repositoryFuture = getWalletRepository();
  }

  void _reload() {
    final repo = _repository;
    if (repo == null) return;
    setState(() {
      _balancesFuture = repo.getBalances();
      _txFuture = repo.listTransactions(limit: 40);
    });
  }

  Future<void> _openTxSheet(WalletRepository repository, {required bool deposit}) async {
    final result = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => WalletTxSheet(repository: repository, deposit: deposit),
    );
    if (result == true) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<WalletRepository>(
      future: _repositoryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('تعذّر تحميل المحافظ\n${snapshot.error}', textAlign: TextAlign.center));
        }
        _repository = snapshot.data!;
        _balancesFuture ??= _repository!.getBalances();
        _txFuture ??= _repository!.listTransactions(limit: 40);
        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
            children: [
              FutureBuilder<Map<WalletId, double>>(
                future: _balancesFuture,
                builder: (context, snap) {
                  final balances = snap.data ?? {for (final w in WalletId.values) w: 0.0};
                  return Row(
                    children: [
                      Expanded(child: _BalanceCard(walletId: WalletId.cash, amount: balances[WalletId.cash] ?? 0)),
                      const SizedBox(width: 10),
                      Expanded(child: _BalanceCard(walletId: WalletId.wallet, amount: balances[WalletId.wallet] ?? 0)),
                    ],
                  );
                },
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: () => _openTxSheet(_repository!, deposit: true),
                      icon: const Icon(Icons.add_circle_outline),
                      label: const Text('إيداع'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _openTxSheet(_repository!, deposit: false),
                      icon: const Icon(Icons.remove_circle_outline),
                      label: const Text('سحب'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 22),
              const Text('آخر الحركات', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
              const SizedBox(height: 8),
              FutureBuilder<List<WalletTransaction>>(
                future: _txFuture,
                builder: (context, snap) {
                  if (snap.connectionState != ConnectionState.done) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 20),
                      child: Center(child: CircularProgressIndicator()),
                    );
                  }
                  final txs = snap.data ?? const [];
                  if (txs.isEmpty) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 20),
                      child: Center(child: Text('لا توجد حركات بعد', style: TextStyle(color: Colors.black54))),
                    );
                  }
                  return Column(children: txs.map((t) => _TxTile(tx: t)).toList());
                },
              ),
            ],
          ),
        );
      },
    );
  }
}

class _BalanceCard extends StatelessWidget {
  const _BalanceCard({required this.walletId, required this.amount});
  final WalletId walletId;
  final double amount;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(walletId.label, style: const TextStyle(color: Colors.black54, fontSize: 12)),
              const SizedBox(height: 6),
              Text('${amount.toStringAsFixed(0)} ج.م',
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
            ],
          ),
        ),
      );
}

class _TxTile extends StatelessWidget {
  const _TxTile({required this.tx});
  final WalletTransaction tx;

  @override
  Widget build(BuildContext context) {
    final isIn = tx.amount >= 0;
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: (isIn ? Colors.green : Colors.red).withOpacity(0.12),
          child: Icon(isIn ? Icons.south_west_rounded : Icons.north_east_rounded,
              color: isIn ? Colors.green.shade700 : Colors.red.shade700),
        ),
        title: Text('${tx.type.label} • ${tx.walletId.label}'),
        subtitle: Text(tx.note ?? '—'),
        trailing: Text(
          '${isIn ? '+' : ''}${tx.amount.toStringAsFixed(0)}',
          style: TextStyle(
            fontWeight: FontWeight.w900,
            color: isIn ? Colors.green.shade700 : Colors.red.shade700,
          ),
        ),
      ),
    );
  }
}

class WalletTxSheet extends StatefulWidget {
  const WalletTxSheet({super.key, required this.repository, required this.deposit});
  final WalletRepository repository;
  final bool deposit;

  @override
  State<WalletTxSheet> createState() => _WalletTxSheetState();
}

class _WalletTxSheetState extends State<WalletTxSheet> {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _noteController = TextEditingController();
  WalletId _walletId = WalletId.cash;
  bool _submitting = false;
  String? _error;

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final amount = double.parse(_amountController.text);
      if (widget.deposit) {
        await widget.repository.deposit(walletId: _walletId, amount: amount, note: _noteController.text);
      } else {
        await widget.repository.withdraw(walletId: _walletId, amount: amount, note: _noteController.text);
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
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(widget.deposit ? 'إيداع في محفظة' : 'سحب من محفظة',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
            const SizedBox(height: 16),
            SegmentedButton<WalletId>(
              segments: WalletId.values
                  .map((w) => ButtonSegment(value: w, label: Text(w.label)))
                  .toList(),
              selected: {_walletId},
              onSelectionChanged: (s) => setState(() => _walletId = s.first),
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: _amountController,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'القيمة (ج.م)'),
              validator: (v) {
                final n = double.tryParse(v ?? '');
                if (n == null || n <= 0) return 'أدخل قيمة صحيحة';
                return null;
              },
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: _noteController,
              decoration: const InputDecoration(labelText: 'ملاحظة (اختياري)'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 10),
              Text(_error!, style: TextStyle(color: Colors.red.shade700)),
            ],
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _submitting ? null : _submit,
              child: _submitting
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : Text(widget.deposit ? 'تأكيد الإيداع' : 'تأكيد السحب'),
            ),
          ],
        ),
      ),
    );
  }
}
