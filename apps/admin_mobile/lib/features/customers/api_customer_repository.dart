import '../customers/customer_models.dart';
import '../customers/customer_repository.dart';
import '../../core/api_client.dart';

/// Online-mode customer repository.
/// Mirrors apps/desktop/api_customers_repo.py.
class ApiCustomerRepository implements CustomerRepository {
  ApiCustomerRepository({required this.client});

  final ApiClient client;

  Customer _toCustomer(Map<String, dynamic> d) => Customer(
        id: d['id'] as String,
        name: d['name'] as String,
        phone: d['phone'] as String?,
        active: d['active'] as bool? ?? true,
      );

  @override
  Future<List<Customer>> listCustomers({String query = ''}) async {
    final raw = await client.query('customers');
    final all = raw.map(_toCustomer).toList();
    final q = query.trim().toLowerCase();
    if (q.isEmpty) {
      return all..sort((a, b) => a.name.compareTo(b.name));
    }
    return all
        .where((c) =>
            c.name.toLowerCase().contains(q) ||
            (c.phone?.contains(q) ?? false))
        .toList()
      ..sort((a, b) => a.name.compareTo(b.name));
  }

  @override
  Future<Customer?> getCustomer(String id) async {
    final all = await listCustomers();
    try {
      return all.firstWhere((c) => c.id == id);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<Customer> addCustomer({required String name, String? phone}) async {
    if (name.trim().isEmpty) throw CustomerException('اسم العميل مطلوب.');
    final data = await client.command(
      ApiClient.newCommandId('cmd-create-customer'),
      'createCustomer',
      {
        'name': name.trim(),
        'phone': (phone?.trim().isEmpty ?? true) ? null : phone!.trim(),
      },
    );
    return _toCustomer(data);
  }

  @override
  Future<Customer> updateCustomer(Customer customer) async {
    if (customer.name.trim().isEmpty) throw CustomerException('اسم العميل مطلوب.');
    final data = await client.command(
      ApiClient.newCommandId('cmd-update-customer'),
      'updateCustomer',
      {
        'customer_id': customer.id,
        'changes': {
          'name': customer.name.trim(),
          'phone': (customer.phone?.trim().isEmpty ?? true)
              ? null
              : customer.phone!.trim(),
          'active': customer.active,
        },
      },
    );
    return _toCustomer(data);
  }
}
