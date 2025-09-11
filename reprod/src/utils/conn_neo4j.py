# file: src/utils/conn_neo4j.py
"""
Container-safe Neo4j connection utility for the ARUK/UCL pipeline.

Design goals:
- No .env reads at import time (entrypoint supplies env; caller passes creds).
- Deterministic logging and timeouts.
- Minimal, explicit API suitable for batch jobs and CI.

Usage:
    from src.utils.conn_neo4j import Neo4jConnection

    conn = Neo4jConnection(uri="bolt://neo4j:7687", user="neo4j", password="testpassword")
    try:
        conn.give_graph_summary()
    finally:
        conn.close()
"""

from __future__ import annotations

import logging
from typing import Optional, Dict

from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import ServiceUnavailable, AuthError


class Neo4jConnection:
    """
    Thin wrapper around the official Neo4j Python driver (v5.x).

    Parameters
    ----------
    uri : str
        Bolt URI, e.g. "bolt://neo4j:7687".
    user : str
        Neo4j username.
    password : str
        Neo4j password.
    max_connection_lifetime : int
        Seconds; renews underlying sockets to avoid stale connections in long jobs.
    connection_timeout : int
        Seconds to wait for initial TCP handshake.
    acquire_timeout : int
        Seconds to wait for a pooled connection.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        *,
        max_connection_lifetime: int = 300,
        connection_timeout: int = 15,
        acquire_timeout: int = 30,
        # You may expose more driver settings here as needed
    ) -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None

        logging.info("Neo4jConnection: initializing driver for %s", self.uri)
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=basic_auth(self.user, self.password),
                max_connection_lifetime=max_connection_lifetime,
                connection_timeout=connection_timeout,
                max_transaction_retry_time=10.0,
            )
        except AuthError as e:
            logging.critical("Neo4j authentication failed: %s", e)
            raise
        except Exception as e:
            logging.critical("Failed to create Neo4j driver: %s", e)
            raise

        # Lightweight connectivity check (won't create a session pool yet in v5)
        try:
            self._driver.verify_connectivity()
            logging.info("Neo4j connectivity verified for %s", self.uri)
        except ServiceUnavailable as e:
            logging.critical("Neo4j service unavailable at %s: %s", self.uri, e)
            # Surface the error so the pipeline fails fast & visibly
            raise
        except Exception as e:
            logging.critical("Neo4j connectivity check failed: %s", e)
            raise

    # --- context manager sugar -------------------------------------------------

    def __enter__(self) -> "Neo4jConnection":
        return self

    def __exit__(self, exc_type, exc_value, tb) -> None:
        self.close()

    # --- lifecycle -------------------------------------------------------------

    @property
    def driver(self):
        if self._driver is None:
            raise RuntimeError("Neo4j driver is not initialized.")
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            logging.info("Closing Neo4j driver")
            self._driver.close()
            self._driver = None
            logging.info("Neo4j driver closed")

    # --- helpers ---------------------------------------------------------------

    def give_graph_summary(self) -> None:
        """
        Log a concise summary of the graph: node and relationship counts.
        """
        counts = self.check_graph_empty()
        if counts is None:
            logging.warning("Failed to compute graph summary.")
            return

        node_count = counts.get("node_count", 0)
        rel_count = counts.get("relationship_count", 0)
        if node_count == 0 and rel_count == 0:
            logging.warning("Graph is empty.")
        else:
            logging.info("Graph contains %d nodes and %d relationships.", node_count, rel_count)

    def check_graph_empty(self) -> Optional[Dict[str, int]]:
        """
        Return counts of nodes and relationships, or None on failure.

        Returns
        -------
        dict | None
            {'node_count': int, 'relationship_count': int} or None if query failed.
        """
        try:
            with self.driver.session() as session:
                def _counts(tx):
                    rec1 = tx.run("MATCH (n) RETURN count(n) AS c").single()
                    rec2 = tx.run("MATCH ()-[r]-() RETURN count(r) AS c").single()
                    node_c = rec1["c"] if rec1 is not None else 0
                    rel_c = rec2["c"] if rec2 is not None else 0
                    return {"node_count": int(node_c), "relationship_count": int(rel_c)}

                return session.execute_read(_counts)
        except Exception as e:
            logging.error("Failed to compute graph counts: %s", e)
            return None