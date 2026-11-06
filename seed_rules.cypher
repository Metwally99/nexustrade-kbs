// =============================================================================
//  NexusTrade — Knowledge Base Seed Data
// =============================================================================
//  Loads the 25 IF-THEN rules (5 domains × 5 rules) into the rule graph.
//
//  Prerequisite: the schema must already be applied — run `schema.cypher`
//  first so the uniqueness constraints exist before MERGE statements rely
//  on them.
//
//  Notes on property types:
//    - `threshold` is heterogeneous: number | string | boolean.
//      String thresholds prefixed with "DYNAMIC:" reference another fact key
//      that must be resolved at evaluation time.
//    - `action_value` is heterogeneous: boolean | string (e.g. "VIP").
//
//  Usage:
//    cypher-shell -u neo4j -p <password> -f seed_rules.cypher
//
//  Re-running:
//    The first statement clears all Rule/Condition/Domain nodes so the
//    file is idempotent — running it again gives a clean reload. Comment
//    that line out if you want to preserve existing rules.
// =============================================================================


// ── Reset existing rule data ─────────────────────────────────────────────────
MATCH (n) WHERE n:Rule OR n:Condition OR n:Domain DETACH DELETE n;


// ── Domains ──────────────────────────────────────────────────────────────────
MERGE (:Domain {name: "pricing",   display_name: "Pricing & Discounts"});
MERGE (:Domain {name: "inventory", display_name: "Inventory Reorder"});
MERGE (:Domain {name: "customer",  display_name: "Customer Segmentation"});
MERGE (:Domain {name: "supplier",  display_name: "Supplier & Procurement"});
MERGE (:Domain {name: "sales",     display_name: "Sales Performance Diagnosis"});


// =============================================================================
//  DOMAIN 1: Pricing & Discounts (R1–R5)
// =============================================================================

// ── R1 ───────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R1"})
SET r.description    = "IF stock > 150% of avg sales rate THEN recommend 20% clearance discount",
    r.action         = "Recommend 20% clearance discount for {pid} — overstock detected",
    r.action_key     = "recommendation_{pid}_clearance_discount",
    r.action_value   = true,
    r.priority       = 6,
    r.entity_type    = "product",
    r.entity_pattern = "product_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "pricing"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R1"})
CREATE (c:Condition {
  fact_pattern: "product_{pid}_stock_vs_avg_sales_pct",
  operator:    ">",
  threshold:   150,
  description: "Stock exceeds 150% of average sales rate"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// ── R2 ───────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R2"})
SET r.description    = "IF margin > 40% AND competitor price < our price THEN recommend price match",
    r.action         = "Recommend price match for {pid} — high margin allows competitive pricing",
    r.action_key     = "recommendation_{pid}_price_match",
    r.action_value   = true,
    r.priority       = 7,
    r.entity_type    = "product",
    r.entity_pattern = "product_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "pricing"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R2"})
CREATE (c1:Condition {
  fact_pattern: "product_{pid}_margin_pct",
  operator:    ">",
  threshold:   40,
  description: "Profit margin exceeds 40%"
})
CREATE (c2:Condition {
  fact_pattern: "product_{pid}_competitor_price",
  operator:    "<",
  threshold:   "DYNAMIC:product_{pid}_selling_price",
  description: "Competitor price is lower than our price"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R3 ───────────────────────────────────────────────────────────────────────
//  Fixed from "segment=VIP AND recency>30" (impossible — R11 sets VIP only
//  when recency<30) to direct monetary+recency conditions.
MERGE (r:Rule {rule_id: "R3"})
SET r.description    = "IF monetary > 500 AND last purchase > 30 days THEN trigger loyalty discount",
    r.action         = "Trigger loyalty discount for customer {cid} — high-value re-engagement",
    r.action_key     = "recommendation_{cid}_loyalty_discount",
    r.action_value   = true,
    r.priority       = 6,
    r.entity_type    = "customer",
    r.entity_pattern = "customer_(C\\d+)_"
WITH r
MATCH (d:Domain {name: "pricing"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R3"})
CREATE (c1:Condition {
  fact_pattern: "customer_{cid}_monetary",
  operator:    ">",
  threshold:   500,
  description: "Customer total spend exceeds $500"
})
CREATE (c2:Condition {
  fact_pattern: "customer_{cid}_recency",
  operator:    ">",
  threshold:   30,
  description: "Last purchase was more than 30 days ago"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R4 ───────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R4"})
SET r.description    = "IF return rate > 15% AND price > market avg THEN flag for price revision",
    r.action         = "Flag {pid} for price revision — high returns + above-market pricing",
    r.action_key     = "recommendation_{pid}_price_revision",
    r.action_value   = true,
    r.priority       = 8,
    r.entity_type    = "product",
    r.entity_pattern = "product_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "pricing"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R4"})
CREATE (c1:Condition {
  fact_pattern: "sales_{pid}_return_rate",
  operator:    ">",
  threshold:   0.15,
  description: "Return rate exceeds 15%"
})
CREATE (c2:Condition {
  fact_pattern: "product_{pid}_selling_price",
  operator:    ">",
  threshold:   "DYNAMIC:product_{pid}_market_avg_price",
  description: "Selling price is above market average"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R5 ───────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R5"})
SET r.description    = "IF seasonal demand = peak AND stock sufficient THEN recommend 10% price increase",
    r.action         = "Recommend 10% price increase for {pid} — peak season + adequate stock",
    r.action_key     = "recommendation_{pid}_peak_price_increase",
    r.action_value   = true,
    r.priority       = 7,
    r.entity_type    = "product",
    r.entity_pattern = "product_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "pricing"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R5"})
CREATE (c1:Condition {
  fact_pattern: "product_{pid}_seasonal_demand",
  operator:    "==",
  threshold:   "peak",
  description: "Seasonal demand is at peak"
})
CREATE (c2:Condition {
  fact_pattern: "product_{pid}_stock_sufficient",
  operator:    "==",
  threshold:   true,
  description: "Stock level is sufficient"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// =============================================================================
//  DOMAIN 2: Inventory Reorder (R6–R10)
// =============================================================================

// ── R6 ───────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R6"})
SET r.description    = "IF stock < reorder point AND lead time < 7 days THEN place standard reorder",
    r.action         = "Place standard reorder for {pid} via supplier {sid}",
    r.action_key     = "recommendation_{pid}_standard_reorder",
    r.action_value   = true,
    r.priority       = 9,
    r.entity_type    = "product",
    r.entity_pattern = "product_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "inventory"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R6"})
CREATE (c1:Condition {
  fact_pattern: "product_{pid}_stock",
  operator:    "<",
  threshold:   "DYNAMIC:product_{pid}_reorder_point",
  description: "Stock is below reorder point"
})
CREATE (c2:Condition {
  fact_pattern: "supplier_{sid}_lead_time",
  operator:    "<",
  threshold:   7,
  description: "Supplier lead time is under 7 days"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R7 ───────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R7"})
SET r.description    = "IF stock < reorder point AND lead time >= 7 days THEN place urgent reorder × 1.5",
    r.action         = "Place URGENT reorder (×1.5 qty) for {pid} via supplier {sid} — long lead time",
    r.action_key     = "recommendation_{pid}_urgent_reorder",
    r.action_value   = true,
    r.priority       = 10,
    r.entity_type    = "product",
    r.entity_pattern = "product_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "inventory"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R7"})
CREATE (c1:Condition {
  fact_pattern: "product_{pid}_stock",
  operator:    "<",
  threshold:   "DYNAMIC:product_{pid}_reorder_point",
  description: "Stock is below reorder point"
})
CREATE (c2:Condition {
  fact_pattern: "supplier_{sid}_lead_time",
  operator:    ">=",
  threshold:   7,
  description: "Supplier lead time is 7 days or more"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R8 ───────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R8"})
SET r.description    = "IF stock turnover < 0.3 THEN flag slow-moving, reduce next order 30%",
    r.action         = "Flag {pid} as slow-moving — reduce next order by 30%",
    r.action_key     = "recommendation_{pid}_slow_moving",
    r.action_value   = true,
    r.priority       = 5,
    r.entity_type    = "product",
    r.entity_pattern = "product_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "inventory"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R8"})
CREATE (c:Condition {
  fact_pattern: "product_{pid}_turnover_rate",
  operator:    "<",
  threshold:   0.3,
  description: "Stock turnover rate is below 0.3"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// ── R9 ───────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R9"})
SET r.description    = "IF stockouts > 2 last month THEN increase safety stock 20%",
    r.action         = "Increase safety stock for {pid} by 20% — frequent stockouts detected",
    r.action_key     = "recommendation_{pid}_increase_safety_stock",
    r.action_value   = true,
    r.priority       = 8,
    r.entity_type    = "product",
    r.entity_pattern = "product_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "inventory"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R9"})
CREATE (c:Condition {
  fact_pattern: "product_{pid}_stockouts_last_month",
  operator:    ">",
  threshold:   2,
  description: "More than 2 stockouts last month"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// ── R10 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R10"})
SET r.description    = "IF supplier reliability < 70% THEN recommend switching to backup",
    r.action         = "Recommend switching from supplier {sid} to backup — low reliability",
    r.action_key     = "recommendation_{sid}_switch_supplier",
    r.action_value   = true,
    r.priority       = 7,
    r.entity_type    = "supplier",
    r.entity_pattern = "supplier_(S\\d+)_"
WITH r
MATCH (d:Domain {name: "inventory"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R10"})
CREATE (c:Condition {
  fact_pattern: "supplier_{sid}_reliability",
  operator:    "<",
  threshold:   70,
  description: "Supplier reliability score is below 70%"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// =============================================================================
//  DOMAIN 3: Customer Segmentation (R11–R15)
// =============================================================================

// ── R11 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R11"})
SET r.description    = "IF recency < 30 AND frequency > 5 AND monetary > 500 THEN segment = VIP",
    r.action         = "Classify customer {cid} as VIP",
    r.action_key     = "customer_{cid}_segment",
    r.action_value   = "VIP",
    r.priority       = 8,
    r.entity_type    = "customer",
    r.entity_pattern = "customer_(C\\d+)_"
WITH r
MATCH (d:Domain {name: "customer"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R11"})
CREATE (c1:Condition {
  fact_pattern: "customer_{cid}_recency",
  operator:    "<",
  threshold:   30,
  description: "Last purchase within 30 days"
})
CREATE (c2:Condition {
  fact_pattern: "customer_{cid}_frequency",
  operator:    ">",
  threshold:   5,
  description: "Purchase frequency exceeds 5"
})
CREATE (c3:Condition {
  fact_pattern: "customer_{cid}_monetary",
  operator:    ">",
  threshold:   500,
  description: "Total spend exceeds $500"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2)
CREATE (r)-[:HAS_CONDITION {order: 3}]->(c3);


// ── R12 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R12"})
SET r.description    = "IF recency > 90 AND frequency > 3 THEN segment = at-risk, trigger win-back",
    r.action         = "Classify customer {cid} as AT-RISK — trigger win-back campaign",
    r.action_key     = "customer_{cid}_segment",
    r.action_value   = "at-risk",
    r.priority       = 7,
    r.entity_type    = "customer",
    r.entity_pattern = "customer_(C\\d+)_"
WITH r
MATCH (d:Domain {name: "customer"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R12"})
CREATE (c1:Condition {
  fact_pattern: "customer_{cid}_recency",
  operator:    ">",
  threshold:   90,
  description: "No purchase in over 90 days"
})
CREATE (c2:Condition {
  fact_pattern: "customer_{cid}_frequency",
  operator:    ">",
  threshold:   3,
  description: "Has made more than 3 purchases historically"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R13 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R13"})
SET r.description    = "IF recency > 180 THEN segment = churned, recommend reactivation offer",
    r.action         = "Classify customer {cid} as CHURNED — recommend reactivation offer",
    r.action_key     = "customer_{cid}_segment",
    r.action_value   = "churned",
    r.priority       = 6,
    r.entity_type    = "customer",
    r.entity_pattern = "customer_(C\\d+)_"
WITH r
MATCH (d:Domain {name: "customer"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R13"})
CREATE (c:Condition {
  fact_pattern: "customer_{cid}_recency",
  operator:    ">",
  threshold:   180,
  description: "No purchase in over 180 days"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// ── R14 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R14"})
SET r.description    = "IF frequency = 1 AND recency < 14 THEN segment = new customer, start onboarding",
    r.action         = "Classify customer {cid} as NEW CUSTOMER — initiate onboarding sequence",
    r.action_key     = "customer_{cid}_segment",
    r.action_value   = "new_customer",
    r.priority       = 5,
    r.entity_type    = "customer",
    r.entity_pattern = "customer_(C\\d+)_"
WITH r
MATCH (d:Domain {name: "customer"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R14"})
CREATE (c1:Condition {
  fact_pattern: "customer_{cid}_frequency",
  operator:    "==",
  threshold:   1,
  description: "Only one purchase made"
})
CREATE (c2:Condition {
  fact_pattern: "customer_{cid}_recency",
  operator:    "<",
  threshold:   14,
  description: "Purchase was within last 14 days"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R15 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R15"})
SET r.description    = "IF monetary > 1000 AND frequency > 10 THEN recommend premium tier upsell",
    r.action         = "Recommend premium tier upsell for customer {cid}",
    r.action_key     = "recommendation_{cid}_premium_upsell",
    r.action_value   = true,
    r.priority       = 6,
    r.entity_type    = "customer",
    r.entity_pattern = "customer_(C\\d+)_"
WITH r
MATCH (d:Domain {name: "customer"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R15"})
CREATE (c1:Condition {
  fact_pattern: "customer_{cid}_monetary",
  operator:    ">",
  threshold:   1000,
  description: "Total spend exceeds $1000"
})
CREATE (c2:Condition {
  fact_pattern: "customer_{cid}_frequency",
  operator:    ">",
  threshold:   10,
  description: "More than 10 purchases"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// =============================================================================
//  DOMAIN 4: Supplier & Procurement (R16–R20)
// =============================================================================

// ── R16 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R16"})
SET r.description    = "IF supplier price increase > 10% AND alternative exists THEN renegotiate",
    r.action         = "Renegotiate with supplier {sid} — price increase too high, alternatives exist",
    r.action_key     = "recommendation_{sid}_renegotiate",
    r.action_value   = true,
    r.priority       = 7,
    r.entity_type    = "supplier",
    r.entity_pattern = "supplier_(S\\d+)_"
WITH r
MATCH (d:Domain {name: "supplier"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R16"})
CREATE (c1:Condition {
  fact_pattern: "supplier_{sid}_price_increase_pct",
  operator:    ">",
  threshold:   10,
  description: "Supplier price increase exceeds 10%"
})
CREATE (c2:Condition {
  fact_pattern: "supplier_{sid}_has_alternative",
  operator:    "==",
  threshold:   true,
  description: "Alternative supplier is available"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R17 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R17"})
SET r.description    = "IF lead time > 14 days AND stock < 2× reorder point THEN preorder now",
    r.action         = "Preorder {pid} from supplier {sid} NOW — long lead time + low stock",
    r.action_key     = "recommendation_{pid}_preorder",
    r.action_value   = true,
    r.priority       = 9,
    r.entity_type    = "supplier",
    r.entity_pattern = "supplier_(S\\d+)_"
WITH r
MATCH (d:Domain {name: "supplier"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R17"})
CREATE (c1:Condition {
  fact_pattern: "supplier_{sid}_lead_time",
  operator:    ">",
  threshold:   14,
  description: "Supplier lead time exceeds 14 days"
})
CREATE (c2:Condition {
  fact_pattern: "product_{pid}_stock",
  operator:    "<",
  threshold:   "DYNAMIC:product_{pid}_reorder_point_x2",
  description: "Stock is below 2× reorder point"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R18 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R18"})
SET r.description    = "IF supplier reliability < 60% THEN blacklist, activate backup supplier",
    r.action         = "BLACKLIST supplier {sid} — reliability critically low, activate backup",
    r.action_key     = "recommendation_{sid}_blacklist",
    r.action_value   = true,
    r.priority       = 10,
    r.entity_type    = "supplier",
    r.entity_pattern = "supplier_(S\\d+)_"
WITH r
MATCH (d:Domain {name: "supplier"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R18"})
CREATE (c:Condition {
  fact_pattern: "supplier_{sid}_reliability",
  operator:    "<",
  threshold:   60,
  description: "Supplier reliability is below 60%"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// ── R19 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R19"})
SET r.description    = "IF order quantity > 100 AND no bulk discount THEN negotiate bulk pricing",
    r.action         = "Negotiate bulk pricing with supplier {sid} for {pid} — high volume, no discount",
    r.action_key     = "recommendation_{sid}_bulk_negotiation",
    r.action_value   = true,
    r.priority       = 6,
    r.entity_type    = "supplier",
    r.entity_pattern = "supplier_(S\\d+)_"
WITH r
MATCH (d:Domain {name: "supplier"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R19"})
CREATE (c1:Condition {
  fact_pattern: "product_{pid}_avg_sales_rate",
  operator:    ">",
  threshold:   100,
  description: "Monthly order quantity exceeds 100 units"
})
CREATE (c2:Condition {
  fact_pattern: "supplier_{sid}_bulk_discount",
  operator:    "==",
  threshold:   false,
  description: "No bulk discount currently available"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// ── R20 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R20"})
SET r.description    = "IF single source = true AND category = critical THEN recommend dual-sourcing",
    r.action         = "Recommend dual-sourcing for {pid} — single supplier risk on critical product",
    r.action_key     = "recommendation_{pid}_dual_source",
    r.action_value   = true,
    r.priority       = 8,
    r.entity_type    = "supplier",
    r.entity_pattern = "supplier_(S\\d+)_"
WITH r
MATCH (d:Domain {name: "supplier"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R20"})
CREATE (c1:Condition {
  fact_pattern: "supplier_{sid}_single_source",
  operator:    "==",
  threshold:   true,
  description: "Product has only a single supplier"
})
CREATE (c2:Condition {
  fact_pattern: "product_{pid}_is_critical",
  operator:    "==",
  threshold:   true,
  description: "Product category is critical"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c1)
CREATE (r)-[:HAS_CONDITION {order: 2}]->(c2);


// =============================================================================
//  DOMAIN 5: Sales Performance Diagnosis (R21–R25)
// =============================================================================

// ── R21 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R21"})
SET r.description    = "IF revenue this month < 80% of last month THEN diagnose declining sales",
    r.action         = "⚠️ DECLINING SALES for {pid} — revenue fell significantly month-over-month",
    r.action_key     = "diagnosis_{pid}_declining_sales",
    r.action_value   = true,
    r.priority       = 9,
    r.entity_type    = "product",
    r.entity_pattern = "sales_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "sales"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R21"})
CREATE (c:Condition {
  fact_pattern: "sales_{pid}_revenue_vs_last_month_pct",
  operator:    "<",
  threshold:   80,
  description: "Revenue dropped below 80% of previous month"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// ── R22 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R22"})
SET r.description    = "IF top product revenue share > 60% THEN flag over-dependence risk",
    r.action         = "⚠️ OVER-DEPENDENCE on {pid} — diversify product portfolio",
    r.action_key     = "diagnosis_{pid}_over_dependence",
    r.action_value   = true,
    r.priority       = 8,
    r.entity_type    = "product",
    r.entity_pattern = "sales_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "sales"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R22"})
CREATE (c:Condition {
  fact_pattern: "sales_{pid}_revenue_share_pct",
  operator:    ">",
  threshold:   60,
  description: "Single product accounts for >60% of total revenue"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// ── R23 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R23"})
SET r.description    = "IF cart abandonment rate > 70% THEN recommend checkout UX review",
    r.action         = "Recommend checkout UX review for {pid} — very high cart abandonment",
    r.action_key     = "diagnosis_{pid}_high_cart_abandonment",
    r.action_value   = true,
    r.priority       = 7,
    r.entity_type    = "product",
    r.entity_pattern = "sales_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "sales"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R23"})
CREATE (c:Condition {
  fact_pattern: "sales_{pid}_cart_abandonment_rate",
  operator:    ">",
  threshold:   0.70,
  description: "Cart abandonment rate exceeds 70%"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// ── R24 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R24"})
SET r.description    = "IF avg order value dropped > 15% THEN recommend upsell/bundle strategy",
    r.action         = "Recommend upsell/bundle strategy for {pid} — AOV declining",
    r.action_key     = "diagnosis_{pid}_aov_decline",
    r.action_value   = true,
    r.priority       = 6,
    r.entity_type    = "product",
    r.entity_pattern = "sales_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "sales"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R24"})
CREATE (c:Condition {
  fact_pattern: "sales_{pid}_aov_change_pct",
  operator:    "<",
  threshold:   -15,
  description: "Average order value dropped by more than 15%"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// ── R25 ──────────────────────────────────────────────────────────────────────
MERGE (r:Rule {rule_id: "R25"})
SET r.description    = "IF new customer ratio < 20% THEN recommend acquisition campaign",
    r.action         = "Recommend customer acquisition campaign for {pid} — weak new customer flow",
    r.action_key     = "diagnosis_{pid}_weak_acquisition",
    r.action_value   = true,
    r.priority       = 7,
    r.entity_type    = "product",
    r.entity_pattern = "sales_(P\\d+)_"
WITH r
MATCH (d:Domain {name: "sales"}) MERGE (r)-[:IN_DOMAIN]->(d);

MATCH (r:Rule {rule_id: "R25"})
CREATE (c:Condition {
  fact_pattern: "sales_{pid}_new_customer_ratio",
  operator:    "<",
  threshold:   0.20,
  description: "New customer ratio is below 20%"
})
CREATE (r)-[:HAS_CONDITION {order: 1}]->(c);


// =============================================================================
//  Verification queries (run individually after load)
// =============================================================================
//
//  // 1. Total counts per label
//  MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label;
//
//  // 2. Rules per domain
//  MATCH (r:Rule)-[:IN_DOMAIN]->(d:Domain)
//  RETURN d.name AS domain, count(r) AS rule_count
//  ORDER BY domain;
//
//  // 3. Full rule with ordered conditions
//  MATCH (r:Rule {rule_id: "R6"})-[h:HAS_CONDITION]->(c:Condition)
//  RETURN r.rule_id, r.description, r.action, h.order, c
//  ORDER BY h.order;
//
//  // 4. Backward-chaining lookup: rules that can prove a goal pattern
//  MATCH (r:Rule)
//  WHERE r.action_key CONTAINS "clearance_discount"
//  RETURN r.rule_id, r.action_key, r.priority;
//
//  // 5. Find every rule that depends on a given fact (forward index)
//  MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)
//  WHERE c.fact_pattern CONTAINS "stock"
//  RETURN r.rule_id, c.fact_pattern, c.operator, c.threshold;
//
// =============================================================================
