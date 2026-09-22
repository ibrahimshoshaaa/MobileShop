import 'supplier_models.dart';

abstract class SupplierRepository {
  Future<List<Supplier>> listSuppliers({String query = ''});
  Future<Supplier> addSupplier({required String name, String? phone});
  Future<Supplier> updateSupplier(Supplier supplier);
}
