from decimal import Decimal
class EmployeeService:
    def commission(self,base,rate): return (base*rate/Decimal('100')).quantize(Decimal('.01'))
    def salary(self,base,commission=Decimal('0'),bonus=Decimal('0'),deductions=Decimal('0')): return base+commission+bonus-deductions
