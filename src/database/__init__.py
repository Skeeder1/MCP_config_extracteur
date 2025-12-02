"""
Database package - Couche d'accès aux données PostgreSQL.

Ce package contient:
- DatabaseManager: Gestion des connexions et transactions
- Repositories: Accès aux données par table (pattern Repository)
"""

from .db_manager import DatabaseManager

__all__ = ['DatabaseManager']
