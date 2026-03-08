import json
import random
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
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


@dataclass
class PendingReceipt:
    due_tick: int
    product: Product
    supplier: Supplier
    warehouse: Warehouse
    quantity: float
    unit_cost: float
    discount_rate: float


@dataclass
class SupplierPayable:
    due_tick: int
    order_id: str
    product: Product
    supplier: Supplier
    warehouse: Warehouse
    outstanding_amount: float
    original_amount: float
    quantity: float
    unit_cost: float


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
        package_path = resources.files("producer").joinpath("domain_data", name)
        if package_path.is_file():
            return json.loads(package_path.read_text(encoding="utf-8"))

        repo_path = Path(__file__).resolve().parents[3] / "domain_data" / name
        return json.loads(repo_path.read_text(encoding="utf-8"))


class RetailSimulation:
    def __init__(self, catalog: Catalog, seed: int | None = None) -> None:
        self.catalog = catalog
        self.random = random.Random(seed)
        self.inventory: dict[tuple[str, str], dict[str, float]] = {}
        self.bootstrap_queue: list[dict[str, Any]] = []
        self.fulfilled_sales: list[dict[str, Any]] = []
        self.pending_sale_lines: list[dict[str, Any]] = []
        self.pending_freights: list[dict[str, Any]] = []
        self.pending_purchase_receipts: list[PendingReceipt] = []
        self.pending_supplier_payments: list[SupplierPayable] = []
        self.current_tick = 0
        self.market_temperature = 1.0
        self.demand_state = {
            product.product_id: {
                "level": self.random.uniform(0.88, 1.12),
                "trend": self.random.uniform(-0.015, 0.015),
            }
            for product in catalog.products.values()
        }
        self.liquidity = {"cash": 0.0, "bank_accounts": 0.0}
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
        eligible: list[dict[str, Any]] = []
        for sale in self.fulfilled_sales:
            if float(sale.get("returnable_quantity", 0.0)) < 1.0:
                continue
            delivered_tick = int(sale.get("delivered_tick", self.current_tick + 1))
            return_deadline_tick = int(sale.get("return_deadline_tick", delivered_tick))
            if self.current_tick < delivered_tick or self.current_tick > return_deadline_tick:
                continue
            eligible.append(sale)
        return eligible

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

    def _update_market_state(self) -> None:
        self.market_temperature = max(0.82, min(1.24, (self.market_temperature * 0.92) + (self.random.uniform(0.88, 1.14) * 0.08)))
        for state in self.demand_state.values():
            state["trend"] = max(-0.045, min(0.045, (state["trend"] * 0.84) + self.random.uniform(-0.015, 0.015)))
            state["level"] = max(0.58, min(1.65, state["level"] + state["trend"] + self.random.uniform(-0.025, 0.025)))

    def demand_multiplier(self, product_id: str) -> float:
        state = self.demand_state[product_id]
        return round(state["level"] * self.market_temperature, 4)

    def pending_receipt_quantity(self, product_id: str) -> float:
        return round(sum(item.quantity for item in self.pending_purchase_receipts if item.product.product_id == product_id), 3)

    def inventory_position(self, product_id: str) -> float:
        return round(self.current_quantity(product_id) + self.pending_receipt_quantity(product_id), 3)

    def update_liquidity(self, account_code: str, delta: float) -> None:
        if account_code == self.account_code("cash"):
            self.liquidity["cash"] = round(max(self.liquidity["cash"] + delta, 0.0), 2)
        if account_code == self.account_code("bank_accounts"):
            self.liquidity["bank_accounts"] = round(max(self.liquidity["bank_accounts"] + delta, 0.0), 2)

    def available_liquidity(self) -> float:
        return round(self.liquidity["cash"] + self.liquidity["bank_accounts"], 2)

    def procurement_lead_ticks(self, supplier: Supplier) -> int:
        base = max(supplier.lead_time_days, 2)
        return self.random.randint(base, base + max(supplier.lead_time_days, 2))

    def payment_term_ticks(self, supplier: Supplier) -> int:
        base = max(supplier.payment_terms_days // 2, 8)
        return self.random.randint(base, base + max(supplier.payment_terms_days // 2, 6))

    def delivery_ticks(self, freight_service: str | None) -> int:
        if freight_service == "pickup":
            return 1
        if freight_service == "express":
            return self.random.randint(1, 3)
        if freight_service == "scheduled":
            return self.random.randint(4, 7)
        return self.random.randint(2, 5)

    def return_window_ticks(self, customer_segment: str | None) -> int:
        base = {
            "prime": 28,
            "recorrente": 24,
            "reativado": 22,
            "novo": 18,
            "corporativo": 14,
        }.get(customer_segment or "", 18)
        return self.random.randint(max(base - 4, 10), base + 4)

    def return_propensity(self, *, product: Product, channel: Channel, customer_segment: str | None, quantity: float) -> float:
        propensity = 0.012
        if product.product_category in {"Telefonia", "Eletronicos"}:
            propensity += 0.018
        elif product.product_category in {"Acessorios", "Perifericos"}:
            propensity += 0.009
        else:
            propensity += 0.005

        if channel.channel_type == "marketplace":
            propensity += 0.01
        elif channel.channel_type == "b2b":
            propensity -= 0.006

        if customer_segment == "novo":
            propensity += 0.007
        elif customer_segment == "corporativo":
            propensity -= 0.01
        elif customer_segment == "prime":
            propensity -= 0.004

        if quantity >= 3:
            propensity += 0.004

        return round(min(max(propensity, 0.004), 0.085), 4)

    def schedule_procurement(self, *, force: bool = False) -> None:
        planned = 0
        ranked_products = sorted(
            self.catalog.products.values(),
            key=lambda product: (self.inventory_position(product.product_id) / max(product.target_stock, 1)) - self.demand_multiplier(product.product_id),
        )
        for product in ranked_products:
            supplier = self.catalog.suppliers[product.preferred_supplier_id]
            warehouse = self.catalog.warehouses[product.default_warehouse_id]
            demand_pressure = self.demand_multiplier(product.product_id)
            projected_demand = max(product.reorder_point * 0.45, product.target_stock * 0.22 * demand_pressure)
            inventory_position = self.inventory_position(product.product_id)
            reorder_trigger = max(product.reorder_point * 1.45, projected_demand * 1.15)
            if not force and inventory_position > reorder_trigger:
                continue
            shortage = max((product.target_stock * self.random.uniform(1.15, 1.45) * demand_pressure) - inventory_position, 0.0)
            if shortage <= 0 and not force:
                continue
            base_lot = max(product.reorder_point * self.random.uniform(0.9, 1.4), projected_demand * self.random.uniform(0.6, 0.95), 12)
            quantity = round(max(shortage, base_lot), 0)
            if quantity <= 0:
                continue
            unit_cost = round(product.base_cost * self.random.uniform(0.95, 1.06), 2)
            discount_rate = min(self.random.uniform(0.0, 0.028), 0.04)
            due_tick = self.current_tick if force else self.current_tick + self.procurement_lead_ticks(supplier)
            self.pending_purchase_receipts.append(
                PendingReceipt(
                    due_tick=due_tick,
                    product=product,
                    supplier=supplier,
                    warehouse=warehouse,
                    quantity=float(quantity),
                    unit_cost=unit_cost,
                    discount_rate=discount_rate,
                )
            )
            planned += 1
            if planned >= (4 if force else 2):
                break

    def due_purchase_receipts(self) -> list[PendingReceipt]:
        return [item for item in self.pending_purchase_receipts if item.due_tick <= self.current_tick]

    def due_supplier_payables(self) -> list[SupplierPayable]:
        return [item for item in self.pending_supplier_payments if item.due_tick <= self.current_tick and item.outstanding_amount > 0.01]

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
        due_receipts = self.due_purchase_receipts()
        if due_receipts:
            receipt = min(due_receipts, key=lambda item: item.due_tick)
            self.pending_purchase_receipts.remove(receipt)
        else:
            self.schedule_procurement(force=True)
            receipt = min(self.pending_purchase_receipts, key=lambda item: item.due_tick)
            self.pending_purchase_receipts.remove(receipt)

        product = receipt.product
        supplier = receipt.supplier
        warehouse = receipt.warehouse
        quantity = int(receipt.quantity)
        unit_cost = receipt.unit_cost
        gross_amount = round(quantity * unit_cost, 2)
        discount = round(gross_amount * receipt.discount_rate, 2)
        net_amount = round(gross_amount - discount, 2)
        tax_amount = round(net_amount * product.tax_rate, 2)

        current = self.inventory.setdefault((product.product_id, warehouse.warehouse_id), {"quantity": 0.0, "avg_cost": unit_cost})
        new_quantity = current["quantity"] + quantity
        current["avg_cost"] = round(((current["quantity"] * current["avg_cost"]) + net_amount) / max(new_quantity, 1), 4)
        current["quantity"] = new_quantity

        payable_total = round(net_amount + tax_amount, 2)
        order_id = self.next_document_id("PO")
        self.pending_supplier_payments.append(
            SupplierPayable(
                due_tick=self.current_tick + self.payment_term_ticks(supplier),
                order_id=order_id,
                product=product,
                supplier=supplier,
                warehouse=warehouse,
                outstanding_amount=payable_total,
                original_amount=payable_total,
                quantity=float(quantity),
                unit_cost=unit_cost,
            )
        )

        return {
            "event_type": "purchase",
            "order_id": order_id,
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

    def next_supplier_payment(self) -> dict[str, Any]:
        due_payables = self.due_supplier_payables()
        if not due_payables:
            return self.next_sale()

        payable = self.choice_weighted(due_payables, lambda item: item.outstanding_amount)
        available_bank = self.liquidity["bank_accounts"]
        available_cash = self.liquidity["cash"]
        available_total = available_bank + available_cash
        if available_total < 50:
            return self.next_sale()

        target_payment = payable.outstanding_amount * self.random.uniform(0.35, 0.8)
        payment_amount = round(min(payable.outstanding_amount, max(min(target_payment, available_total), min(payable.outstanding_amount, available_total))), 2)
        payment_account = self.account_code("bank_accounts") if available_bank >= payment_amount or available_bank >= available_cash else self.account_code("cash")
        self.update_liquidity(payment_account, -payment_amount)

        payable.outstanding_amount = round(max(payable.outstanding_amount - payment_amount, 0.0), 2)
        if payable.outstanding_amount <= 0.01:
            self.pending_supplier_payments.remove(payable)
        else:
            payable.due_tick = self.current_tick + self.random.randint(4, 10)

        return {
            "event_type": "supplier_payment",
            "order_id": payable.order_id,
            "product": payable.product,
            "supplier": payable.supplier,
            "warehouse": payable.warehouse,
            "channel": self.catalog.channels["b2b_procurement"],
            "quantity": 0.0,
            "unit_price": payable.unit_cost,
            "gross_amount": payment_amount,
            "discount": 0.0,
            "net_amount": payment_amount,
            "tax": 0.0,
            "marketplace_fee": 0.0,
            "cost_basis": payable.unit_cost,
            "cmv": 0.0,
            "sale_id": None,
            "customer_id": None,
            "customer_name": None,
            "customer_cpf": None,
            "customer_email": None,
            "customer_segment": None,
            "payment_method": "supplier_transfer",
            "payment_installments": 1,
            "order_status": "paid",
            "order_origin": "accounts_payable",
            "coupon_code": None,
            "device_type": None,
            "sales_region": payable.warehouse.state,
            "freight_service": None,
            "cart_items_count": 1,
            "cart_quantity": 0.0,
            "cart_gross_amount": payment_amount,
            "cart_discount": 0.0,
            "cart_net_amount": payment_amount,
            "sale_line_index": 1,
            "debit_account": self.account_code("accounts_payable"),
            "credit_account": payment_account,
        }

    def next_sale(self) -> dict[str, Any]:
        if self.pending_sale_lines:
            line = self.pending_sale_lines.pop(0)
            settlement_amount = round(line["net_amount"] + line["tax"] - line["marketplace_fee"], 2)
            self.update_liquidity(line["debit_account"], settlement_amount)
            return line

        products = self.available_products()
        if not products:
            return self.next_purchase()
        lines = self.build_sale_lines()
        if not lines:
            return self.next_purchase()

        for line in lines:
            delivered_tick = self.current_tick + self.delivery_ticks(line.get("freight_service"))
            return_deadline_tick = delivered_tick + self.return_window_ticks(line.get("customer_segment"))
            sale_snapshot = {
                **line,
                "returnable_quantity": line["quantity"],
                "delivered_tick": delivered_tick,
                "return_deadline_tick": return_deadline_tick,
                "return_propensity": self.return_propensity(
                    product=line["product"],
                    channel=line["channel"],
                    customer_segment=line.get("customer_segment"),
                    quantity=float(line["quantity"]),
                ),
                "due_tick": max(self.current_tick + 1, delivered_tick - self.random.randint(0, 1)),
            }
            self.fulfilled_sales.append(sale_snapshot)
            self.pending_freights.append(sale_snapshot)
        if len(self.fulfilled_sales) > 400:
            self.fulfilled_sales = self.fulfilled_sales[-250:]
        if len(self.pending_freights) > 200:
            self.pending_freights = self.pending_freights[-120:]
        self.pending_sale_lines = lines[1:]
        line = lines[0]
        settlement_amount = round(line["net_amount"] + line["tax"] - line["marketplace_fee"], 2)
        self.update_liquidity(line["debit_account"], settlement_amount)
        return line

    def next_return(self) -> dict[str, Any]:
        candidates = self.returnable_sales()
        if not candidates:
            return self.next_sale()
        sale = self.choice_weighted(
            candidates,
            lambda item: float(item["returnable_quantity"]) * max(float(item.get("return_propensity", 0.01)), 0.004),
        )
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
        refund_account = sale["debit_account"]
        self.update_liquidity(refund_account, -round(net_amount + tax_amount, 2))
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
            "credit_account": refund_account,
        }

    def next_freight(self) -> dict[str, Any]:
        if not self.pending_freights:
            return self.next_sale()
        sale = self.pending_freights.pop(0)
        base_per_unit = 4.5 if sale["product"].product_category in {"Telefonia", "Eletronicos"} else 3.2
        freight_amount = round(base_per_unit * sale["quantity"] * self.random.uniform(0.95, 1.35), 2)
        bank_fee = round(max(freight_amount * self.random.uniform(0.008, 0.018), 0.35), 2)
        self.update_liquidity(self.account_code("bank_accounts"), -round(freight_amount + bank_fee, 2))
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
        self.current_tick += 1
        self._update_market_state()
        self.schedule_procurement()

        due_receipts = self.due_purchase_receipts()
        due_payables = self.due_supplier_payables()
        due_freights = [item for item in self.pending_freights if int(item.get("due_tick", self.current_tick)) <= self.current_tick]
        return_candidates = self.returnable_sales()
        low_stock_count = len(self.low_stock_products())

        actions: list[tuple[str, float]] = []
        if due_receipts:
            actions.append(("purchase", 1.6 + len(due_receipts) * 0.45))
        elif low_stock_count:
            actions.append(("purchase", 0.45 + low_stock_count * 0.22))
        if due_payables and self.available_liquidity() > 50:
            actions.append(("supplier_payment", 0.9 + len(due_payables) * 0.2))
        if due_freights:
            actions.append(("freight", 0.55 + len(due_freights) * 0.12))
        if return_candidates:
            eligible_units = sum(min(float(sale.get("returnable_quantity", 0.0)), 3.0) for sale in return_candidates)
            average_propensity = sum(float(sale.get("return_propensity", 0.01)) for sale in return_candidates) / max(len(return_candidates), 1)
            actions.append(("return", 0.015 + min(eligible_units, 80.0) * 0.015 * max(average_propensity, 0.01)))
        if self.available_products():
            sale_pressure = sum(self.demand_multiplier(product.product_id) for product in self.available_products()) / max(len(self.available_products()), 1)
            actions.append(("sale", max(1.35, 2.8 + sale_pressure - low_stock_count * 0.3)))

        if not actions:
            return self.next_purchase()

        action = self.choose_weighted_pair(actions)
        if action == "purchase":
            return self.next_purchase()
        if action == "supplier_payment":
            return self.next_supplier_payment()
        if action == "freight":
            return self.next_freight()
        if action == "return":
            return self.next_return()
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
