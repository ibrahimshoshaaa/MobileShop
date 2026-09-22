import '../sales/sale_models.dart' show PaymentMethod;
import 'maintenance_models.dart';

abstract class MaintenanceRepository {
  Future<List<MaintenanceTicket>> listTickets();
  Future<MaintenanceTicket> createTicket({
    required String customerId,
    required String customerName,
    required String device,
    String? imei,
    required String problem,
  });
  Future<MaintenanceTicket> advanceStatus(String ticketId);
  Future<MaintenanceTicket> cancelTicket(String ticketId);
  Future<MaintenancePartUsage> usePart({
    required String ticketId,
    required String productId,
    required String productName,
    required int quantity,
    required double cost,
  });
  Future<List<MaintenancePartUsage>> listPartsUsed(String ticketId);
  Future<MaintenanceTicket> deliverTicket({
    required String ticketId,
    required double finalPrice,
    required double payment,
    required PaymentMethod method,
  });
}
