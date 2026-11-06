# NexusTrade · Knowledge-Based Decision Support

A team project connecting mock ERP data to an expert system for e-commerce decisions. Rules cover pricing, inventory, customer segmentation, suppliers, and sales performance.

## Architecture

- Forward chaining evaluates available facts and produces recommendations.
- Backward chaining investigates a user-selected goal and records the reasoning trace.
- Neo4j stores the rule knowledge base. MongoDB stores ERP entities, with a mock option for local development.
- A Flask interface presents rules, data, and explanations.

## Setup

```bash
python -m venv .venv
pip install -r requirements.txt
```

Activate your environment and provide database settings through environment variables. The application uses `DB_CONNECT`, `DB_NAME`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`. Create and seed your own databases using `schema.cypher` and `seed_rules.cypher` after reviewing their contents. Start the web application with `python app.py`.

No credentials or customer data are included. The system is an educational prototype and requires database services and configuration to run end to end.
