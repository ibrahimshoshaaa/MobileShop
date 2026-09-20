from backend.functions.maintenance.service import MaintenanceService

def transition(ticket_id,status,service=None): return (service or MaintenanceService()).transition(ticket_id,status)
