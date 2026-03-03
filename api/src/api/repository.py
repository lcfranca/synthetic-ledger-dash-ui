import random
from datetime import datetime, timezone


class DashboardRepository:
    async def get_summary(self) -> dict:
        inventory_value = round(random.uniform(100000, 500000), 2)
        cash_balance = round(random.uniform(50000, 200000), 2)
        revenue = round(random.uniform(10000, 60000), 2)
        expenses = round(random.uniform(5000, 30000), 2)
        net_income = round(revenue - expenses, 2)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "balance_sheet": {
                "assets": {
                    "cash": cash_balance,
                    "inventory": inventory_value,
                },
                "liabilities": {
                    "accounts_payable": round(random.uniform(5000, 25000), 2)
                },
            },
            "income_statement": {
                "revenue": revenue,
                "expenses": expenses,
                "net_income": net_income,
                "cmv": round(random.uniform(4000, 20000), 2),
            },
        }
