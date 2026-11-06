"""
NexusTrade — Mock ERP Module
===========================
Simulates four core ERP data tables for an e-commerce business:
  • Inventory  — product stock levels, reorder points, turnover, costs
  • Sales      — monthly revenue, orders, returns, cart abandonment, AOV
  • Customers  — RFM scores and segment tags
  • Suppliers  — lead time, reliability, pricing, bulk discounts

Supports multiple e-commerce business presets that the user can choose from.
The ERP exposes a simple API that the inference engine consumes as facts.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class Product:
    product_id: str
    name: str
    stock_level: int
    reorder_point: int
    avg_sales_rate: float        # units sold per month on average
    turnover_rate: float         # stock turnover ratio (0‑1 scale)
    unit_cost: float
    selling_price: float
    market_avg_price: float
    competitor_price: float
    category: str
    is_critical: bool = False
    seasonal_demand: str = "normal"   # "peak" | "low" | "normal"
    stockouts_last_month: int = 0


@dataclass
class SalesRecord:
    month: str                    # e.g. "2026-03"
    product_id: str
    revenue: float
    order_count: int
    return_rate: float            # 0‑1
    cart_abandonment_rate: float  # 0‑1
    avg_order_value: float
    new_customer_ratio: float     # 0‑1


@dataclass
class Customer:
    customer_id: str
    name: str
    recency_days: int             # days since last purchase
    frequency: int                # number of purchases
    monetary_value: float         # total spend
    segment: str = "unclassified"


@dataclass
class Supplier:
    supplier_id: str
    name: str
    product_id: str
    lead_time_days: int
    reliability_score: float      # 0‑100
    price_per_unit: float
    previous_price: float
    bulk_discount_available: bool
    is_single_source: bool = False
    has_alternative: bool = True


# ── Business Presets ─────────────────────────────────────────────────────────

BUSINESS_PRESETS = {
    "tech_electronics": {
        "name": "TechVault Electronics",
        "description": "Online electronics & gadgets store — laptops, earbuds, hubs, smart devices",
        "icon": "💻",
        "products": [
            Product("P001", "Wireless Earbuds Pro", stock_level=320, reorder_point=100, avg_sales_rate=200, turnover_rate=0.7, unit_cost=25.00, selling_price=59.99, market_avg_price=54.99, competitor_price=52.99, category="electronics", is_critical=True, seasonal_demand="peak", stockouts_last_month=0),
            Product("P002", "USB-C Hub 7-in-1", stock_level=30, reorder_point=50, avg_sales_rate=90, turnover_rate=0.85, unit_cost=12.00, selling_price=29.99, market_avg_price=27.99, competitor_price=26.99, category="electronics", is_critical=True, seasonal_demand="normal", stockouts_last_month=1),
            Product("P003", "Mechanical Keyboard RGB", stock_level=500, reorder_point=60, avg_sales_rate=80, turnover_rate=0.2, unit_cost=35.00, selling_price=89.99, market_avg_price=82.00, competitor_price=79.99, category="electronics", is_critical=False, seasonal_demand="low", stockouts_last_month=0),
            Product("P004", "Smart Watch Band", stock_level=45, reorder_point=80, avg_sales_rate=120, turnover_rate=0.9, unit_cost=3.00, selling_price=14.99, market_avg_price=12.99, competitor_price=11.99, category="accessories", is_critical=False, seasonal_demand="normal", stockouts_last_month=3),
            Product("P005", "Portable Charger 20000mAh", stock_level=200, reorder_point=40, avg_sales_rate=50, turnover_rate=0.4, unit_cost=15.00, selling_price=39.99, market_avg_price=36.99, competitor_price=34.99, category="electronics", is_critical=False, seasonal_demand="peak", stockouts_last_month=0),
        ],
        "sales": [
            SalesRecord("2026-03", "P001", revenue=12000, order_count=200, return_rate=0.05, cart_abandonment_rate=0.35, avg_order_value=60.0, new_customer_ratio=0.30),
            SalesRecord("2026-03", "P002", revenue=2700, order_count=90, return_rate=0.08, cart_abandonment_rate=0.40, avg_order_value=30.0, new_customer_ratio=0.22),
            SalesRecord("2026-03", "P003", revenue=7200, order_count=80, return_rate=0.18, cart_abandonment_rate=0.72, avg_order_value=90.0, new_customer_ratio=0.15),
            SalesRecord("2026-03", "P004", revenue=1800, order_count=120, return_rate=0.02, cart_abandonment_rate=0.45, avg_order_value=15.0, new_customer_ratio=0.25),
            SalesRecord("2026-03", "P005", revenue=2000, order_count=50, return_rate=0.03, cart_abandonment_rate=0.55, avg_order_value=40.0, new_customer_ratio=0.18),
            SalesRecord("2026-02", "P001", revenue=15000, order_count=250, return_rate=0.04, cart_abandonment_rate=0.30, avg_order_value=60.0, new_customer_ratio=0.35),
            SalesRecord("2026-02", "P002", revenue=3200, order_count=110, return_rate=0.06, cart_abandonment_rate=0.38, avg_order_value=29.1, new_customer_ratio=0.25),
            SalesRecord("2026-02", "P003", revenue=9000, order_count=100, return_rate=0.15, cart_abandonment_rate=0.65, avg_order_value=90.0, new_customer_ratio=0.20),
            SalesRecord("2026-02", "P004", revenue=2100, order_count=140, return_rate=0.02, cart_abandonment_rate=0.40, avg_order_value=15.0, new_customer_ratio=0.28),
            SalesRecord("2026-02", "P005", revenue=2200, order_count=56, return_rate=0.03, cart_abandonment_rate=0.50, avg_order_value=39.3, new_customer_ratio=0.20),
        ],
        "customers": [
            Customer("C001", "Alice Johnson", recency_days=5, frequency=12, monetary_value=1500.00),
            Customer("C002", "Bob Smith", recency_days=95, frequency=6, monetary_value=450.00),
            Customer("C003", "Carol Williams", recency_days=200, frequency=2, monetary_value=120.00),
            Customer("C004", "David Lee", recency_days=10, frequency=1, monetary_value=35.00),
            Customer("C005", "Eve Martinez", recency_days=20, frequency=8, monetary_value=980.00),
            Customer("C006", "Frank Chen", recency_days=3, frequency=15, monetary_value=2200.00),
            Customer("C007", "Grace Kim", recency_days=120, frequency=4, monetary_value=310.00),
            Customer("C008", "Hank Patel", recency_days=45, frequency=3, monetary_value=275.00),
        ],
        "suppliers": [
            Supplier("S001", "TechSource Ltd", product_id="P001", lead_time_days=5, reliability_score=92.0, price_per_unit=25.00, previous_price=24.00, bulk_discount_available=True, is_single_source=False, has_alternative=True),
            Supplier("S002", "ChipConnect Inc", product_id="P002", lead_time_days=18, reliability_score=65.0, price_per_unit=13.20, previous_price=12.00, bulk_discount_available=False, is_single_source=True, has_alternative=False),
            Supplier("S003", "KeyMasters Co", product_id="P003", lead_time_days=3, reliability_score=88.0, price_per_unit=35.00, previous_price=33.00, bulk_discount_available=True, is_single_source=False, has_alternative=True),
            Supplier("S004", "BandFactory", product_id="P004", lead_time_days=10, reliability_score=55.0, price_per_unit=3.30, previous_price=2.80, bulk_discount_available=False, is_single_source=True, has_alternative=True),
            Supplier("S005", "PowerCell Supply", product_id="P005", lead_time_days=7, reliability_score=78.0, price_per_unit=15.00, previous_price=14.50, bulk_discount_available=False, is_single_source=False, has_alternative=True),
        ],
    },

    "fashion_boutique": {
        "name": "Velvet & Thread Fashion",
        "description": "Online fashion boutique — dresses, sneakers, handbags, jewelry, sunglasses",
        "icon": "👗",
        "products": [
            Product("P001", "Summer Floral Dress", stock_level=380, reorder_point=70, avg_sales_rate=150, turnover_rate=0.6, unit_cost=18.00, selling_price=65.99, market_avg_price=59.99, competitor_price=54.99, category="clothing", is_critical=False, seasonal_demand="peak", stockouts_last_month=0),
            Product("P002", "Classic Sneakers", stock_level=25, reorder_point=60, avg_sales_rate=110, turnover_rate=0.92, unit_cost=22.00, selling_price=79.99, market_avg_price=74.99, competitor_price=69.99, category="footwear", is_critical=True, seasonal_demand="normal", stockouts_last_month=4),
            Product("P003", "Leather Handbag", stock_level=150, reorder_point=20, avg_sales_rate=30, turnover_rate=0.18, unit_cost=40.00, selling_price=129.99, market_avg_price=119.99, competitor_price=109.99, category="accessories", is_critical=False, seasonal_demand="normal", stockouts_last_month=0),
            Product("P004", "Gold Pendant Necklace", stock_level=40, reorder_point=35, avg_sales_rate=45, turnover_rate=0.75, unit_cost=15.00, selling_price=49.99, market_avg_price=44.99, competitor_price=42.99, category="jewelry", is_critical=True, seasonal_demand="peak", stockouts_last_month=0),
            Product("P005", "Designer Sunglasses", stock_level=300, reorder_point=50, avg_sales_rate=60, turnover_rate=0.25, unit_cost=12.00, selling_price=44.99, market_avg_price=39.99, competitor_price=37.99, category="accessories", is_critical=False, seasonal_demand="peak", stockouts_last_month=0),
        ],
        "sales": [
            SalesRecord("2026-03", "P001", revenue=9900, order_count=150, return_rate=0.22, cart_abandonment_rate=0.60, avg_order_value=66.0, new_customer_ratio=0.35),
            SalesRecord("2026-03", "P002", revenue=8800, order_count=110, return_rate=0.10, cart_abandonment_rate=0.38, avg_order_value=80.0, new_customer_ratio=0.28),
            SalesRecord("2026-03", "P003", revenue=3900, order_count=30, return_rate=0.05, cart_abandonment_rate=0.75, avg_order_value=130.0, new_customer_ratio=0.12),
            SalesRecord("2026-03", "P004", revenue=2250, order_count=45, return_rate=0.03, cart_abandonment_rate=0.42, avg_order_value=50.0, new_customer_ratio=0.18),
            SalesRecord("2026-03", "P005", revenue=2700, order_count=60, return_rate=0.08, cart_abandonment_rate=0.58, avg_order_value=45.0, new_customer_ratio=0.15),
            SalesRecord("2026-02", "P001", revenue=7500, order_count=120, return_rate=0.20, cart_abandonment_rate=0.55, avg_order_value=62.5, new_customer_ratio=0.30),
            SalesRecord("2026-02", "P002", revenue=12000, order_count=150, return_rate=0.08, cart_abandonment_rate=0.35, avg_order_value=80.0, new_customer_ratio=0.32),
            SalesRecord("2026-02", "P003", revenue=5200, order_count=40, return_rate=0.04, cart_abandonment_rate=0.70, avg_order_value=130.0, new_customer_ratio=0.15),
            SalesRecord("2026-02", "P004", revenue=2500, order_count=50, return_rate=0.03, cart_abandonment_rate=0.40, avg_order_value=50.0, new_customer_ratio=0.20),
            SalesRecord("2026-02", "P005", revenue=3000, order_count=66, return_rate=0.07, cart_abandonment_rate=0.52, avg_order_value=45.5, new_customer_ratio=0.19),
        ],
        "customers": [
            Customer("C001", "Sophia Laurent", recency_days=2, frequency=18, monetary_value=3200.00),
            Customer("C002", "Marcus Brown", recency_days=100, frequency=5, monetary_value=520.00),
            Customer("C003", "Lina Chen", recency_days=250, frequency=1, monetary_value=65.00),
            Customer("C004", "Jake Miller", recency_days=8, frequency=1, monetary_value=80.00),
            Customer("C005", "Priya Sharma", recency_days=15, frequency=9, monetary_value=1100.00),
            Customer("C006", "Omar Hassan", recency_days=60, frequency=3, monetary_value=240.00),
            Customer("C007", "Mia Torres", recency_days=150, frequency=7, monetary_value=890.00),
            Customer("C008", "Ethan Park", recency_days=25, frequency=6, monetary_value=720.00),
        ],
        "suppliers": [
            Supplier("S001", "TextileCraft Global", product_id="P001", lead_time_days=12, reliability_score=72.0, price_per_unit=18.00, previous_price=15.50, bulk_discount_available=True, is_single_source=False, has_alternative=True),
            Supplier("S002", "SoleMakers Ltd", product_id="P002", lead_time_days=20, reliability_score=58.0, price_per_unit=24.00, previous_price=22.00, bulk_discount_available=False, is_single_source=True, has_alternative=True),
            Supplier("S003", "LeatherLux Import", product_id="P003", lead_time_days=8, reliability_score=90.0, price_per_unit=40.00, previous_price=38.00, bulk_discount_available=True, is_single_source=False, has_alternative=True),
            Supplier("S004", "GoldChain Direct", product_id="P004", lead_time_days=4, reliability_score=95.0, price_per_unit=15.00, previous_price=14.80, bulk_discount_available=False, is_single_source=True, has_alternative=False),
            Supplier("S005", "OpticStyle Co", product_id="P005", lead_time_days=6, reliability_score=80.0, price_per_unit=12.00, previous_price=11.00, bulk_discount_available=False, is_single_source=False, has_alternative=True),
        ],
    },

    "health_wellness": {
        "name": "PureLife Wellness",
        "description": "Health & wellness e-store — supplements, yoga gear, organic teas, candles, fitness trackers",
        "icon": "🌿",
        "products": [
            Product("P001", "Organic Protein Powder", stock_level=90, reorder_point=100, avg_sales_rate=130, turnover_rate=0.88, unit_cost=18.00, selling_price=44.99, market_avg_price=42.99, competitor_price=39.99, category="supplements", is_critical=True, seasonal_demand="normal", stockouts_last_month=2),
            Product("P002", "Yoga Mat Premium", stock_level=400, reorder_point=50, avg_sales_rate=70, turnover_rate=0.15, unit_cost=10.00, selling_price=34.99, market_avg_price=32.00, competitor_price=29.99, category="fitness", is_critical=False, seasonal_demand="low", stockouts_last_month=0),
            Product("P003", "Organic Green Tea (50-pack)", stock_level=55, reorder_point=80, avg_sales_rate=140, turnover_rate=0.92, unit_cost=4.50, selling_price=12.99, market_avg_price=11.99, competitor_price=11.49, category="beverages", is_critical=False, seasonal_demand="normal", stockouts_last_month=3),
            Product("P004", "Aromatherapy Candle Set", stock_level=250, reorder_point=40, avg_sales_rate=55, turnover_rate=0.35, unit_cost=8.00, selling_price=28.99, market_avg_price=25.99, competitor_price=24.99, category="wellness", is_critical=False, seasonal_demand="peak", stockouts_last_month=0),
            Product("P005", "Fitness Tracker Band", stock_level=35, reorder_point=45, avg_sales_rate=85, turnover_rate=0.8, unit_cost=20.00, selling_price=59.99, market_avg_price=54.99, competitor_price=49.99, category="electronics", is_critical=True, seasonal_demand="peak", stockouts_last_month=0),
        ],
        "sales": [
            SalesRecord("2026-03", "P001", revenue=5850, order_count=130, return_rate=0.04, cart_abandonment_rate=0.32, avg_order_value=45.0, new_customer_ratio=0.28),
            SalesRecord("2026-03", "P002", revenue=2450, order_count=70, return_rate=0.12, cart_abandonment_rate=0.68, avg_order_value=35.0, new_customer_ratio=0.10),
            SalesRecord("2026-03", "P003", revenue=1820, order_count=140, return_rate=0.02, cart_abandonment_rate=0.42, avg_order_value=13.0, new_customer_ratio=0.24),
            SalesRecord("2026-03", "P004", revenue=1595, order_count=55, return_rate=0.03, cart_abandonment_rate=0.50, avg_order_value=29.0, new_customer_ratio=0.16),
            SalesRecord("2026-03", "P005", revenue=5100, order_count=85, return_rate=0.06, cart_abandonment_rate=0.44, avg_order_value=60.0, new_customer_ratio=0.20),
            SalesRecord("2026-02", "P001", revenue=7200, order_count=160, return_rate=0.03, cart_abandonment_rate=0.28, avg_order_value=45.0, new_customer_ratio=0.32),
            SalesRecord("2026-02", "P002", revenue=3150, order_count=90, return_rate=0.10, cart_abandonment_rate=0.62, avg_order_value=35.0, new_customer_ratio=0.14),
            SalesRecord("2026-02", "P003", revenue=2100, order_count=160, return_rate=0.02, cart_abandonment_rate=0.38, avg_order_value=13.1, new_customer_ratio=0.28),
            SalesRecord("2026-02", "P004", revenue=1700, order_count=60, return_rate=0.03, cart_abandonment_rate=0.48, avg_order_value=28.3, new_customer_ratio=0.19),
            SalesRecord("2026-02", "P005", revenue=6800, order_count=110, return_rate=0.05, cart_abandonment_rate=0.40, avg_order_value=61.8, new_customer_ratio=0.25),
        ],
        "customers": [
            Customer("C001", "Nora Greenfield", recency_days=3, frequency=14, monetary_value=1800.00),
            Customer("C002", "James Cooper", recency_days=110, frequency=5, monetary_value=380.00),
            Customer("C003", "Yuki Tanaka", recency_days=190, frequency=2, monetary_value=95.00),
            Customer("C004", "Aisha Khan", recency_days=7, frequency=1, monetary_value=45.00),
            Customer("C005", "Leo Rivera", recency_days=18, frequency=10, monetary_value=1350.00),
            Customer("C006", "Dana Olsen", recency_days=4, frequency=20, monetary_value=2800.00),
            Customer("C007", "Raj Patel", recency_days=85, frequency=4, monetary_value=290.00),
            Customer("C008", "Chloe Adams", recency_days=35, frequency=6, monetary_value=560.00),
        ],
        "suppliers": [
            Supplier("S001", "NutraSource Wholesale", product_id="P001", lead_time_days=5, reliability_score=90.0, price_per_unit=18.00, previous_price=17.50, bulk_discount_available=True, is_single_source=False, has_alternative=True),
            Supplier("S002", "FitGear Wholesale", product_id="P002", lead_time_days=3, reliability_score=88.0, price_per_unit=10.00, previous_price=9.50, bulk_discount_available=True, is_single_source=False, has_alternative=True),
            Supplier("S003", "LeafOrigin Co", product_id="P003", lead_time_days=10, reliability_score=55.0, price_per_unit=4.80, previous_price=4.00, bulk_discount_available=False, is_single_source=True, has_alternative=True),
            Supplier("S004", "WaxWorks Supply", product_id="P004", lead_time_days=7, reliability_score=78.0, price_per_unit=8.00, previous_price=7.80, bulk_discount_available=False, is_single_source=False, has_alternative=True),
            Supplier("S005", "WearTech Direct", product_id="P005", lead_time_days=15, reliability_score=62.0, price_per_unit=22.00, previous_price=20.00, bulk_discount_available=False, is_single_source=True, has_alternative=False),
        ],
    },
}


def get_available_businesses() -> Dict[str, Dict[str, str]]:
    """Return {key: {name, description, icon}} for all presets."""
    return {
        key: {"name": v["name"], "description": v["description"], "icon": v["icon"]}
        for key, v in BUSINESS_PRESETS.items()
    }


# ── Mock ERP Database ────────────────────────────────────────────────────────

class MockERP:
    """Central mock ERP that holds all business data and exposes it as facts."""

    def __init__(self, business_key: str = "tech_electronics"):
        self.products: List[Product] = []
        self.sales: List[SalesRecord] = []
        self.customers: List[Customer] = []
        self.suppliers: List[Supplier] = []
        self.business_key: str = business_key
        self.business_name: str = ""
        self.business_description: str = ""
        self.business_icon: str = ""
        self._load_preset(business_key)

    def switch_business(self, business_key: str):
        """Switch to a different business preset."""
        self._load_preset(business_key)

    def sync_from_mongo(self) -> None:
        """
        Pull current Product/Customer/Supplier state from MongoDB into the
        in-memory dataclasses so the inference engine sees dashboard edits.

        Merge semantics: fields the dashboard can edit (stock, price, recency,
        lead_time, ...) are overwritten from Mongo; auxiliary fields the
        dashboard does NOT edit (competitor_price, seasonal_demand, etc.) are
        preserved on the existing in-memory record. Mongo records absent from
        memory are added with sensible defaults; in-memory records absent from
        Mongo are removed so deletes propagate.

        If MongoDB is unreachable, log a warning and leave state untouched —
        diagnosis still runs against whatever is in memory.
        """
        try:
            # Lazy import so CLI users who only use the in-memory presets
            # don't need MongoDB at all.
            from Database.models.products  import Product  as ProductDoc
            from Database.models.customers import Customer as CustomerDoc
            from Database.models.suppliers import Supplier as SupplierDoc
        except ImportError as e:
            print(f"  ⚠️  sync_from_mongo skipped (mongoengine models not importable): {e}")
            return

        try:
            mongo_products  = list(ProductDoc.objects())
            mongo_customers = list(CustomerDoc.objects())
            mongo_suppliers = list(SupplierDoc.objects())
        except Exception as e:
            print(f"  ⚠️  sync_from_mongo skipped (MongoDB query failed): {e}")
            return

        self._sync_products(mongo_products)
        self._sync_customers(mongo_customers)
        self._sync_suppliers(mongo_suppliers)

    def _sync_products(self, mongo_products) -> None:
        existing = {p.product_id: p for p in self.products}
        seen_ids = set()

        for mp in mongo_products:
            pid = mp.product_id
            seen_ids.add(pid)

            # Back-compute unit_cost from margin so extract_facts gives the
            # same margin% the user set in the dashboard. Guard against
            # margin == 100 which would imply zero cost.
            margin_pct = max(0.0, min(99.99, float(mp.margin or 0)))
            unit_cost  = round(float(mp.price) * (1 - margin_pct / 100.0), 4)

            if pid in existing:
                p = existing[pid]
                p.stock_level    = int(mp.stock)
                p.reorder_point  = int(mp.reorder_level)
                p.turnover_rate  = float(mp.turnover)
                p.selling_price  = float(mp.price)
                p.unit_cost      = unit_cost
            else:
                # New product added via dashboard — fill in plausible defaults
                # for fields the form doesn't cover.
                p = Product(
                    product_id           = pid,
                    name                 = mp.name,
                    stock_level          = int(mp.stock),
                    reorder_point        = int(mp.reorder_level),
                    avg_sales_rate       = max(int(mp.stock) // 2, 50),
                    turnover_rate        = float(mp.turnover),
                    unit_cost            = unit_cost,
                    selling_price        = float(mp.price),
                    market_avg_price     = float(mp.price),
                    competitor_price     = round(float(mp.price) * 0.95, 2),
                    category             = "general",
                    is_critical          = False,
                    seasonal_demand      = "normal",
                    stockouts_last_month = 0,
                )
                self.products.append(p)
                existing[pid] = p

            # Always refresh the name (cheap, lets renames propagate)
            p.name = mp.name

            # Sync the latest sales record so revenue / returns / cart_abandon
            # values from Mongo flow into extract_facts().
            self._upsert_latest_sales(
                product_id        = pid,
                revenue           = float(mp.revenue),
                revenue_delta_pct = float(mp.revenue_delta),
                return_rate       = float(mp.returns) / 100.0,
                cart_abandon_rate = float(mp.cart_abandonment) / 100.0,
            )

        # Drop in-memory products no longer in Mongo, plus their sales and any
        # suppliers pointing at them (sync_suppliers below will repopulate).
        self.products  = [p for p in self.products  if p.product_id in seen_ids]
        self.sales     = [s for s in self.sales     if s.product_id in seen_ids]
        self.suppliers = [s for s in self.suppliers if s.product_id in seen_ids]

    def _sync_customers(self, mongo_customers) -> None:
        existing = {c.customer_id: c for c in self.customers}
        seen_ids = set()

        for mc in mongo_customers:
            cid = mc.customer_id
            seen_ids.add(cid)
            if cid in existing:
                c = existing[cid]
                c.name           = mc.name
                c.recency_days   = int(mc.recency)
                c.frequency      = int(mc.frequency)
                c.monetary_value = float(mc.monetary)
                # segment is set by inference (R11–R14); don't overwrite
            else:
                self.customers.append(Customer(
                    customer_id    = cid,
                    name           = mc.name,
                    recency_days   = int(mc.recency),
                    frequency      = int(mc.frequency),
                    monetary_value = float(mc.monetary),
                    segment        = "unclassified",
                ))

        self.customers = [c for c in self.customers if c.customer_id in seen_ids]

    def _sync_suppliers(self, mongo_suppliers) -> None:
        existing = {s.supplier_id: s for s in self.suppliers}
        seen_ids = set()

        for ms in mongo_suppliers:
            sid = ms.supplier_id
            seen_ids.add(sid)
            referenced_pid = ms.product.product_id if ms.product else ""
            price_delta = float(ms.price_delta or 0.0)
            price       = float(ms.price_per_unit)
            # Back-compute previous_price so extract_facts derives the same
            # price_increase_pct the dashboard shows.
            previous_price = price / (1 + price_delta / 100.0) if price_delta and price else price

            if sid in existing:
                s = existing[sid]
                s.name                    = ms.name
                s.product_id              = referenced_pid
                s.lead_time_days          = int(ms.lead_time)
                s.reliability_score       = float(ms.reliability)
                s.price_per_unit          = price
                s.previous_price          = previous_price
                s.bulk_discount_available = bool(ms.bulk_available)
                s.is_single_source        = bool(ms.single_source)
            else:
                self.suppliers.append(Supplier(
                    supplier_id             = sid,
                    name                    = ms.name,
                    product_id              = referenced_pid,
                    lead_time_days          = int(ms.lead_time),
                    reliability_score       = float(ms.reliability),
                    price_per_unit          = price,
                    previous_price          = previous_price,
                    bulk_discount_available = bool(ms.bulk_available),
                    is_single_source        = bool(ms.single_source),
                    has_alternative         = True,
                ))

        self.suppliers = [s for s in self.suppliers if s.supplier_id in seen_ids]

    def _upsert_latest_sales(self, product_id: str, revenue: float,
                             revenue_delta_pct: float, return_rate: float,
                             cart_abandon_rate: float) -> None:
        """Update the latest SalesRecord for `product_id` with values edited
        via the dashboard. Adjust the previous month's revenue so the derived
        revenue_delta matches what the user set."""
        latest   = self.get_latest_sales(product_id)
        previous = self.get_previous_sales(product_id)

        if latest is None:
            # No history yet — fabricate one current record so the sales
            # rules (R21–R25) have something to compare against later.
            latest = SalesRecord(
                month                 = "2026-03",
                product_id            = product_id,
                revenue               = revenue,
                order_count           = 100,
                return_rate           = return_rate,
                cart_abandonment_rate = cart_abandon_rate,
                avg_order_value       = max(revenue / 100, 1.0),
                new_customer_ratio    = 0.20,
            )
            self.sales.append(latest)
        else:
            latest.revenue               = revenue
            latest.return_rate           = return_rate
            latest.cart_abandonment_rate = cart_abandon_rate

        # Honor user-set revenue_delta by adjusting the previous record.
        if revenue_delta_pct and revenue:
            denom = 1 + revenue_delta_pct / 100.0
            if denom:
                implied_prev_rev = revenue / denom
                if previous is None:
                    self.sales.append(SalesRecord(
                        month                 = "2026-02",
                        product_id            = product_id,
                        revenue               = implied_prev_rev,
                        order_count           = 100,
                        return_rate           = return_rate,
                        cart_abandonment_rate = cart_abandon_rate,
                        avg_order_value       = max(implied_prev_rev / 100, 1.0),
                        new_customer_ratio    = 0.20,
                    ))
                else:
                    previous.revenue = implied_prev_rev

    def _load_preset(self, business_key: str):
        """Load a business preset by key."""
        if business_key not in BUSINESS_PRESETS:
            raise ValueError(
                f"Unknown business: '{business_key}'. "
                f"Available: {list(BUSINESS_PRESETS.keys())}"
            )
        preset = BUSINESS_PRESETS[business_key]
        self.business_key = business_key
        self.business_name = preset["name"]
        self.business_description = preset["description"]
        self.business_icon = preset["icon"]
        self.products = list(preset["products"])
        self.sales = list(preset["sales"])
        self.customers = list(preset["customers"])
        self.suppliers = list(preset["suppliers"])
        # Reset customer segments for fresh inference
        for c in self.customers:
            c.segment = "unclassified"

    # ── Public API ───────────────────────────────────────────────────────

    def get_all_products(self) -> List[Product]:
        return self.products

    def get_product(self, product_id: str) -> Optional[Product]:
        return next((p for p in self.products if p.product_id == product_id), None)

    def get_sales(self, product_id: str = None) -> List[SalesRecord]:
        if product_id:
            return [s for s in self.sales if s.product_id == product_id]
        return self.sales

    def get_latest_sales(self, product_id: str) -> Optional[SalesRecord]:
        records = sorted(
            [s for s in self.sales if s.product_id == product_id],
            key=lambda s: s.month, reverse=True
        )
        return records[0] if records else None

    def get_previous_sales(self, product_id: str) -> Optional[SalesRecord]:
        records = sorted(
            [s for s in self.sales if s.product_id == product_id],
            key=lambda s: s.month, reverse=True
        )
        return records[1] if len(records) > 1 else None

    def get_all_customers(self) -> List[Customer]:
        return self.customers

    def get_customer(self, customer_id: str) -> Optional[Customer]:
        return next((c for c in self.customers if c.customer_id == customer_id), None)

    def get_all_suppliers(self) -> List[Supplier]:
        return self.suppliers

    def get_suppliers_for_product(self, product_id: str) -> List[Supplier]:
        return [s for s in self.suppliers if s.product_id == product_id]

    def get_total_revenue_share(self) -> Dict[str, float]:
        """Return each product's share of total revenue for the latest month."""
        latest_sales = {}
        for s in self.sales:
            if s.product_id not in latest_sales or s.month > latest_sales[s.product_id].month:
                latest_sales[s.product_id] = s
        total = sum(s.revenue for s in latest_sales.values())
        if total == 0:
            return {}
        return {pid: (s.revenue / total) * 100 for pid, s in latest_sales.items()}

    # ── Fact Extraction (used by inference engine) ───────────────────────

    def extract_facts(self) -> Dict[str, Any]:
        """
        Convert all ERP data into a flat dictionary of facts
        that the inference engine can reason over.
        """
        facts: Dict[str, Any] = {}

        # ── Product / Inventory facts
        for p in self.products:
            pid = p.product_id
            facts[f"product_{pid}_stock"] = p.stock_level
            facts[f"product_{pid}_reorder_point"] = p.reorder_point
            facts[f"product_{pid}_avg_sales_rate"] = p.avg_sales_rate
            facts[f"product_{pid}_turnover_rate"] = p.turnover_rate
            facts[f"product_{pid}_unit_cost"] = p.unit_cost
            facts[f"product_{pid}_selling_price"] = p.selling_price
            facts[f"product_{pid}_market_avg_price"] = p.market_avg_price
            facts[f"product_{pid}_competitor_price"] = p.competitor_price
            facts[f"product_{pid}_category"] = p.category
            facts[f"product_{pid}_is_critical"] = p.is_critical
            facts[f"product_{pid}_seasonal_demand"] = p.seasonal_demand
            facts[f"product_{pid}_stockouts_last_month"] = p.stockouts_last_month
            # Derived
            margin = ((p.selling_price - p.unit_cost) / p.selling_price) * 100 if p.selling_price else 0
            facts[f"product_{pid}_margin_pct"] = round(margin, 2)
            stock_vs_avg = (p.stock_level / p.avg_sales_rate) * 100 if p.avg_sales_rate else 0
            facts[f"product_{pid}_stock_vs_avg_sales_pct"] = round(stock_vs_avg, 2)
            facts[f"product_{pid}_stock_sufficient"] = p.stock_level >= p.reorder_point

        # ── Sales facts
        for p in self.products:
            pid = p.product_id
            latest = self.get_latest_sales(pid)
            previous = self.get_previous_sales(pid)
            if latest:
                facts[f"sales_{pid}_latest_revenue"] = latest.revenue
                facts[f"sales_{pid}_order_count"] = latest.order_count
                facts[f"sales_{pid}_return_rate"] = latest.return_rate
                facts[f"sales_{pid}_cart_abandonment_rate"] = latest.cart_abandonment_rate
                facts[f"sales_{pid}_avg_order_value"] = latest.avg_order_value
                facts[f"sales_{pid}_new_customer_ratio"] = latest.new_customer_ratio
            if latest and previous:
                rev_ratio = (latest.revenue / previous.revenue) * 100 if previous.revenue else 100
                facts[f"sales_{pid}_revenue_vs_last_month_pct"] = round(rev_ratio, 2)
                aov_change = ((latest.avg_order_value - previous.avg_order_value) / previous.avg_order_value) * 100 if previous.avg_order_value else 0
                facts[f"sales_{pid}_aov_change_pct"] = round(aov_change, 2)

        # ── Revenue‑share facts
        revenue_shares = self.get_total_revenue_share()
        for pid, share in revenue_shares.items():
            facts[f"sales_{pid}_revenue_share_pct"] = round(share, 2)

        # ── Customer facts
        # NOTE: customer_{cid}_segment is intentionally NOT seeded here.
        # It's an *inferred* fact produced by R11–R14. Seeding it would
        # poison the skip-if-already-set logic in ForwardChainer and block
        # those rules from ever firing.
        for c in self.customers:
            cid = c.customer_id
            facts[f"customer_{cid}_recency"] = c.recency_days
            facts[f"customer_{cid}_frequency"] = c.frequency
            facts[f"customer_{cid}_monetary"] = c.monetary_value

        # ── Supplier facts
        for s in self.suppliers:
            sid = s.supplier_id
            facts[f"supplier_{sid}_product"] = s.product_id
            facts[f"supplier_{sid}_lead_time"] = s.lead_time_days
            facts[f"supplier_{sid}_reliability"] = s.reliability_score
            facts[f"supplier_{sid}_price"] = s.price_per_unit
            facts[f"supplier_{sid}_previous_price"] = s.previous_price
            facts[f"supplier_{sid}_bulk_discount"] = s.bulk_discount_available
            facts[f"supplier_{sid}_single_source"] = s.is_single_source
            facts[f"supplier_{sid}_has_alternative"] = s.has_alternative
            # Derived
            price_increase_pct = ((s.price_per_unit - s.previous_price) / s.previous_price) * 100 if s.previous_price else 0
            facts[f"supplier_{sid}_price_increase_pct"] = round(price_increase_pct, 2)

        return facts

    # ── Pretty Print ─────────────────────────────────────────────────────

    def print_summary(self):
        """Print a readable summary of all ERP data."""
        print("=" * 70)
        print(f"  {self.business_icon} {self.business_name} — ERP Data Summary")
        print(f"  {self.business_description}")
        print("=" * 70)

        print("\n📦 INVENTORY")
        print("-" * 70)
        print(f"{'ID':<6} {'Product':<30} {'Stock':>6} {'Reorder':>8} {'Turnover':>9} {'Price':>8}")
        print("-" * 70)
        for p in self.products:
            print(f"{p.product_id:<6} {p.name:<30} {p.stock_level:>6} {p.reorder_point:>8} {p.turnover_rate:>9.2f} ${p.selling_price:>7.2f}")

        print("\n📊 SALES (Latest Month)")
        print("-" * 70)
        print(f"{'Product':<6} {'Revenue':>10} {'Orders':>7} {'Return%':>8} {'Cart Abd%':>10} {'AOV':>8}")
        print("-" * 70)
        for p in self.products:
            s = self.get_latest_sales(p.product_id)
            if s:
                print(f"{s.product_id:<6} ${s.revenue:>9,.0f} {s.order_count:>7} {s.return_rate:>7.0%} {s.cart_abandonment_rate:>9.0%} ${s.avg_order_value:>7.2f}")

        print("\n👥 CUSTOMERS")
        print("-" * 70)
        print(f"{'ID':<6} {'Name':<20} {'Recency':>8} {'Freq':>5} {'Monetary':>10} {'Segment':<15}")
        print("-" * 70)
        for c in self.customers:
            print(f"{c.customer_id:<6} {c.name:<20} {c.recency_days:>5} d  {c.frequency:>5} ${c.monetary_value:>9,.2f} {c.segment:<15}")

        print("\n🏭 SUPPLIERS")
        print("-" * 70)
        print(f"{'ID':<6} {'Supplier':<22} {'For':>5} {'Lead':>5} {'Reliability':>12} {'Price':>8} {'Bulk':>5}")
        print("-" * 70)
        for s in self.suppliers:
            bulk = "Yes" if s.bulk_discount_available else "No"
            print(f"{s.supplier_id:<6} {s.name:<22} {s.product_id:>5} {s.lead_time_days:>4}d {s.reliability_score:>10.0f}% ${s.price_per_unit:>7.2f} {bulk:>5}")
        print()


# ── Quick test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Available businesses:")
    for key, info in get_available_businesses().items():
        print(f"  {info['icon']} {key}: {info['name']} — {info['description']}")

    print()
    for key in BUSINESS_PRESETS:
        erp = MockERP(key)
        erp.print_summary()
