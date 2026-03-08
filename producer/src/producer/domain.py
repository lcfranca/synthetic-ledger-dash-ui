import json
import random
from dataclasses import dataclass
from importlib import resources
from typing import Any


FIRST_NAMES = (
    "Ana",
    "Bruno",
    "Carla",
    "Daniel",
    "Eduarda",
    "Felipe",
    "Gabriela",
    "Henrique",
    "Isabela",
    "Joao",
    "Karen",
    "Lucas",
    "Mariana",
    "Nicolas",
    "Olivia",
    "Paulo",
    "Renata",
    "Sofia",
    "Tiago",
    "Valeria",
)

LAST_NAMES = (
    "Silva",
    "Souza",
    "Costa",
    "Oliveira",
    "Pereira",
    "Rodrigues",
    "Almeida",
    "Nogueira",
    "Carvalho",
    "Barbosa",
    "Mendes",
    "Gomes",
)

EMAIL_PROVIDERS = (
    ("gmail.com", 0.56),
    ("outlook.com", 0.16),
    ("hotmail.com", 0.12),
    ("yahoo.com.br", 0.08),
    ("icloud.com", 0.05),
    ("uol.com.br", 0.03),
)

CUSTOMER_SEGMENTS = (
    ("prime", 0.24),
    ("recorrente", 0.36),
    ("novo", 0.22),
    ("corporativo", 0.08),
    ("reativado", 0.10),
)

PAYMENT_METHODS = {
    "direct": (("pix", 0.34), ("credit_card", 0.38), ("debit_card", 0.12), ("bank_slip", 0.06), ("wallet", 0.10)),
    "marketplace": (("marketplace_wallet", 0.42), ("credit_card", 0.31), ("pix", 0.17), ("bank_slip", 0.10)),
    "b2b": (("invoice", 0.62), ("bank_slip", 0.23), ("pix", 0.15)),
}

ORDER_STATUSES = (("approved", 0.28), ("invoiced", 0.24), ("picking", 0.18), ("shipped", 0.18), ("delivered", 0.12))
DEVICE_TYPES = (("mobile_app", 0.46), ("mobile_web", 0.22), ("desktop", 0.24), ("store_assisted", 0.08))
FREIGHT_SERVICES = (("express", 0.33), ("standard", 0.47), ("scheduled", 0.12), ("pickup", 0.08))
ORDER_ORIGINS = (("crm_campaign", 0.16), ("organic_search", 0.22), ("retargeting", 0.14), ("marketplace_search", 0.31), ("social_commerce", 0.17))
COUPON_PREFIXES = ("BFCM", "FLASH", "LOYAL", "VIP", "APP", "CRM", "PLUS")


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
        self.pending_sale_lines: list[dict[str, Any]] = []
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

    def choose_weighted_pair(self, items: tuple[tuple[str, float], ...] | list[tuple[str, float]]) -> str:
        options = list(items)
        labels = [item[0] for item in options]
        weights = [max(float(item[1]), 0.001) for item in options]
        return self.random.choices(labels, weights=weights, k=1)[0]

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

    def generate_cpf(self) -> str:
        digits = [self.random.randint(0, 9) for _ in range(9)]
        first_check = ((sum(value * weight for value, weight in zip(digits, range(10, 1, -1))) * 10) % 11) % 10
        digits.append(first_check)
        second_check = ((sum(value * weight for value, weight in zip(digits, range(11, 1, -1))) * 10) % 11) % 10
        digits.append(second_check)
        text = "".join(str(value) for value in digits)
        return f"{text[0:3]}.{text[3:6]}.{text[6:9]}-{text[9:11]}"

    def build_customer_profile(self) -> dict[str, str]:
        first_name = self.random.choice(FIRST_NAMES)
        last_name = self.random.choice(LAST_NAMES)
        normalized_first = first_name.lower()
        normalized_last = last_name.lower()
        suffix = self.random.randint(10, 9999)
        provider = self.choose_weighted_pair(EMAIL_PROVIDERS)
        return {
            "customer_id": f"cust-{self.random.randint(100000, 999999)}",
            "customer_name": f"{first_name} {last_name}",
            "customer_cpf": self.generate_cpf(),
            "customer_email": f"{normalized_first}.{normalized_last}{suffix}@{provider}",
            "customer_segment": self.choose_weighted_pair(CUSTOMER_SEGMENTS),
            "sales_region": self.random.choice(["SP", "RJ", "MG", "PR", "SC", "BA", "DF"]),
        }

    def build_payment_profile(self, channel: Channel) -> tuple[str, int]:
        payment_method = self.choose_weighted_pair(PAYMENT_METHODS.get(channel.channel_type, PAYMENT_METHODS["direct"]))
        if payment_method in {"pix", "debit_card", "wallet", "marketplace_wallet"}:
            installments = 1
        elif payment_method == "credit_card":
            installments = self.random.choices([1, 2, 3, 4, 5, 6, 8, 10, 12], weights=[12, 8, 14, 12, 10, 16, 7, 5, 4], k=1)[0]
        else:
            installments = self.random.choice([1, 1, 1, 2])
        return payment_method, installments

    def build_coupon_code(self, channel: Channel, item_count: int) -> str | None:
        chance = 0.19 + (0.08 if item_count >= 3 else 0.0) + (0.04 if channel.channel_type == "direct" else 0.0)
        if self.random.random() > chance:
            return None
        prefix = self.random.choice(COUPON_PREFIXES)
        return f"{prefix}{self.random.randint(10, 99)}"

    def build_sale_lines(self) -> list[dict[str, Any]]:
        products = self.available_products()
        if not products:
            return []

        primary_product = self.choice_weighted(products, lambda item: item.demand_weight)
        primary_channel = self.choice_weighted(
            [self.catalog.channels[channel_id] for channel_id in primary_product.channel_ids],
            lambda item: item.demand_weight,
        )
        eligible_products = [
            product
            for product in products
            if primary_channel.channel_id in product.channel_ids and self.available_warehouses_for_product(product)
        ]
        if not eligible_products:
            return []

        desired_lines = self.random.randint(1, min(4, len(eligible_products)))
        chosen_products: list[Product] = []
        seen_product_ids: set[str] = set()
        while len(chosen_products) < desired_lines:
            candidate = self.choice_weighted(eligible_products, lambda item: item.demand_weight)
            if candidate.product_id in seen_product_ids:
                if len(seen_product_ids) == len(eligible_products):
                    break
                continue
            seen_product_ids.add(candidate.product_id)
            chosen_products.append(candidate)

        customer = self.build_customer_profile()
        payment_method, payment_installments = self.build_payment_profile(primary_channel)
        order_id = self.next_document_id("SO")
        sale_id = self.next_document_id("SAL")
        order_status = self.choose_weighted_pair(ORDER_STATUSES)
        device_type = self.choose_weighted_pair(DEVICE_TYPES)
        freight_service = self.choose_weighted_pair(FREIGHT_SERVICES)
        order_origin = self.choose_weighted_pair(ORDER_ORIGINS)
        coupon_code = self.build_coupon_code(primary_channel, len(chosen_products))

        lines: list[dict[str, Any]] = []
        cart_quantity = 0.0
        cart_gross_amount = 0.0
        cart_discount = 0.0
        cart_net_amount = 0.0

        for line_index, product in enumerate(chosen_products, start=1):
            warehouse_candidates = self.available_warehouses_for_product(product)
            if not warehouse_candidates:
                continue
            warehouse = self.choice_weighted(
                warehouse_candidates,
                lambda item: self.inventory.get((product.product_id, item.warehouse_id), {}).get("quantity", 0.0),
            )
            stock = self.inventory.setdefault((product.product_id, warehouse.warehouse_id), {"quantity": 0.0, "avg_cost": product.base_cost})
            max_units = int(stock["quantity"])
            if max_units <= 0:
                continue
            quantity = float(self.random.randint(1, min(max_units, 3 if len(chosen_products) > 2 else 4)))
            stock_ratio = max(stock["quantity"] / max(float(product.target_stock), 1.0), 0.15)
            dynamic_markup = 1.0 + min(max(1.0 - stock_ratio, 0.0), 0.18)
            segment_adjustment = 0.985 if customer["customer_segment"] in {"prime", "recorrente"} else 1.01
            unit_price = round(product.base_price * primary_channel.price_multiplier * dynamic_markup * segment_adjustment * self.random.uniform(0.97, 1.04), 2)
            gross_amount = round(quantity * unit_price, 2)
            discount_rate = self.random.uniform(0.0, 0.035)
            if coupon_code:
                discount_rate += self.random.uniform(0.01, 0.035)
            if len(chosen_products) >= 3:
                discount_rate += 0.012
            discount = round(gross_amount * min(discount_rate, 0.12), 2)
            net_amount = round(gross_amount - discount, 2)
            tax_amount = round(net_amount * product.tax_rate, 2)
            marketplace_fee = round(net_amount * primary_channel.commission_rate, 2)
            avg_cost = float(stock["avg_cost"])
            cmv = round(quantity * avg_cost, 2)
            stock["quantity"] = round(max(stock["quantity"] - quantity, 0.0), 2)

            line = {
                "event_type": "sale",
                "sale_id": sale_id,
                "order_id": order_id,
                "product": product,
                "supplier": self.catalog.suppliers[product.preferred_supplier_id],
                "warehouse": warehouse,
                "channel": primary_channel,
                "quantity": quantity,
                "unit_price": unit_price,
                "gross_amount": gross_amount,
                "discount": discount,
                "net_amount": net_amount,
                "tax": tax_amount,
                "marketplace_fee": marketplace_fee,
                "cost_basis": avg_cost,
                "cmv": cmv,
                "customer_id": customer["customer_id"],
                "customer_name": customer["customer_name"],
                "customer_cpf": customer["customer_cpf"],
                "customer_email": customer["customer_email"],
                "customer_segment": customer["customer_segment"],
                "sales_region": customer["sales_region"],
                "payment_method": payment_method,
                "payment_installments": payment_installments,
                "order_status": order_status,
                "order_origin": order_origin,
                "coupon_code": coupon_code,
                "device_type": device_type,
                "freight_service": freight_service,
                "cart_items_count": len(chosen_products),
                "debit_account": self.settlement_account_code(primary_channel),
                "credit_account": self.account_code("revenue"),
                "sale_line_index": line_index,
            }
            cart_quantity += quantity
            cart_gross_amount += gross_amount
            cart_discount += discount
            cart_net_amount += net_amount
            lines.append(line)

        for line in lines:
            line["cart_quantity"] = round(cart_quantity, 3)
            line["cart_gross_amount"] = round(cart_gross_amount, 2)
            line["cart_discount"] = round(cart_discount, 2)
            line["cart_net_amount"] = round(cart_net_amount, 2)

        return lines

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
            "sale_id": None,
            "customer_id": None,
            "customer_name": None,
            "customer_cpf": None,
            "customer_email": None,
            "customer_segment": None,
            "payment_method": None,
            "payment_installments": 1,
            "order_status": "received",
            "order_origin": "procurement",
            "coupon_code": None,
            "device_type": None,
            "sales_region": warehouse.state,
            "freight_service": None,
            "cart_items_count": 1,
            "cart_quantity": float(quantity),
            "cart_gross_amount": gross_amount,
            "cart_discount": discount,
            "cart_net_amount": net_amount,
            "sale_line_index": 1,
            "debit_account": self.account_code("inventory"),
            "credit_account": self.account_code("accounts_payable"),
        }

    def next_sale(self) -> dict[str, Any]:
        if self.pending_sale_lines:
            return self.pending_sale_lines.pop(0)

        products = self.available_products()
        if not products:
            return self.next_purchase()
        lines = self.build_sale_lines()
        if not lines:
            return self.next_purchase()

        for line in lines:
            sale_snapshot = {
                **line,
                "returnable_quantity": line["quantity"],
            }
            self.fulfilled_sales.append(sale_snapshot)
            self.pending_freights.append(sale_snapshot)
        if len(self.fulfilled_sales) > 400:
            self.fulfilled_sales = self.fulfilled_sales[-250:]
        if len(self.pending_freights) > 200:
            self.pending_freights = self.pending_freights[-120:]
        self.pending_sale_lines = lines[1:]
        return lines[0]

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
            "sale_id": sale.get("sale_id"),
            "customer_id": sale["customer_id"],
            "customer_name": sale.get("customer_name"),
            "customer_cpf": sale.get("customer_cpf"),
            "customer_email": sale.get("customer_email"),
            "customer_segment": sale.get("customer_segment"),
            "payment_method": sale.get("payment_method"),
            "payment_installments": sale.get("payment_installments", 1),
            "order_status": "returned",
            "order_origin": sale.get("order_origin"),
            "coupon_code": sale.get("coupon_code"),
            "device_type": sale.get("device_type"),
            "sales_region": sale.get("sales_region"),
            "freight_service": sale.get("freight_service"),
            "cart_items_count": sale.get("cart_items_count", 1),
            "cart_quantity": sale.get("cart_quantity", quantity),
            "cart_gross_amount": sale.get("cart_gross_amount", gross_amount),
            "cart_discount": sale.get("cart_discount", discount),
            "cart_net_amount": sale.get("cart_net_amount", net_amount),
            "sale_line_index": sale.get("sale_line_index", 1),
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
            "sale_id": sale.get("sale_id"),
            "customer_id": sale["customer_id"],
            "customer_name": sale.get("customer_name"),
            "customer_cpf": sale.get("customer_cpf"),
            "customer_email": sale.get("customer_email"),
            "customer_segment": sale.get("customer_segment"),
            "payment_method": sale.get("payment_method"),
            "payment_installments": sale.get("payment_installments", 1),
            "order_status": sale.get("order_status", "shipped"),
            "order_origin": sale.get("order_origin"),
            "coupon_code": sale.get("coupon_code"),
            "device_type": sale.get("device_type"),
            "sales_region": sale.get("sales_region"),
            "freight_service": sale.get("freight_service"),
            "cart_items_count": sale.get("cart_items_count", 1),
            "cart_quantity": sale.get("cart_quantity", sale["quantity"]),
            "cart_gross_amount": sale.get("cart_gross_amount", sale["gross_amount"]),
            "cart_discount": sale.get("cart_discount", sale["discount"]),
            "cart_net_amount": sale.get("cart_net_amount", sale["net_amount"]),
            "sale_line_index": sale.get("sale_line_index", 1),
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
            "sale_id": None,
            "customer_id": None,
            "customer_name": None,
            "customer_cpf": None,
            "customer_email": None,
            "customer_segment": None,
            "payment_method": None,
            "payment_installments": 1,
            "order_status": "opening_stock",
            "order_origin": "bootstrap",
            "coupon_code": None,
            "device_type": None,
            "sales_region": warehouse.state,
            "freight_service": None,
            "cart_items_count": 1,
            "cart_quantity": quantity,
            "cart_gross_amount": gross_amount,
            "cart_discount": 0.0,
            "cart_net_amount": net_amount,
            "sale_line_index": 1,
            "debit_account": self.account_code("inventory"),
            "credit_account": self.account_code("accounts_payable"),
        }
