"""
Dependency definitions for AgentHeaven.

This module contains all dependency definitions used by the dependency manager.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DependencyInfo:
    """Information about a dependency."""

    name: str
    packages: List[str]
    install: str
    description: str
    optional: bool = True
    required_for: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.required_for is None:
            self.required_for = []


def get_default_dependencies() -> dict:
    """Get all default dependency definitions."""
    return {
        "mysql": DependencyInfo(
            name="mysql",
            packages=["pymysql"],
            install="pip install pymysql mysqlclient",
            description="MySQL database support",
            required_for=["database", "mysql_connections"],
        ),
        "postgresql": DependencyInfo(
            name="postgresql",
            packages=["psycopg2"],
            install="pip install psycopg2-binary",
            description="PostgreSQL database support",
            required_for=["database", "postgresql_connections"],
        ),
        "duckdb": DependencyInfo(
            name="duckdb",
            packages=["duckdb"],
            install="pip install duckdb duckdb-engine",
            description="DuckDB database support",
            required_for=["database", "analytics"],
        ),
        "spacy": DependencyInfo(
            name="spacy",
            packages=["spacy"],
            install="pip install spacy",
            description="spaCy NLP library",
            required_for=["nlp", "text_processing"],
        ),
        "prompt_toolkit": DependencyInfo(
            name="prompt_toolkit",
            packages=["prompt_toolkit"],
            install="pip install prompt_toolkit",
            description="Enhanced CLI experience",
            required_for=["cli", "user_interface"],
        ),
        "fastmcp": DependencyInfo(
            name="fastmcp",
            packages=["fastmcp"],
            install="pip install fastmcp",
            description="FastMCP interface",
            required_for=["mcp", "interfaces"],
        ),
        "pyahocorasick": DependencyInfo(
            name="pyahocorasick",
            packages=["ahocorasick"],
            install="pip install pyahocorasick",
            description="Aho-Corasick automaton for fast string matching",
            required_for=["string_search", "pattern_matching"],
        ),
        "chromadb": DependencyInfo(
            name="chromadb",
            packages=["chromadb"],
            install="pip install chromadb",
            description="ChromaDB vector database",
            required_for=["vector_db", "chroma_integration"],
        ),
        "mongodb": DependencyInfo(
            name="mongodb",
            packages=["pymongo"],
            install="pip install pymongo",
            description="MongoDB database support",
            required_for=["database", "mongodb_connections"],
        ),
        "milvus": DependencyInfo(
            name="milvus",
            packages=["pymilvus"],
            install="pip install pymilvus",
            description="Milvus vector database",
            required_for=["vector_db", "milvus_integration"],
        ),
        "lancedb": DependencyInfo(
            name="lancedb",
            packages=["lancedb", "pyarrow"],
            install="pip install lancedb pyarrow",
            description="Lance vector database",
            required_for=["vector_db", "lance_integration"],
        ),
        "llamaindex": DependencyInfo(
            name="llamaindex",
            packages=["llama_index"],
            install="pip install llama-index llama-index-llms-ollama",
            description="LlamaIndex integration",
            required_for=["rag", "llm_integration"],
        ),
        "neo4j": DependencyInfo(
            name="neo4j",
            packages=["neo4j"],
            install="pip install neo4j",
            description="Neo4j graph database",
            required_for=["graph_db", "neo4j_integration"],
        ),
    }
