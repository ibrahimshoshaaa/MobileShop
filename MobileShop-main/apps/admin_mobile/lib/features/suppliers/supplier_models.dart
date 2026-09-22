import 'package:flutter/foundation.dart';

/// Deviation from shared/models/erp.py Supplier: the backend tracks which
/// branches a supplier is associated with (`branch_ids`). Neither this app
/// nor any other feature here has a branch-selection UI yet (everything
/// runs under one local branch — see LocalStore.defaultBranchId), so that
/// field is omitted rather than faked with a single-item list that would
/// just be dead weight until multi-branch support actually exists.
@immutable
class Supplier {
  final String id;
  final String name;
  final String? phone;
  final bool active;

  const Supplier({
    required this.id,
    required this.name,
    this.phone,
    this.active = true,
  });

  Supplier copyWith({String? name, String? phone, bool? active}) => Supplier(
        id: id,
        name: name ?? this.name,
        phone: phone ?? this.phone,
        active: active ?? this.active,
      );
}

class SupplierException implements Exception {
  final String message;
  SupplierException(this.message);
  @override
  String toString() => message;
}
