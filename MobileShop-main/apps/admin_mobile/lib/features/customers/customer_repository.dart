import 'customer_models.dart';

abstract class CustomerRepository {
  Future<List<Customer>> listCustomers({String query = ''});
  Future<Customer?> getCustomer(String id);
  Future<Customer> addCustomer({required String name, String? phone});
  Future<Customer> updateCustomer(Customer customer);
}
