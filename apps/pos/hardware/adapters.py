from dataclasses import dataclass
class BarcodeScanner:
    def scan(self): raise NotImplementedError
class IMEIScanner:
    def scan(self): raise NotImplementedError
class ThermalPrinter:
    def print_receipt(self, receipt): raise NotImplementedError
class CashDrawer:
    def open(self): raise NotImplementedError
class Camera:
    def capture(self): raise NotImplementedError
@dataclass
class Receipt:
    invoice_id:str; lines:list; total:str; currency:str='EGP'
