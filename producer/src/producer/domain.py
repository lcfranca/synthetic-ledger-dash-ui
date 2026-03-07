import json
import random
from dataclasses import dataclass
from importlib import resources
from typing import Any


@dataclass(frozen=True)
class Product:
    product_id: str
    product_name: str
    product_category: str
    product_brand: str
    preferred_supplier_id: str
    default_warehouse_id: str
    base_cost: float
    base_price: float
    tax_rate: float
    reorder_point: int
    target_stock: int
    demand_weight: float
    initial_stock: dict[str, int]
    channel_ids: list[str]


@dataclass(frozen=True)
class Supplier:
    supplier_id: str
    supplier_name: str
    payment_terms_days: int
    lead_time_days: int


@dataclass(frozen=True)
class Channel:
    channel_id: str
    channel_name: str
    commission_rate: float
    settlement_days: int
    price_multiplier: float
    demand_weight: float
    channel_type: str


@dataclass(frozen=True)
class Warehouse:
    warehouse_id: str
    warehouse_name: str
    city: str
    state: str


class Catalog:
    def __init__(self) -> None:
        self.company = self._load_json("company_profile.json")
        self.accounts_by_role = {
            item["account_role"]: item
            for item in self._load_json("accounts.json")
        }
        self.channels = {
            item["channel_id"]: Channel(**item)
            for item in self._load_json("channels.json")
        }
        self.suppliers = {
            item["supplier_id"]: Supplier(**item)
            for item in self._load_json("suppliers.json")
        }
        self.warehouses = {
            item["warehouse_id"]: Warehouse(**item)
            for item in self._load_json("warehouses.json")
        }
        self.products = {
            item["product_id"]: Product(**item)
            for item in self._load_json("products.json")
        }

    @staticmethod
    def _load_json(name: str) -> Any:
        path = resources.files("producer").joinpath("domain_data", name)
        return json.loads(path.read_text(encoding="utf-8"))


class RetailSimulation:
    def __init__(self, catalog: Catalog, seed: int | None = None) -> None:
        self.catalog = catalog
        self.random = random.Random(seed)
        self.inventory: dict[tuple[str, str], dict[str, float]] = {}
        self.bootstrap_queue: list[dict[str, Any]] = []
        self.fulfilled_sales: list[dict[str, Any]] = []
        self.pending_freights: list[dict[str, Any]] = []
        self.document_sequence = 0
        for product in catalog.products.values():
            for warehouse_id, quantity in product.initial_stock.items():
                self.inventory[(product.product_id, warehouse_id)] = {
                    "quantity": 0.0,
                    "avg_cost": float(product.base_cost),
                }
                if quantity > 0:
                    self.bootstrap_queue.append(self._build_opening_purchase(product, warehouse_id, float(quantity)))

    def choice_weighted(self, items: list[Any], weight_getter) -> Any:
        weights = [max(float(weight_getter(item)), 0.001) for item in items]
        return self.random.choices(items, weights=weights, k=1)[0]

    def available_products(self) -> list[Product]:
        available = []
        for product in self.catalog.products.values():
            total_qty = sum(
                self.inventory.get((product.product_id, warehouse_id), {}).get("quantity", 0.0)
                for warehouse_id in product.initial_stock
            )
            if total_qty >= 1:
                available.append(product)
        return available

    def available_warehouses_for_product(self, product: Product) -> list[Warehouse]:
        available = []
        for warehouse_id in product.initial_stock:
            quantity = self.inventory.get((product.product_id, warehouse_id), {}).get("quantity", 0.0)
            if quantity >= 1:
                available.append(self.catalog.warehouses[warehouse_id])
        return available

    def low_stock_products(self) -> list[Product]:
        low_stock = []
        for product in self.catalog.products.values():
            total_qty = sum(
                self.inventory.get((product.product_id, warehouse_id), {}).get("quantity", 0.0)
                for warehouse_id in product.initial_stock
            )
            if total_qty <= product.reorder_point:
                low_stock.append(product)
        return low_stock

    def returnable_sales(self) -> list[dict[str, Any]]:
        return [sale for sale in self.fulfilled_sales if float(sale.get("returnable_quantity", 0.0)) >= 1.0]

    def account_code(self, role: str) -> str:
        return str(self.catalog.accounts_by_role[role]["account_code"])

    def next_document_id(self, prefix: str) -> str:
        self.document_sequence += 1
        return f"{prefix}-{self.document_sequence:07d}"

    @staticmethod
    def per_unit(total: float, quantity: float) -> float:
        if quantity <= 0:
            return 0.0
        return float(total) / float(quantity)

    def settlement_account_code(self, channel: Channel) -> str:
        if channel.channel_type == "direct":
            return self.account_code("bank_accounts")
        return self.account_code("cash")

    def next_purchase(self) -> dict[str, Any]:
        candidates = self.low_stock_products() or list(self.catalog.products.values())
        product = self.choice_weighted(
            candidates,
            lambda item: max(item.target_stock - self.current_quantity(item.product_id), 1),
        )
        supplier = self.catalog.suppliers[product.preferred_supplier_id]
        warehouse = self.catalog.warehouses[product.default_warehouse_id]
        quantity = self.random.randint(max(product.reorder_point // 3, 12), max(product.target_stock - int(self.current_quantity(product.product_id)), 20))
        unit_cost = round(product.base_cost * self.random.uniform(0.96, 1.05), 2)
        gross_amount = round(quantity * unit_cost, 2)
        discount = round(gross_amount * self.random.uniform(0.0, 0.03), 2)
        net_amount = round(gross_amount - discount, 2)
        tax_amount = round(net_amount * product.tax_rate, 2)
        current = self.inventory.setdefault((product.product_id, warehouse.warehouse_id), {"quantity": 0.0, "avg_cost": unit_cost})
        new_quantity = current["quantity"] + quantity
        current["avg_cost"] = round(((current["quantity"] * current["avg_cost"]) + net_amount) / max(new_quantity, 1), 4)
        current["quantity"] = new_quantity
        return {
            "event_type": "purchase",
            "order_id": self.next_document_id("PO"),
            "product": product,
            "supplier": supplier,
            "warehouse": warehouse,
            "channel": self.catalog.channels["b2b_procurement"],
            "quantity": float(quantity),
            "unit_price": unit_cost,
            "gross_amount": gross_amount,
            "discount": discount,
            "net_amount": net_amount,
            "tax": tax_amount,
            "marketplace_fee": 0.0,
            "cost_basis": unit_cost,
            "cmv": 0.0,
            "customer_id": None,
            "debit_account": self.account_code("inventory"),
            "credit_account": self.account_code("accounts_payable"),
        }

    def next_sale(self) -> dict[str, Any]:
        products = self.available_products()
        if not products:
            return self.next_purchase()
        product = self.choice_weighted(products, lambda item: item.demand_weight)
        warehouse_candidates = self.available_warehouses_for_product(product)
        if not warehouse_candidates:
            return self.next_purchase()
        warehouse = self.choice_weighted(
            warehouse_candidates,
            lambda item: self.inventory.get((product.product_id, item.warehouse_id), {}).get("quantity", 0.0),
        )
        stock = self.inventory.setdefault((product.product_id, warehouse.warehouse_id), {"quantity": 0.0, "avg_cost": product.base_cost})
        max_units = int(stock["quantity"])
        if max_units <= 0:
            return self.next_purchase()
        quantity = float(self.random.randint(1, min(max_units, 4)))
        channel = self.choice_weighted(
            [self.catalog.channels[channel_id] for channel_id in product.channel_ids],
            lambda item: item.demand_weight,
        )
        unit_price = round(product.base_price * channel.price_multiplier * self.random.uniform(0.97, 1.06), 2)
        gross_amount = round(quantity * unit_price, 2)
        discount = round(gross_amount * self.random.uniform(0.0, 0.08), 2)
        net_amount = round(gross_amount - discount, 2)
        tax_amount = round(net_amount * product.tax_rate, 2)
        marketplace_fee = round(net_amount * channel.commission_rate, 2)
        avg_cost = float(stock["avg_cost"])
        cmv = round(quantity * avg_cost, 2)
        order_id = self.next_document_id("SO")
        stock["quantity"] = round(max(stock["quantity"] - quantity, 0.0), 2)
        scenario = {
            "event_type": "sale",
            "order_id": order_id,
            "product": product,
            "supplier": self.catalog.suppliers[product.preferred_supplier_id],
            "warehouse": warehouse,
            "channel": channel,
            "quantity": quantity,
            "unit_price": unit_price,
            "gross_amount": gross_amount,
            "discount": discount,
            "net_amount": net_amount,
            "tax": tax_amount,
            "marketplace_fee": marketplace_fee,
            "cost_basis": avg_cost,
            "cmv": cmv,
            "customer_id": f"cust-{self.random.randint(1000, 9999)}",
            "debit_account": self.settlement_account_code(channel),
            "credit_account": self.account_code("revenue"),
        }
        sale_snapshot = {
            **scenario,
            "returnable_quantity": quantity,
        }
        self.fulfilled_sales.append(sale_snapshot)
        self.pending_freights.append(sale_snapshot)
        if len(self.fulfilled_sales) > 400:
            self.fulfilled_sales = self.fulfilled_sales[-250:]
        if len(self.pending_freights) > 200:
            self.pending_freights = self.pending_freights[-120:]
        return scenario

    def next_return(self) -> dict[str, Any]:
        candidates = self.returnable_sales()
        if not candidates:
            return self.next_sale()
        sale = self.choice_weighted(candidates, lambda item: item["returnable_quantity"])
        quantity = float(self.random.randint(1, min(int(sale["returnable_quantity"]), 2)))
        sale["returnable_quantity"] = round(float(sale["returnable_quantity"]) - quantity, 2)
        stock = self.inventory.setdefault(
            (sale["product"].product_id, sale["warehouse"].warehouse_id),
            {"quantity": 0.0, "avg_cost": float(sale["cost_basis"])},
        )
        stock["quantity"] = round(stock["quantity"] + quantity, 2)
        stock["avg_cost"] = round(float(sale["cost_basis"]), 4)
        gross_amount = round(self.per_unit(sale["gross_amount"], sale["quantity"]) * quantity, 2)
        discount = round(self.per_unit(sale["discount"], sale["quantity"]) * quantity, 2)
        net_amount = round(self.per_unit(sale["net_amount"], sale["quantity"]) * quantity, 2)
        tax_amount = round(self.per_unit(sale["tax"], sale["quantity"]) * quantity, 2)
        cmv = round(self.per_unit(sale["cmv"], sale["quantity"]) * quantity, 2)
        return {
            "event_type": "return",
            "order_id": sale["order_id"],
            "product": sale["product"],
            "supplier": sale["supplier"],
            "warehouse": sale["warehouse"],
            "channel": sale["channel"],
            "quantity": quantity,
            "unit_price": round(net_amount / max(quantity, 1.0), 2),
            "gross_amount": gross_amount,
            "discount": discount,
            "net_amount": net_amount,
            "tax": tax_amount,
            "marketplace_fee": 0.0,
            "cost_basis": sale["cost_basis"],
            "cmv": cmv,
            "customer_id": sale["customer_id"],
            "debit_account": self.account_code("returns"),
            "credit_account": sale["debit_account"],
        }

    def next_freight(self) -> dict[str, Any]:
        if not self.pending_freights:
            return self.next_sale()
        sale = self.pending_freights.pop(0)
        base_per_unit = 4.5 if sale["product"].product_category in {"Telefonia", "Eletronicos"} else 3.2
        freight_amount = round(base_per_unit * sale["quantity"] * self.random.uniform(0.95, 1.35), 2)
        bank_fee = round(max(freight_amount * self.random.uniform(0.008, 0.018), 0.35), 2)
        return {
            "event_type": "freight",
            "order_id": sale["order_id"],
            "product": sale["product"],
            "supplier": sale["supplier"],
            "warehouse": sale["warehouse"],
            "channel": sale["channel"],
            "quantity": sale["quantity"],
            "unit_price": round(freight_amount / max(sale["quantity"], 1.0), 2),
            "gross_amount": freight_amount,
            "discount": 0.0,
            "net_amount": freight_amount,
            "tax": 0.0,
            "marketplace_fee": bank_fee,
            "cost_basis": 0.0,
            "cmv": 0.0,
            "customer_id": sale["customer_id"],
            "debit_account": self.account_code("outbound_freight"),
            "credit_account": self.account_code("bank_accounts"),
        }

    def current_quantity(self, product_id: str) -> float:
        return round(
            sum(position["quantity"] for (current_product_id, _), position in self.inventory.items() if current_product_id == product_id),
            2,
        )

    def next_event(self) -> dict[str, Any]:
        if self.pending_freights and self.random.random() < 0.16:
            return self.next_freight()
        if self.returnable_sales() and self.random.random() < 0.09:
            return self.next_return()
        if self.low_stock_products() and self.random.random() < 0.38:
            return self.next_purchase()
        return self.next_sale()

    def drain_bootstrap_events(self) -> list[dict[str, Any]]:
        pending = list(self.bootstrap_queue)
        self.bootstrap_queue.clear()
        return pending

    def _build_opening_purchase(self, product: Product, warehouse_id: str, quantity: float) -> dict[str, Any]:
        supplier = self.catalog.suppliers[product.preferred_supplier_id]
        warehouse = self.catalog.warehouses[warehouse_id]
        unit_cost = round(product.base_cost * self.random.uniform(0.98, 1.02), 2)
        gross_amount = round(quantity * unit_cost, 2)
        net_amount = gross_amount
        tax_amount = round(net_amount * product.tax_rate, 2)
        current = self.inventory.setdefault((product.product_id, warehouse_id), {"quantity": 0.0, "avg_cost": unit_cost})
        new_quantity = current["quantity"] + quantity
        current["avg_cost"] = round(((current["quantity"] * current["avg_cost"]) + net_amount) / max(new_quantity, 1), 4)
        current["quantity"] = new_quantity
        return {
            "event_type": "purchase",
            "order_id": self.next_document_id("BOOT"),
            "product": product,
            "supplier": supplier,
            "warehouse": warehouse,
            "channel": self.catalog.channels["b2b_procurement"],
            "quantity": quantity,
            "unit_price": unit_cost,
            "gross_amount": gross_amount,
            "discount": 0.0,
            "net_amount": net_amount,
            "tax": tax_amount,
            "marketplace_fee": 0.0,
            "cost_basis": unit_cost,
            "cmv": 0.0,
            "customer_id": None,
            "debit_account": self.account_code("inventory"),
            "credit_account": self.account_code("accounts_payable"),
        }
