import 'package:flutter/foundation.dart';

@immutable
class Customer {
  final String id;
  final String name;
  final String? phone;
  final bool active;

  const Customer({
    required this.id,
    required this.name,
    this.phone,
    this.active = true,
  });

  Customer copyWith({String? name, String? phone, bool? active}) => Customer(
        id: id,
        name: name ?? this.name,
        phone: phone ?? this.phone,
        active: active ?? this.active,
      );
}

class CustomerException implements Exception {
  final String message;
  CustomerException(this.message);
  @override
  String toString() => message;
}
