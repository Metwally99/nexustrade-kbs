# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # MongoDB (ERP data)
    MONGO_URI = os.getenv("DB_CONNECT")
    DB_NAME = os.getenv("DB_NAME")

    # Neo4j Aura (rule knowledge base)
    NEO4J_URI      = os.getenv("NEO4J_URI")
    NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
