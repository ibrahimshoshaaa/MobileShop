from decimal import Decimal

from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.commands import CommandContext, CreateSaleCommand
from shared.models.erp import Product, Wallet


def ctx(cid, branch):
    return CommandContext(cid, "u", branch, frozenset({"sales.create", "inventory.read", "stock.adjust"}), "tenant-a")


def test_reports_full_uses_branch_scoped_sales_and_cogs():
    e=ERPCommandEngine()
    e.products.create("p", Product("p","Phone","P","PHONE_NEW",default_cost=Decimal("100")))
    e.wallets.create("w1", Wallet("w1","b1","Cash","CASH"))
    e.wallets.create("w2", Wallet("w2","b2","Cash","CASH"))
    e.ledger.create("open1", {"id":"open1","branch_id":"b1","account_id":"wallet:w1","debit":Decimal("1000"),"credit":Decimal("0")})
    e.ledger.create("open2", {"id":"open2","branch_id":"b2","account_id":"wallet:w2","debit":Decimal("1000"),"credit":Decimal("0")})
    e.adjust_stock(ctx("stock1","b1"),"p",2,100)
    e.adjust_stock(ctx("stock2","b2"),"p",2,100)
    e.create_sale(CreateSaleCommand(ctx("sale1","b1"),None,({"product_id":"p","quantity":1,"unit_price":150},),({"wallet_id":"w1","amount":150},)))
    e.create_sale(CreateSaleCommand(ctx("sale2","b2"),None,({"product_id":"p","quantity":1,"unit_price":300},),({"wallet_id":"w2","amount":300},)))
    report=e.reports_full("b1")
    assert report["sales_count"] == 1
    assert report["revenue"] == Decimal("150.00")
    assert report["cogs"] == Decimal("100.00")
    assert report["gross_profit"] == Decimal("50.00")
