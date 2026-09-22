import '../expenses/expense_repository.dart';
import '../inventory/inventory_models.dart';
import '../inventory/inventory_repository.dart';
import '../maintenance/maintenance_repository.dart';
import '../sales/sale_repository.dart';
import 'reports_models.dart';

/// Pulls together the four existing repositories into one summary. Deliberately
/// does not introduce a new storage layer — reports are a read-only view over
/// data the other features already own.
class ReportsRepository {
  ReportsRepository({
    required this.salesRepository,
    required this.expenseRepository,
    required this.maintenanceRepository,
    required this.inventoryRepository,
  });

  final SalesRepository salesRepository;
  final ExpenseRepository expenseRepository;
  final MaintenanceRepository maintenanceRepository;
  final InventoryRepository inventoryRepository;

  Future<ReportSummary> buildSummary(DateRange range) async {
    // Fetched once and reused for the current inventory-value/low-stock
    // snapshot below (COGS itself no longer needs it — see the loop below).
    final products = await inventoryRepository.listProducts();

    final sales = await salesRepository.listSalesInRange(from: range.start, to: range.end);
    var salesCount = 0;
    var salesRevenue = 0.0;
    var salesDiscount = 0.0;
    var estimatedCogs = 0.0;
    var hasEstimatedCosts = false;
    for (final sale in sales) {
      if (sale.status != 'COMPLETED') continue; // voided sales don't count as revenue
      salesCount++;
      salesRevenue += sale.total;
      salesDiscount += sale.discount;
      for (final item in sale.items) {
        // Since 1.4, each item carries its own cost-at-sale snapshot, so
        // this is exact rather than a lookup against the product's current
        // (possibly since-changed) cost — except for items backfilled by
        // the 1.4 migration from a pre-1.4 sale, which flag themselves via
        // costIsEstimated so the UI can say so.
        estimatedCogs += item.lineCost;
        if (item.costIsEstimated) hasEstimatedCosts = true;
      }
    }

    final expenses = await expenseRepository.listExpenses(from: range.start, to: range.end);
    final expensesTotal = expenses.fold<double>(0, (sum, e) => sum + e.amount);

    // MaintenanceRepository has no date-ranged query yet, so we fetch every
    // ticket and filter here — same cost as the "recent sales" pattern used
    // elsewhere in the app before this change.
    final allTickets = await maintenanceRepository.listTickets();
    var maintenanceDeliveredCount = 0;
    var maintenanceRevenue = 0.0;
    var maintenancePartsCost = 0.0;
    for (final ticket in allTickets) {
      if (ticket.status != 'DELIVERED') continue;
      if (!range.contains(ticket.createdAt)) continue;
      maintenanceDeliveredCount++;
      maintenanceRevenue += ticket.finalCost;
      maintenancePartsCost += ticket.partsCost;
    }

    var inventoryValue = 0.0;
    var lowStockCount = 0;
    for (final product in products) {
      if (!product.active) continue;
      if (product.type == ProductType.service) continue; // services don't hold stock
      inventoryValue += product.defaultCost * product.quantity;
      if (product.isLowStock) lowStockCount++;
    }

    return ReportSummary(
      range: range,
      salesCount: salesCount,
      salesRevenue: salesRevenue,
      salesDiscount: salesDiscount,
      estimatedCogs: estimatedCogs,
      hasEstimatedCosts: hasEstimatedCosts,
      expensesTotal: expensesTotal,
      maintenanceDeliveredCount: maintenanceDeliveredCount,
      maintenanceRevenue: maintenanceRevenue,
      maintenancePartsCost: maintenancePartsCost,
      inventoryValue: inventoryValue,
      lowStockCount: lowStockCount,
    );
  }
}
