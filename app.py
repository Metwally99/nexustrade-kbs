"""
NexusTrade — Flask Web Dashboard
================================
A stunning, colorful web interface for the NexusTrade Knowledge-Based System.
Features glassmorphism design, animated gradients, interactive cards,
business preset selector, and comprehensive business intelligence visualization.
"""

import json
from flask import Flask, render_template_string, jsonify, request
from erp_module import MockERP, get_available_businesses
from knowledge_base import KnowledgeBase
from inference_engine import ForwardChainer, BackwardChainer
from explanation import ExplanationEngine

# Database (mongoengine)
from mongoengine import connect as me_connect
from Database.config import Config
from Database.models.products import Product
from Database.models.customers import Customer
from Database.models.suppliers import Supplier

app = Flask(__name__)

# ── Neo4j Graph API ────────────────────────────────────────────────────────
def _graph_data():
    """Return nodes and edges for the rule graph.
    Nodes: Domain, Rule, Condition (unique by fact_pattern).
    Edges: (Domain)<-[:IN_DOMAIN]-(Rule), (Rule)-[:HAS_CONDITION]->(Condition).
    """
    try:
        _kb = kb
    except NameError:
        _kb = KnowledgeBase()
    # Collect unique domains
    domains = {r.domain for r in _kb.rules}
    # Collect unique conditions by fact_pattern
    cond_map = {}
    for r in _kb.rules:
        for c in r.conditions:
            if c.fact_pattern not in cond_map:
                cond_map[c.fact_pattern] = c
    # Build node list
    nodes = []
    for d in domains:
        nodes.append({"data": {"id": f"domain_{d}", "label": d, "group": "domain"}})
    for r in _kb.rules:
        nodes.append({"data": {"id": r.rule_id, "label": r.rule_id, "group": "rule"}})
    for fp, c in cond_map.items():
        nid = f"cond_{fp}".replace(" ", "_")
        nodes.append({"data": {"id": nid, "label": fp, "group": "condition"}})
    # Build edge list
    edges = []
    for r in _kb.rules:
        # rule -> domain
        edges.append({"data": {"source": f"domain_{r.domain}", "target": r.rule_id, "type": "IN_DOMAIN"}})
        # rule -> conditions
        for c in r.conditions:
            cid = f"cond_{c.fact_pattern}".replace(" ", "_")
            edges.append({"data": {"source": r.rule_id, "target": cid, "type": "HAS_CONDITION"}})
    return {"nodes": nodes, "edges": edges}

@app.route("/api/graph")
def api_graph():
    """Expose the rule graph as JSON for the frontend visualizer."""
    data = _graph_data()
    return jsonify(data)


# ── MongoDB connection via mongoengine ───────────────────────────────────────
try:
    me_connect(db=Config.DB_NAME, host=Config.MONGO_URI,
               serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    # Probe connection immediately so we catch errors now, not at first query
    from mongoengine.connection import get_connection
    get_connection().server_info()
    print("  ✅ MongoDB Atlas connected")
except Exception as _mongo_err:
    print(f"  ⚠️  MongoDB Atlas unavailable ({_mongo_err.__class__.__name__}). Using in-memory mongomock.")
    import mongoengine
    mongoengine.disconnect_all()
    import mongomock
    from mongoengine import register_connection
    register_connection(alias="default", db="NexusTrade", mongo_client_class=mongomock.MongoClient)

# ── Global instances ─────────────────────────────────────────────────────────
erp = MockERP("tech_electronics")
kb = KnowledgeBase()
explainer = ExplanationEngine()


# ── Helper: run forward chaining and get structured results ──────────────────
def get_diagnosis_data():
    fc = ForwardChainer(kb, erp)
    fc.run()
    trace_data = explainer.get_trace_data(fc.trace)

    # ── Write inferred segments back to MongoDB ──────────────────────
    seg_map_display = {
        "VIP": "VIP", "at-risk": "At Risk", "at_risk": "At Risk",
        "churned": "Inactive", "new_customer": "Regular",
        "loyal": "Loyal", "regular": "Regular",
    }
    for key, val in fc.facts.items():
        if key.startswith("customer_") and key.endswith("_segment"):
            cid = key.split("_")[1]  # customer_C001_segment → C001
            cid_full = "C" + cid if not cid.startswith("C") else cid
            # re-parse: key = "customer_C001_segment"
            parts = key.split("_")
            cid_full = "_".join(parts[1:-1])  # handles e.g. C001
            mapped = seg_map_display.get(str(val), "Unclassified")
            try:
                c_obj = Customer.objects(customer_id=cid_full).first()
                if c_obj and c_obj.segment != mapped:
                    c_obj.segment = mapped
                    c_obj.save()
            except Exception:
                pass

    by_domain = {}
    for item in trace_data:
        by_domain.setdefault(item["domain"], []).append(item)

    # Summary stats — live counts from MongoDB
    total_fired = sum(1 for t in trace_data if t["fired"])
    unique_rules_fired = len(set(t["rule_id"] for t in trace_data if t["fired"]))
    domain_counts = {}
    for domain, items in by_domain.items():
        domain_counts[domain] = sum(1 for i in items if i["fired"])

    return {
        "trace": trace_data,
        "by_domain": by_domain,
        "total_rules": 25,
        "total_fired": total_fired,
        "unique_rules_fired": unique_rules_fired,
        "domain_counts": domain_counts,
        "facts": fc.facts,
        "db_counts": {
            "products": Product.objects.count(),
            "customers": Customer.objects.count(),
            "suppliers": Supplier.objects.count(),
        },
    }


# ── Seed MockERP data into MongoDB (upsert) ─────────────────────────────────

def seed_erp_to_db():
    """Push current MockERP data into MongoDB so the DB always has the base data."""
    for p in erp.get_all_products():
        latest = erp.get_latest_sales(p.product_id)
        prev = erp.get_previous_sales(p.product_id)
        margin = round(((p.selling_price - p.unit_cost) / p.selling_price) * 100, 1)
        rev_change = 0.0
        if latest and prev and prev.revenue:
            rev_change = round(((latest.revenue - prev.revenue) / prev.revenue) * 100, 1)

        obj = Product.objects(product_id=p.product_id).first()
        if not obj:
            obj = Product(product_id=p.product_id)
        obj.name = p.name
        obj.stock = p.stock_level
        obj.reorder_level = p.reorder_point
        obj.turnover = p.turnover_rate
        obj.price = p.selling_price
        obj.margin = margin
        obj.revenue = latest.revenue if latest else 0
        obj.revenue_delta = rev_change
        obj.returns = round(latest.return_rate * 100, 1) if latest else 0
        obj.cart_abandonment = round(latest.cart_abandonment_rate * 100, 1) if latest else 0
        obj.save()

    for c in erp.get_all_customers():
        obj = Customer.objects(customer_id=c.customer_id).first()
        if not obj:
            obj = Customer(customer_id=c.customer_id)
        obj.name = c.name
        obj.recency = c.recency_days
        obj.frequency = c.frequency
        obj.monetary = c.monetary_value
        # Map ERP segment values to the model's allowed choices
        seg_map = {
            "vip": "VIP", "loyal": "Loyal", "regular": "Regular",
            "at_risk": "At Risk", "at-risk": "At Risk",
            "inactive": "Inactive", "churned": "Inactive",
            "new_customer": "Regular", "premium": "VIP",
            "unclassified": "Unclassified",
        }
        raw_seg = (c.segment or "unclassified").lower().strip()
        obj.segment = seg_map.get(raw_seg, "Unclassified")
        obj.save()

    # Build a product lookup for supplier references
    product_lookup = {p.product_id: p for p in Product.objects()}
    for s in erp.get_all_suppliers():
        obj = Supplier.objects(supplier_id=s.supplier_id).first()
        if not obj:
            obj = Supplier(supplier_id=s.supplier_id)
        obj.name = s.name
        obj.product = product_lookup.get(s.product_id)
        obj.lead_time = s.lead_time_days
        obj.reliability = s.reliability_score
        obj.price_per_unit = s.price_per_unit
        obj.price_delta = round(((s.price_per_unit - s.previous_price) / s.previous_price) * 100, 1) if s.previous_price else 0
        obj.bulk_available = s.bulk_discount_available
        obj.single_source = s.is_single_source
        obj.save()

    print("  ✅ ERP data seeded to MongoDB")


# Run seed on startup
seed_erp_to_db()


# ── Read from MongoDB (sorted by ID) ────────────────────────────────────────

def get_db_erp_summary():
    """Return ERP data from MongoDB, sorted by ID."""
    products = []
    for p in Product.objects().order_by("product_id"):
        products.append({
            "id": p.product_id,
            "name": p.name,
            "stock": p.stock,
            "reorder_point": p.reorder_level,
            "turnover": p.turnover,
            "price": p.price,
            "margin": p.margin,
            "revenue": p.revenue,
            "rev_change": p.revenue_delta,
            "return_rate": p.returns,
            "cart_abandon": p.cart_abandonment,
        })

    customers = []
    for c in Customer.objects().order_by("customer_id"):
        customers.append({
            "id": c.customer_id,
            "name": c.name,
            "recency": c.recency,
            "frequency": c.frequency,
            "monetary": c.monetary,
            "segment": c.segment,
        })

    suppliers = []
    for s in Supplier.objects().order_by("supplier_id"):
        suppliers.append({
            "id": s.supplier_id,
            "name": s.name,
            "product_id": s.product.product_id if s.product else "—",
            "lead_time": s.lead_time,
            "reliability": s.reliability,
            "price": s.price_per_unit,
            "price_change": s.price_delta if s.price_delta else 0,
            "bulk": s.bulk_available,
            "single_source": s.single_source,
        })

    return {
        "products": products,
        "customers": customers,
        "suppliers": suppliers,
        "business_name": erp.business_name,
        "business_icon": erp.business_icon,
        "business_description": erp.business_description,
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/diagnosis")
def api_diagnosis():
    data = get_diagnosis_data()
    data.pop("facts", None)
    return jsonify(data)


@app.route("/api/erp")
def api_erp():
    return jsonify(get_db_erp_summary())


# ── CRUD: Add records to MongoDB ─────────────────────────────────────────────

@app.route("/api/products", methods=["POST"])
def api_add_product():
    d = request.get_json(force=True)
    pid = d.get("product_id", "").strip()
    if not pid:
        return jsonify({"error": "product_id is required."}), 400
    if Product.objects(product_id=pid).first():
        return jsonify({"error": f"Product ID '{pid}' already exists. Use a different ID."}), 400
    try:
        p = Product(
            product_id=pid,
            name=d["name"].strip(),
            stock=int(d["stock"]),
            reorder_level=int(d["reorder_level"]),
            turnover=float(d["turnover"]),
            price=float(d["price"]),
            margin=float(d["margin"]),
            revenue=float(d["revenue"]),
            revenue_delta=float(d["revenue_delta"]),
            returns=float(d["returns"]),
            cart_abandonment=float(d["cart_abandonment"]),
        )
        p.save()
        return jsonify({"success": True, "id": str(p.id)}), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/products/<product_id>", methods=["DELETE"])
def api_delete_product(product_id):
    obj = Product.objects(product_id=product_id).first()
    if not obj:
        return jsonify({"error": "Product not found."}), 404
    # Also delete any suppliers referencing this product
    Supplier.objects(product=obj).delete()
    obj.delete()
    return jsonify({"success": True})


@app.route("/api/customers", methods=["POST"])
def api_add_customer():
    d = request.get_json(force=True)
    cid = d.get("customer_id", "").strip()
    if not cid:
        return jsonify({"error": "customer_id is required."}), 400
    if Customer.objects(customer_id=cid).first():
        return jsonify({"error": f"Customer ID '{cid}' already exists. Use a different ID."}), 400
    try:
        c = Customer(
            customer_id=cid,
            name=d["name"].strip(),
            recency=int(d["recency"]),
            frequency=int(d["frequency"]),
            monetary=float(d["monetary"]),
            segment=d.get("segment", "Unclassified").strip() or "Unclassified",
        )
        c.save()
        return jsonify({"success": True, "id": str(c.id)}), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/customers/<customer_id>", methods=["DELETE"])
def api_delete_customer(customer_id):
    obj = Customer.objects(customer_id=customer_id).first()
    if not obj:
        return jsonify({"error": "Customer not found."}), 404
    obj.delete()
    return jsonify({"success": True})


@app.route("/api/suppliers", methods=["POST"])
def api_add_supplier():
    d = request.get_json(force=True)
    sid = d.get("supplier_id", "").strip()
    if not sid:
        return jsonify({"error": "supplier_id is required."}), 400
    if Supplier.objects(supplier_id=sid).first():
        return jsonify({"error": f"Supplier ID '{sid}' already exists. Use a different ID."}), 400
    product = Product.objects(product_id=d.get("product_id", "").strip()).first()
    if not product:
        return jsonify({"error": f"Product '{d.get('product_id')}' not found. Add the product first."}), 400
    try:
        s = Supplier(
            supplier_id=sid,
            name=d["name"].strip(),
            product=product,
            lead_time=int(d["lead_time"]),
            reliability=float(d["reliability"]),
            price_per_unit=float(d["price_per_unit"]),
            price_delta=float(d.get("price_delta", 0)),
            bulk_available=str(d.get("bulk_available", "false")).lower() in ("true", "1", "yes"),
            single_source=str(d.get("single_source", "false")).lower() in ("true", "1", "yes"),
        )
        s.save()
        return jsonify({"success": True, "id": str(s.id)}), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/suppliers/<supplier_id>", methods=["DELETE"])
def api_delete_supplier(supplier_id):
    obj = Supplier.objects(supplier_id=supplier_id).first()
    if not obj:
        return jsonify({"error": "Supplier not found."}), 404
    obj.delete()
    return jsonify({"success": True})


@app.route("/api/rules")
def api_rules():
    rules = []
    for r in kb.get_all_rules():
        conditions = []
        for c in r.conditions:
            conditions.append({
                "fact_pattern": c.fact_pattern,
                "operator": c.operator,
                "threshold": str(c.threshold),
                "description": c.description,
            })
        rules.append({
            "id": r.rule_id,
            "domain": r.domain,
            "description": r.description,
            "action": r.action,
            "priority": r.priority,
            "conditions": conditions,
        })
    return jsonify(rules)


@app.route("/api/businesses")
def api_businesses():
    all_businesses = get_available_businesses()
    businesses = {k: v for k, v in all_businesses.items() if k == "tech_electronics"}
    return jsonify({
        "businesses": businesses,
        "current": erp.business_key,
    })


@app.route("/api/switch_business", methods=["POST"])
def api_switch_business():
    global erp
    key = request.json.get("business_key", "")
    try:
        erp.switch_business(key)
        return jsonify({"success": True, "business": key, "name": erp.business_name})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/backward", methods=["POST"])
def api_backward():
    goal = request.json.get("goal", "")
    if not goal:
        return jsonify({"error": "No goal provided"}), 400

    # Pull latest dashboard edits from MongoDB into MockERP so backward
    # chaining reasons over fresh facts (same pattern as get_diagnosis_data).
    erp.sync_from_mongo()
    bc = BackwardChainer(kb, erp, ask_user=lambda x: None)
    success, trace = bc.run(goal)
    trace_data = explainer.get_trace_data(trace)

    return jsonify({
        "success": success,
        "goal": goal,
        "trace": trace_data,
    })


# ── HTML Template ────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexusTrade — E-Commerce Decision Intelligence</title>
    <!-- Cytoscape.js for graph visualization -->
    <script src="https://unpkg.com/cytoscape@3.28.0/dist/cytoscape.min.js"></script>
    <meta name="description" content="ERP-Integrated Knowledge-Based System for E-commerce Decision Support featuring AI-powered business diagnostics across pricing, inventory, customers, suppliers, and sales.">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
            --bg-primary: #0a0a1a; --bg-secondary: #111128;
            --bg-card: rgba(20, 20, 50, 0.6); --bg-card-hover: rgba(30, 30, 70, 0.8);
            --glass: rgba(255, 255, 255, 0.05); --glass-border: rgba(255, 255, 255, 0.1);
            --glass-highlight: rgba(255, 255, 255, 0.15);
            --text-primary: #f0f0ff; --text-secondary: #a0a0cc; --text-muted: #6b6b99;
            --accent-purple: #8b5cf6; --accent-blue: #3b82f6; --accent-cyan: #06b6d4;
            --accent-emerald: #10b981; --accent-amber: #f59e0b; --accent-rose: #f43f5e;
            --accent-pink: #ec4899; --accent-orange: #f97316;
            --gradient-primary: linear-gradient(135deg, #8b5cf6, #3b82f6, #06b6d4);
            --gradient-pricing: linear-gradient(135deg, #f59e0b, #f97316);
            --gradient-inventory: linear-gradient(135deg, #3b82f6, #06b6d4);
            --gradient-customer: linear-gradient(135deg, #ec4899, #8b5cf6);
            --gradient-supplier: linear-gradient(135deg, #10b981, #06b6d4);
            --gradient-sales: linear-gradient(135deg, #f43f5e, #f59e0b);
            --shadow-lg: 0 20px 60px rgba(0,0,0,0.4);
            --shadow-glow-purple: 0 0 30px rgba(139,92,246,0.3);
            --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px; --radius-xl: 24px;
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        html { scroll-behavior: smooth; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary); color: var(--text-primary);
            min-height: 100vh; overflow-x: hidden; line-height: 1.6;
        }

        /* ── Animated Background ─────────────────────────────────── */
        .bg-animation { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; overflow: hidden; pointer-events: none; }
        .bg-animation .orb { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.15; animation: float 20s ease-in-out infinite; }
        .bg-animation .orb:nth-child(1) { width: 600px; height: 600px; background: var(--accent-purple); top: -10%; left: -5%; animation-duration: 25s; }
        .bg-animation .orb:nth-child(2) { width: 500px; height: 500px; background: var(--accent-blue); top: 50%; right: -10%; animation-delay: -5s; animation-duration: 30s; }
        .bg-animation .orb:nth-child(3) { width: 400px; height: 400px; background: var(--accent-cyan); bottom: -10%; left: 30%; animation-delay: -10s; animation-duration: 22s; }
        .bg-animation .orb:nth-child(4) { width: 350px; height: 350px; background: var(--accent-pink); top: 30%; left: 50%; animation-delay: -15s; animation-duration: 28s; }
        @keyframes float {
            0%, 100% { transform: translate(0, 0) scale(1); }
            25% { transform: translate(50px, -30px) scale(1.1); }
            50% { transform: translate(-30px, 50px) scale(0.95); }
            75% { transform: translate(40px, 20px) scale(1.05); }
        }

        .app-container { position: relative; z-index: 1; max-width: 1400px; margin: 0 auto; padding: 20px; }

        /* ── Header ──────────────────────────────────────────────── */
        .header { text-align: center; padding: 30px 20px 10px; margin-bottom: 10px; }
        .header .logo {
            font-size: 3rem; font-weight: 900;
            background: var(--gradient-primary); -webkit-background-clip: text;
            -webkit-text-fill-color: transparent; background-clip: text;
            letter-spacing: -1px; margin-bottom: 6px; animation: shimmer 3s ease-in-out infinite;
        }
        @keyframes shimmer { 0%, 100% { filter: brightness(1); } 50% { filter: brightness(1.3); } }
        .header .subtitle { font-size: 1rem; color: var(--text-secondary); font-weight: 400; letter-spacing: 2px; text-transform: uppercase; }

        /* ── Business Selector ────────────────────────────────────── */
        .business-selector {
            display: flex; justify-content: center; gap: 12px;
            margin: 20px auto 24px; max-width: 900px; flex-wrap: wrap;
        }
        .business-card {
            flex: 1; min-width: 240px; max-width: 300px;
            padding: 18px 20px; background: var(--glass);
            border: 2px solid var(--glass-border); border-radius: var(--radius-lg);
            cursor: pointer; transition: var(--transition); text-align: center;
        }
        .business-card:hover {
            background: var(--glass-highlight); transform: translateY(-3px);
            border-color: rgba(139,92,246,0.4);
        }
        .business-card.active {
            border-color: var(--accent-purple);
            background: rgba(139,92,246,0.15);
            box-shadow: var(--shadow-glow-purple);
        }
        .business-card .biz-icon { font-size: 2rem; margin-bottom: 6px; }
        .business-card .biz-name { font-size: 0.95rem; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; }
        .business-card .biz-desc { font-size: 0.78rem; color: var(--text-muted); line-height: 1.4; }

        .current-business {
            text-align: center; margin-bottom: 20px;
            font-size: 0.88rem; color: var(--text-secondary);
        }
        .current-business strong { color: var(--accent-cyan); }

        /* ── Navigation ──────────────────────────────────────────── */
        .nav-tabs {
            display: flex; justify-content: center; gap: 6px; margin-bottom: 30px;
            flex-wrap: wrap; padding: 6px; background: var(--glass);
            border: 1px solid var(--glass-border); border-radius: var(--radius-xl);
            backdrop-filter: blur(20px); max-width: 800px; margin-left: auto; margin-right: auto;
        }
        .nav-tab {
            padding: 12px 24px; border: none; background: transparent;
            color: var(--text-secondary); font-family: 'Inter', sans-serif;
            font-size: 0.9rem; font-weight: 500; cursor: pointer;
            border-radius: var(--radius-lg); transition: var(--transition); white-space: nowrap;
        }
        .nav-tab:hover { color: var(--text-primary); background: var(--glass-highlight); }
        .nav-tab.active { background: var(--gradient-primary); color: white; font-weight: 600; box-shadow: var(--shadow-glow-purple); }

        .tab-content { display: none; animation: fadeIn 0.5s ease; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* ── Stats ────────────────────────────────────────────────── */
        .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 28px; }
        .stat-card {
            background: var(--bg-card); border: 1px solid var(--glass-border);
            border-radius: var(--radius-lg); padding: 22px; backdrop-filter: blur(20px);
            transition: var(--transition); position: relative; overflow: hidden;
        }
        .stat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; border-radius: var(--radius-lg) var(--radius-lg) 0 0; }
        .stat-card:nth-child(1)::before { background: var(--gradient-primary); }
        .stat-card:nth-child(2)::before { background: var(--gradient-pricing); }
        .stat-card:nth-child(3)::before { background: var(--gradient-customer); }
        .stat-card:nth-child(4)::before { background: var(--gradient-sales); }
        .stat-card:nth-child(5)::before { background: var(--gradient-inventory); }
        .stat-card:nth-child(6)::before { background: var(--gradient-supplier); }
        .stat-card:hover { transform: translateY(-4px); border-color: var(--glass-highlight); box-shadow: var(--shadow-lg); }
        .stat-card .stat-icon { font-size: 1.6rem; margin-bottom: 8px; }
        .stat-card .stat-value {
            font-size: 1.8rem; font-weight: 800; margin-bottom: 3px;
            background: var(--gradient-primary); -webkit-background-clip: text;
            -webkit-text-fill-color: transparent; background-clip: text;
        }
        .stat-card .stat-label { font-size: 0.8rem; color: var(--text-secondary); font-weight: 500; text-transform: uppercase; letter-spacing: 1px; }

        /* ── Glass Card ──────────────────────────────────────────── */
        .glass-card {
            background: var(--bg-card); border: 1px solid var(--glass-border);
            border-radius: var(--radius-lg); padding: 28px; backdrop-filter: blur(20px);
            margin-bottom: 20px; transition: var(--transition);
        }
        .glass-card:hover { border-color: var(--glass-highlight); }
        .card-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .card-header .icon { width: 44px; height: 44px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; font-size: 1.3rem; }
        .card-header .icon.pricing { background: var(--gradient-pricing); }
        .card-header .icon.inventory { background: var(--gradient-inventory); }
        .card-header .icon.customer { background: var(--gradient-customer); }
        .card-header .icon.supplier { background: var(--gradient-supplier); }
        .card-header .icon.sales { background: var(--gradient-sales); }
        .card-header h2 { font-size: 1.2rem; font-weight: 700; }
        .card-header .badge { margin-left: auto; padding: 4px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
        .badge.alert { background: rgba(244,63,94,0.2); color: var(--accent-rose); border: 1px solid rgba(244,63,94,0.3); }
        .badge.ok { background: rgba(16,185,129,0.2); color: var(--accent-emerald); border: 1px solid rgba(16,185,129,0.3); }
        .badge.warning { background: rgba(245,158,11,0.2); color: var(--accent-amber); border: 1px solid rgba(245,158,11,0.3); }

        /* ── Recommendation Items ────────────────────────────────── */
        .rec-list { display: flex; flex-direction: column; gap: 10px; }
        .rec-item {
            display: flex; align-items: flex-start; gap: 12px; padding: 16px;
            background: var(--glass); border: 1px solid var(--glass-border);
            border-radius: var(--radius-md); transition: var(--transition); cursor: pointer;
        }
        .rec-item:hover { background: var(--glass-highlight); transform: translateX(4px); }
        .rec-item .rule-tag {
            padding: 3px 10px; border-radius: 6px;
            font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
            font-weight: 600; white-space: nowrap; flex-shrink: 0;
        }
        .rule-tag.pricing { background: rgba(245,158,11,0.2); color: var(--accent-amber); }
        .rule-tag.inventory { background: rgba(59,130,246,0.2); color: var(--accent-blue); }
        .rule-tag.customer { background: rgba(236,72,153,0.2); color: var(--accent-pink); }
        .rule-tag.supplier { background: rgba(16,185,129,0.2); color: var(--accent-emerald); }
        .rule-tag.sales { background: rgba(244,63,94,0.2); color: var(--accent-rose); }
        .rec-item .rec-text { font-size: 0.92rem; color: var(--text-primary); line-height: 1.5; }
        .rec-item .priority-bar { margin-left: auto; display: flex; gap: 2px; flex-shrink: 0; }
        .priority-bar .pip { width: 4px; height: 16px; border-radius: 2px; background: var(--glass-border); }
        .priority-bar .pip.filled { background: var(--accent-purple); }
        .priority-bar .pip.high { background: var(--accent-rose); }

        /* ── Evidence Panel ──────────────────────────────────────── */
        .evidence-panel { display: none; margin-top: 12px; padding: 16px; background: rgba(0,0,0,0.3); border-radius: var(--radius-md); border: 1px solid var(--glass-border); }
        .evidence-panel.show { display: block; animation: fadeIn 0.3s ease; }
        .evidence-panel h4 { font-size: 0.85rem; color: var(--accent-cyan); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }
        .evidence-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.85rem; }
        .evidence-item .fact-key { color: var(--text-secondary); font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }
        .evidence-item .fact-value { color: var(--accent-cyan); font-weight: 600; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }

        /* ── Tables ──────────────────────────────────────────────── */
        .data-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.88rem; }
        .data-table thead th {
            background: rgba(139, 92, 246, 0.15); color: var(--text-secondary);
            font-weight: 600; text-transform: uppercase; letter-spacing: 1px;
            font-size: 0.75rem; padding: 14px 16px; text-align: left;
            border-bottom: 1px solid var(--glass-border); position: sticky; top: 0;
        }
        .data-table thead th:first-child { border-radius: var(--radius-md) 0 0 0; }
        .data-table thead th:last-child { border-radius: 0 var(--radius-md) 0 0; }
        .data-table tbody tr { transition: var(--transition); }
        .data-table tbody tr:hover { background: var(--glass-highlight); }
        .data-table tbody td { padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.03); color: var(--text-primary); }
        .text-right { text-align: right; }

        /* ── Add-Record Forms ────────────────────────────────────── */
        .btn-add {
            padding: 8px 18px; background: var(--gradient-primary); border: none;
            border-radius: var(--radius-sm); color: white; font-family: 'Inter', sans-serif;
            font-weight: 600; font-size: 0.82rem; cursor: pointer; transition: var(--transition);
            white-space: nowrap; margin-left: auto;
        }
        .btn-add:hover { transform: translateY(-2px); box-shadow: var(--shadow-glow-purple); }
        .add-form {
            display: none; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 12px; margin-bottom: 18px; padding: 20px;
            background: rgba(0,0,0,0.25); border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
        }
        .add-form.show { display: grid; animation: fadeIn 0.25s ease; }
        .form-field { display: flex; flex-direction: column; gap: 5px; }
        .form-field label {
            font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1px;
            color: var(--text-secondary); font-weight: 700;
        }
        .form-field input, .form-field select {
            width: 100%; padding: 10px 12px; background: var(--glass);
            border: 1px solid var(--glass-border); border-radius: var(--radius-sm);
            color: var(--text-primary); font-family: 'Inter', sans-serif;
            font-size: 0.88rem; outline: none; transition: var(--transition);
        }
        .form-field input:focus, .form-field select:focus {
            border-color: var(--accent-purple); box-shadow: 0 0 16px rgba(139,92,246,0.18);
        }
        .form-field select option { background: var(--bg-secondary); color: var(--text-primary); }
        .form-actions { display: flex; gap: 10px; align-items: flex-end; }
        .form-message { font-size: 0.84rem; min-height: 20px; margin-top: 4px; grid-column: 1 / -1; }
        .form-message.success { color: var(--accent-emerald); }
        .form-message.error   { color: var(--accent-rose); }

        .change-positive { color: var(--accent-emerald); }
        .change-negative { color: var(--accent-rose); }
        .stock-ok { color: var(--accent-emerald); }
        .stock-low { color: var(--accent-rose); font-weight: 600; }
        .stock-high { color: var(--accent-amber); }
        .reliability-high { color: var(--accent-emerald); }
        .reliability-mid { color: var(--accent-amber); }
        .reliability-low { color: var(--accent-rose); font-weight: 600; }
        .segment-badge { padding: 3px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }
        .segment-vip { background: rgba(245,158,11,0.2); color: var(--accent-amber); }
        .segment-loyal { background: rgba(139,92,246,0.2); color: var(--accent-purple); }
        .segment-regular { background: rgba(59,130,246,0.2); color: var(--accent-blue); }
        .segment-at-risk { background: rgba(244,63,94,0.2); color: var(--accent-rose); }
        .segment-inactive { background: rgba(107,107,153,0.3); color: var(--text-muted); }
        .segment-unclassified { background: rgba(107,107,153,0.15); color: var(--text-muted); }
        .btn-del {
            padding: 3px 8px; background: rgba(244,63,94,0.15); border: 1px solid rgba(244,63,94,0.3);
            border-radius: 6px; color: var(--accent-rose); font-size: 0.8rem; cursor: pointer;
            transition: var(--transition);
        }
        .btn-del:hover { background: rgba(244,63,94,0.35); }

        /* ── Backward Chaining ───────────────────────────────────── */
        .query-section { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
        .query-input {
            flex: 1; min-width: 300px; padding: 14px 20px;
            background: var(--glass); border: 1px solid var(--glass-border);
            border-radius: var(--radius-lg); color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace; font-size: 0.9rem;
            outline: none; transition: var(--transition);
        }
        .query-input:focus { border-color: var(--accent-purple); box-shadow: 0 0 20px rgba(139,92,246,0.2); }
        .query-input::placeholder { color: var(--text-muted); }
        .btn-primary {
            padding: 14px 28px; background: var(--gradient-primary); border: none;
            border-radius: var(--radius-lg); color: white; font-family: 'Inter', sans-serif;
            font-weight: 600; font-size: 0.9rem; cursor: pointer; transition: var(--transition); white-space: nowrap;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: var(--shadow-glow-purple); }
        .btn-primary:active { transform: translateY(0); }
        .goal-presets { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
        .preset-btn {
            padding: 8px 16px; background: var(--glass); border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm); color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
            cursor: pointer; transition: var(--transition);
        }
        .preset-btn:hover { background: var(--glass-highlight); color: var(--text-primary); border-color: var(--accent-purple); }

        /* ── Rules Grid ──────────────────────────────────────────── */
        .rules-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 16px; }
        .rule-card { background: var(--glass); border: 1px solid var(--glass-border); border-radius: var(--radius-md); padding: 20px; transition: var(--transition); }
        .rule-card:hover { background: var(--glass-highlight); transform: translateY(-2px); }
        .rule-card .rule-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
        .rule-card .rule-id { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.85rem; }
        .rule-card .rule-desc { font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 10px; line-height: 1.4; }
        .rule-card .rule-action { font-size: 0.85rem; color: var(--accent-cyan); padding: 8px 12px; background: rgba(6,182,212,0.1); border-radius: var(--radius-sm); border-left: 3px solid var(--accent-cyan); }

        .result-box { padding: 24px; border-radius: var(--radius-lg); margin-top: 20px; }
        .result-box.success { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); }
        .result-box.failure { background: rgba(244,63,94,0.1); border: 1px solid rgba(244,63,94,0.3); }
        .result-box h3 { font-size: 1.1rem; margin-bottom: 16px; }
        .result-box.success h3 { color: var(--accent-emerald); }
        .result-box.failure h3 { color: var(--accent-rose); }

        .domain-filters { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .domain-btn {
            padding: 8px 18px; border: 1px solid var(--glass-border); background: transparent;
            border-radius: 20px; color: var(--text-secondary); font-family: 'Inter', sans-serif;
            font-size: 0.83rem; font-weight: 500; cursor: pointer; transition: var(--transition);
        }
        .domain-btn:hover, .domain-btn.active { border-color: var(--accent-purple); color: var(--text-primary); background: rgba(139,92,246,0.15); }

        .spinner { display: inline-block; width: 20px; height: 20px; border: 2px solid var(--glass-border); border-top: 2px solid var(--accent-purple); border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 8px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-overlay { text-align: center; padding: 60px; color: var(--text-secondary); }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-primary); }
        ::-webkit-scrollbar-thumb { background: var(--glass-highlight); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-purple); }

        @media (max-width: 768px) {
            .header .logo { font-size: 2rem; }
            .stats-row { grid-template-columns: repeat(2, 1fr); }
            .rules-grid { grid-template-columns: 1fr; }
            .nav-tab { padding: 10px 16px; font-size: 0.82rem; }
            .app-container { padding: 12px; }
            .business-card { min-width: 200px; }
        }
    </style>
</head>
<body>
    <div class="bg-animation">
        <div class="orb"></div><div class="orb"></div><div class="orb"></div><div class="orb"></div>
    </div>

    <div class="app-container">
        <header class="header">
            <div class="logo">NexusTrade</div>
            <div class="subtitle">E-Commerce Decision Intelligence System</div>
        </header>

        <!-- Business Selector -->
        <div class="business-selector" id="businessSelector"></div>
        <div class="current-business" id="currentBusiness"></div>

        <!-- Navigation -->
        <nav class="nav-tabs" id="mainNav">
            <button class="nav-tab active" onclick="switchTab('dashboard', this)">🏠 Dashboard</button>
            <button class="nav-tab" onclick="switchTab('erp', this)">📊 ERP Data</button>
            <button class="nav-tab" onclick="switchTab('rules', this)">📋 Rules</button>
            <button class="nav-tab" onclick="switchTab('graph', this)">🕸️ Graph</button>
            <button class="nav-tab" onclick="switchTab('query', this)">🎯 Goal Query</button>
        </nav>

        <!-- ══════ DASHBOARD TAB ══════ -->
        <div id="tab-dashboard" class="tab-content active">
            <div class="stats-row" id="statsRow">
                <div class="stat-card"><div class="stat-icon">📋</div><div class="stat-value" id="statRules">25</div><div class="stat-label">Total Rules</div></div>
                <div class="stat-card"><div class="stat-icon">⚡</div><div class="stat-value" id="statFired">—</div><div class="stat-label">Recommendations</div></div>
                <div class="stat-card"><div class="stat-icon">🔍</div><div class="stat-value" id="statUnique">—</div><div class="stat-label">Unique Rules Fired</div></div>
                <div class="stat-card"><div class="stat-icon">📦</div><div class="stat-value" id="statProducts">5</div><div class="stat-label">Products</div></div>
                <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-value" id="statCustomers">8</div><div class="stat-label">Customers</div></div>
                <div class="stat-card"><div class="stat-icon">🏭</div><div class="stat-value" id="statSuppliers">5</div><div class="stat-label">Suppliers</div></div>
            </div>
            <div id="diagnosisResults"><div class="loading-overlay"><div class="spinner"></div>Running forward chaining diagnosis...</div></div>
        </div>

        <!-- ══════ ERP DATA TAB ══════ -->
        <div id="tab-erp" class="tab-content">
            <div id="erpData"><div class="loading-overlay"><div class="spinner"></div>Loading ERP data...</div></div>
        </div>

        <!-- ══════ RULES TAB ══════ -->
        <div id="tab-rules" class="tab-content">
            <div class="domain-filters" id="domainFilters">
                <button class="domain-btn active" onclick="filterRules('all', this)">All Rules</button>
                <button class="domain-btn" onclick="filterRules('pricing', this)">💰 Pricing</button>
                <button class="domain-btn" onclick="filterRules('inventory', this)">📦 Inventory</button>
                <button class="domain-btn" onclick="filterRules('customer', this)">👥 Customer</button>
                <button class="domain-btn" onclick="filterRules('supplier', this)">🏭 Supplier</button>
                <button class="domain-btn" onclick="filterRules('sales', this)">📊 Sales</button>
            </div>
            <div class="rules-grid" id="rulesGrid"><div class="loading-overlay"><div class="spinner"></div>Loading rules...</div></div>
        </div>

        <!-- ══════ GRAPH TAB ══════ -->
        <div id="tab-graph" class="tab-content">
            <div id="graphContainer" style="width: 100%; height: 600px; background: var(--bg-card); border: 1px solid var(--glass-border); border-radius: var(--radius-lg);"></div>
        </div>

        <!-- ══════ GOAL QUERY TAB ══════ -->
        <div id="tab-query" class="tab-content">
            <div class="glass-card">
                <div class="card-header">
                    <div class="icon" style="background: var(--gradient-primary);">🎯</div>
                    <h2>Backward Chaining — Goal-Driven Query</h2>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 0.9rem;">
                    Enter a goal to investigate. The engine works backward from the conclusion to verify supporting facts.
                </p>
                <div class="goal-presets" id="goalPresets"></div>
                <div class="query-section">
                    <input type="text" class="query-input" id="goalInput" placeholder="e.g. recommendation_P002_standard_reorder" />
                    <button class="btn-primary" onclick="runBackward()" id="queryBtn">Run Query</button>
                </div>
                <div id="queryResult"></div>
            </div>
        </div>
    </div>

    <script>
        // ── State ───────────────────────────────────────────────────
        let diagData = null, erpLoaded = false, rulesLoaded = false, allRules = [];
        let currentBusiness = '';

        // ── Tab Management ──────────────────────────────────────────
        function switchTab(tabName, btn) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            btn.classList.add('active');
            if (tabName === 'erp' && !erpLoaded) loadErpData();
            if (tabName === 'rules' && !rulesLoaded) loadRules();
            if (tabName === 'graph' && !graphLoaded) loadGraph();
        }

        // ── Business Selector ───────────────────────────────────────
        let graphLoaded = false;

        async function loadGraph() {
            try {
                const resp = await fetch('/api/graph');
                const data = await resp.json();
                renderCytoscape(data);
                graphLoaded = true;
            } catch (e) {
                console.error('Graph load error', e);
            }
        }

        function renderCytoscape(data) {
            const cy = cytoscape({
                container: document.getElementById('graphContainer'),
                elements: {
                    nodes: data.nodes,
                    edges: data.edges.map(e => ({ data: { source: e.data.source, target: e.data.target, label: e.data.type } }))
                },
                style: [
                    {
                        selector: 'node',
                        style: {
                            'background-color': function (ele) {
                                const g = ele.data('group');
                                if (g === 'domain') return '#8b5cf6';
                                if (g === 'rule') return '#3b82f6';
                                return '#06b6d4'; // condition
                            },
                            'label': 'data(label)',
                            'color': '#fff',
                            'font-size': '12px',
                            'text-valign': 'center',
                            'text-halign': 'center',
                            'width': 'label',
                            'height': 'label',
                            'padding': '8px',
                            'overlay-padding': '6px',
                            'z-index': 10
                        }
                    },
                    {
                        selector: 'edge',
                        style: {
                            'width': 2,
                            'line-color': '#aaa',
                            'target-arrow-color': '#aaa',
                            'target-arrow-shape': 'triangle',
                            'curve-style': 'bezier',
                            'label': 'data(label)',
                            'font-size': '10px',
                            'text-rotation': 'autorotate',
                            'text-margin-x': 0,
                            'text-margin-y': -10,
                            'color': '#ddd'
                        }
                    }
                ],
                layout: {
                    name: 'cose',
                    idealEdgeLength: 120,
                    nodeOverlap: 20,
                    refresh: 20,
                    animate: true,
                    animationDuration: 500,
                    fit: true,
                    padding: 30,
                    randomize: false
                }
            });
        }

        async function loadBusinesses() {
            const resp = await fetch('/api/businesses');
            const data = await resp.json();
            currentBusiness = data.current;
            let html = '';
            for (const [key, biz] of Object.entries(data.businesses)) {
                const activeCls = key === data.current ? 'active' : '';
                html += `<div class="business-card ${activeCls}" onclick="switchBusiness('${key}')" id="biz-${key}">
                    <div class="biz-icon">${biz.icon}</div>
                    <div class="biz-name">${biz.name}</div>
                    <div class="biz-desc">${biz.description}</div>
                </div>`;
            }
            document.getElementById('businessSelector').innerHTML = html;
            updateCurrentBusiness(data.businesses[data.current]);
        }

        function updateCurrentBusiness(biz) {
            document.getElementById('currentBusiness').innerHTML =
                `Currently analyzing: <strong>${biz.icon} ${biz.name}</strong> — ${biz.description}`;
        }

        async function switchBusiness(key) {
            if (key === currentBusiness) return;
            document.querySelectorAll('.business-card').forEach(c => c.classList.remove('active'));
            document.getElementById('biz-' + key).classList.add('active');

            // Show loading
            document.getElementById('diagnosisResults').innerHTML =
                '<div class="loading-overlay"><div class="spinner"></div>Switching business & re-running diagnosis...</div>';

            const resp = await fetch('/api/switch_business', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({business_key: key})
            });
            const data = await resp.json();
            if (data.success) {
                currentBusiness = key;
                // Reload everything
                erpLoaded = false;
                rulesLoaded = false;
                await loadDiagnosis();
                // Update business info
                const bizResp = await fetch('/api/businesses');
                const bizData = await bizResp.json();
                updateCurrentBusiness(bizData.businesses[key]);
                // Re-render goal presets
                renderGoalPresets();
                // If ERP tab was already loaded, force reload
                if (document.getElementById('tab-erp').classList.contains('active')) {
                    loadErpData();
                }
            }
        }

        // ── Dashboard: Forward Chaining ─────────────────────────────
        async function loadDiagnosis() {
            try {
                const resp = await fetch('/api/diagnosis');
                diagData = await resp.json();
                renderDiagnosis(diagData);
            } catch (e) {
                document.getElementById('diagnosisResults').innerHTML =
                    '<div class="glass-card" style="color:var(--accent-rose)">Error loading diagnosis.</div>';
            }
        }

        function renderDiagnosis(data) {
            document.getElementById('statRules').textContent = data.total_rules;
            document.getElementById('statFired').textContent = data.total_fired;
            document.getElementById('statUnique').textContent = data.unique_rules_fired + ' / 25';
            if (data.db_counts) {
                document.getElementById('statProducts').textContent = data.db_counts.products;
                document.getElementById('statCustomers').textContent = data.db_counts.customers;
                document.getElementById('statSuppliers').textContent = data.db_counts.suppliers;
            }

            const domainConfig = {
                pricing:   { label: 'Pricing & Discounts',     icon: '💰', cls: 'pricing' },
                inventory: { label: 'Inventory Reorder',       icon: '📦', cls: 'inventory' },
                customer:  { label: 'Customer Segmentation',   icon: '👥', cls: 'customer' },
                supplier:  { label: 'Supplier & Procurement',  icon: '🏭', cls: 'supplier' },
                sales:     { label: 'Sales Performance',       icon: '📊', cls: 'sales' },
            };

            let html = '';
            for (const [domain, cfg] of Object.entries(domainConfig)) {
                const items = (data.by_domain[domain] || []).filter(t => t.fired);
                const count = items.length;
                const badgeCls = count === 0 ? 'ok' : count >= 3 ? 'alert' : 'warning';
                const badgeText = count === 0 ? '✓ Clear' : count + ' Issue' + (count > 1 ? 's' : '');

                html += `<div class="glass-card">
                    <div class="card-header">
                        <div class="icon ${cfg.cls}">${cfg.icon}</div>
                        <h2>${cfg.label}</h2>
                        <span class="badge ${badgeCls}">${badgeText}</span>
                    </div><div class="rec-list">`;

                if (items.length === 0) {
                    html += `<div style="color: var(--accent-emerald); padding: 8px; font-size: 0.9rem;">✅ No issues detected in this domain.</div>`;
                } else {
                    for (const item of items) {
                        const pips = Array.from({length: 10}, (_, i) => {
                            const filled = i < item.priority;
                            const cls = filled ? (item.priority >= 8 ? 'pip filled high' : 'pip filled') : 'pip';
                            return `<div class="${cls}"></div>`;
                        }).join('');

                        const evidenceId = `ev-${item.rule_id}-${Math.random().toString(36).substr(2,6)}`;
                        let evidenceHtml = '';
                        if (item.evidence && Object.keys(item.evidence).length) {
                            evidenceHtml = `<div class="evidence-panel" id="${evidenceId}">
                                <h4>📊 Supporting Evidence</h4>
                                ${Object.entries(item.evidence).map(([k,v]) =>
                                    `<div class="evidence-item"><span class="fact-key">${k}</span><span class="fact-value">${v}</span></div>`
                                ).join('')}
                                <br><h4>📋 Conditions Evaluated</h4>
                                ${item.conditions.map(c =>
                                    `<div class="evidence-item"><span class="fact-key">${c.description}</span><span class="fact-value">${c.actual_value} ${c.operator} ${c.threshold}</span></div>`
                                ).join('')}
                            </div>`;
                        }

                        html += `<div class="rec-item" onclick="toggleEvidence('${evidenceId}')">
                            <span class="rule-tag ${cfg.cls}">${item.rule_id}</span>
                            <div><div class="rec-text">${item.action}</div>${evidenceHtml}</div>
                            <div class="priority-bar">${pips}</div>
                        </div>`;
                    }
                }
                html += `</div></div>`;
            }
            document.getElementById('diagnosisResults').innerHTML = html;
        }

        function toggleEvidence(id) {
            const el = document.getElementById(id);
            if (el) el.classList.toggle('show');
        }

        // ── ERP Data ────────────────────────────────────────────────
        async function loadErpData() {
            try {
                const resp = await fetch('/api/erp');
                const data = await resp.json();
                erpLoaded = true;
                renderErpData(data);
            } catch (e) {
                document.getElementById('erpData').innerHTML = '<div class="glass-card" style="color:var(--accent-rose)">Error loading ERP data.</div>';
            }
        }

        function renderErpData(data) {
            let html = '';
            html += `<div class="glass-card"><div class="card-header"><div class="icon inventory">📦</div><h2>Products &amp; Inventory</h2>
                <button class="btn-add" onclick="toggleForm('form-product')">＋ Add Product</button></div>
                <div id="form-product" class="add-form">
                    <div class="form-field"><label>Product ID</label><input id="p_product_id" placeholder="e.g. P006"></div>
                    <div class="form-field"><label>Name</label><input id="p_name" placeholder="Product name"></div>
                    <div class="form-field"><label>Stock</label><input id="p_stock" type="number" value="100"></div>
                    <div class="form-field"><label>Reorder Level</label><input id="p_reorder_level" type="number" value="50"></div>
                    <div class="form-field"><label>Turnover</label><input id="p_turnover" type="number" step="0.01" value="1.0"></div>
                    <div class="form-field"><label>Price ($)</label><input id="p_price" type="number" step="0.01" value="49.99"></div>
                    <div class="form-field"><label>Margin (%)</label><input id="p_margin" type="number" step="0.1" value="50.0"></div>
                    <div class="form-field"><label>Revenue ($)</label><input id="p_revenue" type="number" step="0.01" value="0"></div>
                    <div class="form-field"><label>Revenue Δ (%)</label><input id="p_revenue_delta" type="number" step="0.1" value="0"></div>
                    <div class="form-field"><label>Returns (%)</label><input id="p_returns" type="number" step="0.1" value="0"></div>
                    <div class="form-field"><label>Cart Aband. (%)</label><input id="p_cart_abandonment" type="number" step="0.1" value="0"></div>
                    <div class="form-actions"><button class="btn-primary" onclick="submitProduct()">Save Product</button></div>
                    <div id="msg-product" class="form-message"></div>
                </div>
                <div style="overflow-x:auto"><table class="data-table"><thead><tr>
                <th>ID</th><th>Product</th><th>Stock</th><th>Reorder</th><th>Turnover</th><th>Price</th><th>Margin</th><th>Revenue</th><th>Rev Δ</th><th>Returns</th><th>Cart Abd.</th>
                </tr></thead><tbody>`;
            for (const p of data.products) {
                const stockCls = p.stock < p.reorder_point ? 'stock-low' : p.stock > p.reorder_point * 3 ? 'stock-high' : 'stock-ok';
                const revCls = p.rev_change !== null ? (p.rev_change >= 0 ? 'change-positive' : 'change-negative') : '';
                const revText = p.rev_change !== null ? (p.rev_change >= 0 ? '+' : '') + p.rev_change + '%' : '—';
                html += `<tr><td><strong>${p.id}</strong></td><td>${p.name}</td><td class="${stockCls} text-right">${p.stock}</td>
                    <td class="text-right">${p.reorder_point}</td><td class="text-right">${p.turnover}</td>
                    <td class="text-right">$${p.price.toFixed(2)}</td><td class="text-right">${p.margin}%</td>
                    <td class="text-right">$${p.revenue.toLocaleString()}</td><td class="text-right ${revCls}">${revText}</td>
                    <td class="text-right">${p.return_rate}%</td><td class="text-right">${p.cart_abandon}%</td></tr>`;
            }
            html += `</tbody></table></div></div>`;

            html += `<div class="glass-card"><div class="card-header"><div class="icon customer">👥</div><h2>Customers (RFM)</h2>
                <button class="btn-add" onclick="toggleForm('form-customer')">＋ Add Customer</button></div>
                <div id="form-customer" class="add-form">
                    <div class="form-field"><label>Customer ID</label><input id="c_customer_id" placeholder="e.g. C009"></div>
                    <div class="form-field"><label>Name</label><input id="c_name" placeholder="Full name"></div>
                    <div class="form-field"><label>Recency (days)</label><input id="c_recency" type="number" value="10"></div>
                    <div class="form-field"><label>Frequency</label><input id="c_frequency" type="number" value="5"></div>
                    <div class="form-field"><label>Monetary ($)</label><input id="c_monetary" type="number" step="0.01" value="500"></div>
                    <div class="form-field"><label>Segment</label>
                        <select id="c_segment">
                            <option value="VIP">VIP</option><option value="Loyal">Loyal</option>
                            <option value="Regular">Regular</option><option value="At Risk">At Risk</option>
                            <option value="Inactive">Inactive</option><option value="Unclassified" selected>Unclassified</option>
                        </select>
                    </div>
                    <div class="form-actions"><button class="btn-primary" onclick="submitCustomer()">Save Customer</button></div>
                    <div id="msg-customer" class="form-message"></div>
                </div>
                <div style="overflow-x:auto"><table class="data-table"><thead><tr>
                <th>ID</th><th>Name</th><th>Recency (days)</th><th>Frequency</th><th>Monetary</th><th>Segment</th><th></th>
                </tr></thead><tbody>`;
            for (const c of data.customers) {
                const seg = (c.segment || 'Unclassified');
                const segKey = seg.toLowerCase().replace(' ','-');
                html += `<tr><td><strong>${c.id}</strong></td><td>${c.name}</td><td class="text-right">${c.recency}</td>
                    <td class="text-right">${c.frequency}</td><td class="text-right">$${c.monetary.toLocaleString()}</td>
                    <td><span class="segment-badge segment-${segKey}">${seg.toUpperCase()}</span></td>
                    <td><button class="btn-del" onclick="deleteRecord('customers','${c.id}')">✕</button></td></tr>`;
            }
            html += `</tbody></table></div></div>`;

            html += `<div class="glass-card"><div class="card-header"><div class="icon supplier">🏭</div><h2>Suppliers</h2>
                <button class="btn-add" onclick="toggleForm('form-supplier')">＋ Add Supplier</button></div>
                <div id="form-supplier" class="add-form">
                    <div class="form-field"><label>Supplier ID</label><input id="s_supplier_id" placeholder="e.g. S006"></div>
                    <div class="form-field"><label>Name</label><input id="s_name" placeholder="Company name"></div>
                    <div class="form-field"><label>Product ID</label><input id="s_product_id" placeholder="e.g. P001"></div>
                    <div class="form-field"><label>Lead Time (days)</label><input id="s_lead_time" type="number" value="7"></div>
                    <div class="form-field"><label>Reliability (%)</label><input id="s_reliability" type="number" step="0.1" value="90"></div>
                    <div class="form-field"><label>Price / Unit ($)</label><input id="s_price_per_unit" type="number" step="0.01" value="25"></div>
                    <div class="form-field"><label>Price Δ (%)</label><input id="s_price_delta" type="number" step="0.1" value="0"></div>
                    <div class="form-field"><label>Bulk Available</label>
                        <select id="s_bulk_available"><option value="true">Yes</option><option value="false" selected>No</option></select>
                    </div>
                    <div class="form-field"><label>Single Source</label>
                        <select id="s_single_source"><option value="true">Yes</option><option value="false" selected>No</option></select>
                    </div>
                    <div class="form-actions"><button class="btn-primary" onclick="submitSupplier()">Save Supplier</button></div>
                    <div id="msg-supplier" class="form-message"></div>
                </div>
                <div style="overflow-x:auto"><table class="data-table"><thead><tr>
                <th>ID</th><th>Name</th><th>Product</th><th>Lead Time</th><th>Reliability</th><th>Price/Unit</th><th>Price Δ</th><th>Bulk</th><th>Single Source</th><th></th>
                </tr></thead><tbody>`;
            for (const s of data.suppliers) {
                const relCls = s.reliability >= 80 ? 'reliability-high' : s.reliability >= 65 ? 'reliability-mid' : 'reliability-low';
                const priceCls = s.price_change > 5 ? 'change-negative' : 'change-positive';
                html += `<tr><td><strong>${s.id}</strong></td><td>${s.name}</td><td>${s.product_id}</td>
                    <td class="text-right">${s.lead_time}d</td><td class="text-right ${relCls}">${s.reliability}%</td>
                    <td class="text-right">$${s.price.toFixed(2)}</td><td class="text-right ${priceCls}">${s.price_change > 0 ? '+' : ''}${s.price_change}%</td>
                    <td>${s.bulk ? '✅' : '❌'}</td><td>${s.single_source ? '⚠️ Yes' : 'No'}</td>
                    <td><button class="btn-del" onclick="deleteRecord('suppliers','${s.id}')">✕</button></td></tr>`;
            }
            html += `</tbody></table></div></div>`;
            document.getElementById('erpData').innerHTML = html;
        }

        // ── Add-Form Helpers ────────────────────────────────────────
        function toggleForm(id) {
            document.getElementById(id).classList.toggle('show');
        }

        function showMsg(id, text, ok) {
            const el = document.getElementById(id);
            el.textContent = text;
            el.className = 'form-message ' + (ok ? 'success' : 'error');
        }

        async function postJSON(url, body, msgId) {
            showMsg(msgId, 'Saving…', true);
            try {
                const r = await fetch(url, {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify(body)
                });
                const j = await r.json();
                if (j.success) { showMsg(msgId, '✅ Saved successfully!', true); return true; }
                else { showMsg(msgId, '❌ ' + (j.error || 'Save failed.'), false); return false; }
            } catch(e) { showMsg(msgId, '❌ Network error.', false); return false; }
        }

        async function deleteRecord(type, id) {
            if (!confirm(`Delete ${type.slice(0,-1)} '${id}'? This cannot be undone.`)) return;
            try {
                const r = await fetch(`/api/${type}/${id}`, {method: 'DELETE'});
                const j = await r.json();
                if (j.success) { erpLoaded = false; loadErpData(); loadDiagnosis(); }
                else alert('❌ ' + (j.error || 'Delete failed.'));
            } catch(e) { alert('❌ Network error.'); }
        }

        async function submitProduct() {
            const ok = await postJSON('/api/products', {
                product_id: document.getElementById('p_product_id').value,
                name:       document.getElementById('p_name').value,
                stock:      document.getElementById('p_stock').value,
                reorder_level: document.getElementById('p_reorder_level').value,
                turnover:   document.getElementById('p_turnover').value,
                price:      document.getElementById('p_price').value,
                margin:     document.getElementById('p_margin').value,
                revenue:    document.getElementById('p_revenue').value,
                revenue_delta: document.getElementById('p_revenue_delta').value,
                returns:    document.getElementById('p_returns').value,
                cart_abandonment: document.getElementById('p_cart_abandonment').value,
            }, 'msg-product');
            if (ok) setTimeout(() => {
                ['p_product_id','p_name','p_stock','p_reorder_level','p_turnover','p_price','p_margin','p_revenue','p_revenue_delta','p_returns','p_cart_abandonment'].forEach(id => {
                    const el = document.getElementById(id); if(el) el.value = el.defaultValue;
                });
                erpLoaded = false; loadErpData(); loadDiagnosis();
            }, 800);
        }

        async function submitCustomer() {
            const ok = await postJSON('/api/customers', {
                customer_id: document.getElementById('c_customer_id').value,
                name:       document.getElementById('c_name').value,
                recency:    document.getElementById('c_recency').value,
                frequency:  document.getElementById('c_frequency').value,
                monetary:   document.getElementById('c_monetary').value,
                segment:    document.getElementById('c_segment').value,
            }, 'msg-customer');
            if (ok) setTimeout(() => {
                ['c_customer_id','c_name','c_recency','c_frequency','c_monetary'].forEach(id => {
                    const el = document.getElementById(id); if(el) el.value = el.defaultValue;
                });
                document.getElementById('c_segment').value = 'Unclassified';
                erpLoaded = false; loadErpData(); loadDiagnosis();
            }, 800);
        }

        async function submitSupplier() {
            const ok = await postJSON('/api/suppliers', {
                supplier_id:   document.getElementById('s_supplier_id').value,
                name:          document.getElementById('s_name').value,
                product_id:    document.getElementById('s_product_id').value,
                lead_time:     document.getElementById('s_lead_time').value,
                reliability:   document.getElementById('s_reliability').value,
                price_per_unit:document.getElementById('s_price_per_unit').value,
                price_delta:   document.getElementById('s_price_delta').value,
                bulk_available:document.getElementById('s_bulk_available').value,
                single_source: document.getElementById('s_single_source').value,
            }, 'msg-supplier');
            if (ok) setTimeout(() => {
                ['s_supplier_id','s_name','s_product_id','s_lead_time','s_reliability','s_price_per_unit','s_price_delta'].forEach(id => {
                    const el = document.getElementById(id); if(el) el.value = el.defaultValue;
                });
                erpLoaded = false; loadErpData(); loadDiagnosis();
            }, 800);
        }

        // ── Rules ───────────────────────────────────────────────────
        async function loadRules() {
            try {
                const resp = await fetch('/api/rules');
                allRules = await resp.json();
                rulesLoaded = true;
                renderRules(allRules);
            } catch (e) {
                document.getElementById('rulesGrid').innerHTML = '<div class="glass-card" style="color:var(--accent-rose)">Error loading rules.</div>';
            }
        }

        function renderRules(rules) {
            const domainCls = { pricing: 'pricing', inventory: 'inventory', customer: 'customer', supplier: 'supplier', sales: 'sales' };
            let html = '';
            for (const r of rules) {
                html += `<div class="rule-card" data-domain="${r.domain}">
                    <div class="rule-header">
                        <span class="rule-tag ${domainCls[r.domain]}">${r.id}</span>
                        <span class="rule-id" style="color: var(--text-secondary)">${r.domain.toUpperCase()}</span>
                        <span style="margin-left:auto; color:var(--text-muted); font-size:0.8rem;">Priority: ${r.priority}/10</span>
                    </div>
                    <div class="rule-desc">${r.description}</div>
                    <div class="rule-action">→ ${r.action}</div>
                </div>`;
            }
            document.getElementById('rulesGrid').innerHTML = html;
        }

        function filterRules(domain, btn) {
            document.querySelectorAll('.domain-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderRules(domain === 'all' ? allRules : allRules.filter(r => r.domain === domain));
        }

        // ── Goal Presets (dynamic based on current business) ────────
        function renderGoalPresets() {
            const presets = [
                { label: 'Reorder P002?',      goal: 'recommendation_P002_urgent_reorder' },
                { label: 'Discount P003?',      goal: 'recommendation_P003_clearance_discount' },
                { label: 'Segment C001?',       goal: 'customer_C001_segment' },
                { label: 'P001 declining?',     goal: 'diagnosis_P001_declining_sales' },
                { label: 'Price ↑ P001?',       goal: 'recommendation_P001_peak_price_increase' },
                { label: 'Dual-Source P004?',   goal: 'recommendation_P004_dual_source' },
                { label: 'Upsell C006?',        goal: 'recommendation_C006_premium_upsell' },
                { label: 'Blacklist S002?',     goal: 'recommendation_S002_blacklist' },
            ];
            let html = '';
            for (const p of presets) {
                html += `<button class="preset-btn" onclick="setGoal('${p.goal}')">${p.label}</button>`;
            }
            document.getElementById('goalPresets').innerHTML = html;
        }

        // ── Backward Chaining ───────────────────────────────────────
        function setGoal(goal) { document.getElementById('goalInput').value = goal; }

        async function runBackward() {
            const goal = document.getElementById('goalInput').value.trim();
            if (!goal) return;
            const btn = document.getElementById('queryBtn');
            btn.innerHTML = '<div class="spinner"></div> Running...';
            btn.disabled = true;
            try {
                const resp = await fetch('/api/backward', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({goal: goal})
                });
                const data = await resp.json();
                renderBackwardResult(data);
            } catch (e) {
                document.getElementById('queryResult').innerHTML = '<div class="result-box failure"><h3>Error running query</h3></div>';
            } finally {
                btn.innerHTML = 'Run Query'; btn.disabled = false;
            }
        }

        function renderBackwardResult(data) {
            const cls = data.success ? 'success' : 'failure';
            const icon = data.success ? '✅' : '❌';
            const title = data.success ? 'Goal Proved Successfully' : 'Goal Could Not Be Proved';
            let html = `<div class="result-box ${cls}"><h3>${icon} ${title}</h3>
                <p style="color:var(--text-secondary); margin-bottom:16px; font-family:'JetBrains Mono',monospace; font-size:0.85rem;">Goal: ${data.goal}</p>`;
            if (data.trace && data.trace.length > 0) {
                html += `<div class="rec-list">`;
                for (const t of data.trace) {
                    html += `<div class="rec-item" style="cursor:default">
                        <span class="rule-tag ${t.domain}">${t.rule_id}</span>
                        <div><div class="rec-text">${t.action}</div>
                            <div style="margin-top:8px; font-size:0.82rem; color:var(--text-muted);">${t.description}</div>
                            ${t.conditions.map(c =>
                                `<div class="evidence-item" style="margin-top:4px">
                                    <span class="fact-key">${c.description}</span>
                                    <span class="fact-value">${c.actual_value !== null ? c.actual_value + ' ' + c.operator + ' ' + c.threshold : 'Missing'}</span>
                                </div>`
                            ).join('')}
                        </div></div>`;
                }
                html += `</div>`;
            } else {
                html += `<p style="color:var(--text-muted)">No rules found that can conclude this goal.</p>`;
            }
            html += `</div>`;
            document.getElementById('queryResult').innerHTML = html;
        }

        // ── Init ────────────────────────────────────────────────────
        document.addEventListener('DOMContentLoaded', async () => {
            await loadBusinesses();
            await loadDiagnosis();
            renderGoalPresets();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && document.activeElement.id === 'goalInput') runBackward();
        });
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    print("\n  🚀 NexusTrade Web Dashboard starting...")
    print("  📍 Open http://localhost:5001 in your browser\n")
    app.run(debug=True, port=5001)
