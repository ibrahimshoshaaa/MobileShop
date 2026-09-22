import '../sync/api_client.dart';
import 'customer_models.dart';
import 'customer_repository.dart';

/// Server-backed [CustomerRepository] — 4.2 ("قراءة البيانات ... من
/// السيرفر"). [listCustomers]/[getCustomer] call `GET /query/customers` via
/// [ApiClient] instead of the local SQLite table.
///
/// There's no single-customer read endpoint on the server, so [getCustomer]
/// fetches the list and finds the id in it — fine at today's expected
/// customer-list sizes, and exactly what the server itself would have to do
/// internally without a dedicated index.
///
/// Writing a customer isn't part of 4.2 or 4.3, so [addCustomer]/
/// [updateCustomer] delegate to [_local] (the existing offline SQLite
/// repository) unchanged — only the customer *list* comes from the server
/// when there's an active session.
class ApiCustomerRepository implements CustomerRepository {
  ApiCustomerRepository(this._client, this._local);

  final ApiClient _client;
  final CustomerRepository _local;

  Customer _fromJson(Map<String, dynamic> j) => Customer(
        id: j['id'] as String,
        name: j['name'] as String,
        phone: j['phone'] as String?,
        active: j['active'] as bool? ?? true,
      );

  @override
  Future<List<Customer>> listCustomers({String query = ''}) async {
    final List<Map<String, dynamic>> raw;
    try {
      raw = await _client.getCustomers(limit: 500);
    } on ApiException catch (e) {
      throw CustomerException(e.message);
    }
    final q = query.trim().toLowerCase();
    final customers = raw.map(_fromJson).where((c) {
      if (q.isEmpty) return true;
      return c.name.toLowerCase().contains(q) || (c.phone?.contains(q) ?? false);
    }).toList()
      ..sort((a, b) => a.name.compareTo(b.name));
    return customers;
  }

  @override
  Future<Customer?> getCustomer(String id) async {
    final customers = await listCustomers();
    for (final c in customers) {
      if (c.id == id) return c;
    }
    return null;
  }

  @override
  Future<Customer> addCustomer({required String name, String? phone}) =>
      _local.addCustomer(name: name, phone: phone);

  @override
  Future<Customer> updateCustomer(Customer customer) => _local.updateCustomer(customer);
}
