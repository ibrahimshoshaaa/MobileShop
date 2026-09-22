from .adapters import BarcodeScanner, IMEIScanner, ThermalPrinter, CashDrawer, Camera
class MockBarcodeScanner(BarcodeScanner):
    def __init__(self, values=()): self.values=list(values)
    def scan(self): return self.values.pop(0) if self.values else None
class MockIMEIScanner(MockBarcodeScanner, IMEIScanner): pass
class MockThermalPrinter(ThermalPrinter):
    def __init__(self): self.receipts=[]
    def print_receipt(self, receipt): self.receipts.append(receipt)
class MockCashDrawer(CashDrawer):
    def __init__(self): self.opened=0
    def open(self): self.opened+=1
class MockCamera(Camera):
    def capture(self): return b''
