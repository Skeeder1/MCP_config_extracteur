#!/usr/bin/env python3
"""
Script d'initialisation de la base de données PostgreSQL.

Ce script :
1. Lit le fichier schema.sql
2. Se connecte à PostgreSQL
3. Exécute le schéma (création des tables, index, contraintes)
4. Affiche un résumé des tables créées
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Ajouter le répertoire parent au path pour importer les modules du projet
sys.path.insert(0, str(Path(__file__).parent.parent))

# Charger les variables d'environnement
load_dotenv()


def get_db_connection_params():
    """Récupère les paramètres de connexion depuis les variables d'environnement."""
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'mydb'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }


def test_connection(conn_params):
    """Test la connexion à PostgreSQL."""
    print("\n📡 Test de connexion à PostgreSQL...")
    print(f"   Host: {conn_params['host']}:{conn_params['port']}")
    print(f"   Database: {conn_params['database']}")
    print(f"   User: {conn_params['user']}")

    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()

        # Tester avec une requête simple
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"\n✅ Connexion réussie!")
        print(f"   PostgreSQL version: {version.split(',')[0]}")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"\n❌ Erreur de connexion: {e}")
        print("\n💡 Vérifiez que :")
        print("   1. PostgreSQL est démarré")
        print("   2. La base de données 'mydb' existe")
        print("   3. Les credentials dans .env sont corrects")
        print("   4. Le port 5432 est accessible")
        return False


def read_schema_file():
    """Lit le contenu du fichier schema.sql."""
    schema_path = Path(__file__).parent / 'schema.sql'

    if not schema_path.exists():
        raise FileNotFoundError(f"Fichier schema.sql non trouvé: {schema_path}")

    with open(schema_path, 'r', encoding='utf-8') as f:
        return f.read()


def execute_schema(conn_params, schema_sql):
    """Exécute le schéma SQL sur la base de données."""
    print("\n🔨 Exécution du schéma SQL...")

    conn = None
    cursor = None

    try:
        # Connexion
        conn = psycopg2.connect(**conn_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Exécuter le schéma
        cursor.execute(schema_sql)

        print("✅ Schéma exécuté avec succès!")

        return True

    except psycopg2.Error as e:
        print(f"❌ Erreur lors de l'exécution du schéma: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def verify_tables(conn_params):
    """Vérifie que les tables ont été créées."""
    print("\n🔍 Vérification des tables créées...")

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()

        # Lister toutes les tables
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)

        tables = cursor.fetchall()

        if tables:
            print(f"\n📋 {len(tables)} table(s) créée(s):")
            for table in tables:
                print(f"   ✓ {table[0]}")

            # Vérifier les tables attendues
            expected_tables = {'mcp_servers', 'mcp_configs', 'mcp_content',
                             'mcp_categories', 'mcp_tags'}
            found_tables = {table[0] for table in tables}

            missing = expected_tables - found_tables
            if missing:
                print(f"\n⚠️  Tables manquantes: {', '.join(missing)}")
            else:
                print("\n✅ Toutes les tables attendues sont présentes!")

            # Compter les index
            cursor.execute("""
                SELECT COUNT(*)
                FROM pg_indexes
                WHERE schemaname = 'public';
            """)
            index_count = cursor.fetchone()[0]
            print(f"\n📊 {index_count} index créé(s)")

            # Vérifier les vues
            cursor.execute("""
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            views = cursor.fetchall()
            if views:
                print(f"\n👁️  {len(views)} vue(s) créée(s):")
                for view in views:
                    print(f"   ✓ {view[0]}")
        else:
            print("❌ Aucune table trouvée!")
            return False

        return True

    except psycopg2.Error as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def print_summary():
    """Affiche un résumé des prochaines étapes."""
    print("\n" + "="*60)
    print("🎉 Initialisation terminée avec succès!")
    print("="*60)
    print("\n📝 Prochaines étapes:")
    print("   1. Vérifier les tables: psql -h localhost -U postgres -d mydb -c '\\dt'")
    print("   2. Voir le schéma d'une table: psql -h localhost -U postgres -d mydb -c '\\d mcp_servers'")
    print("   3. Continuer avec la Phase 2: Création de la couche d'accès aux données")
    print("\n💡 La base de données est prête à être utilisée!")
    print()


def main():
    """Fonction principale."""
    print("="*60)
    print("🚀 Initialisation de la Base de Données PostgreSQL")
    print("="*60)

    # 1. Récupérer les paramètres de connexion
    conn_params = get_db_connection_params()

    # 2. Tester la connexion
    if not test_connection(conn_params):
        print("\n❌ Arrêt du script en raison d'une erreur de connexion.")
        sys.exit(1)

    # 3. Lire le fichier schema.sql
    try:
        schema_sql = read_schema_file()
        print(f"\n📄 Fichier schema.sql chargé ({len(schema_sql)} caractères)")
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    # 4. Exécuter le schéma
    if not execute_schema(conn_params, schema_sql):
        print("\n❌ Arrêt du script en raison d'une erreur d'exécution.")
        sys.exit(1)

    # 5. Vérifier les tables
    if not verify_tables(conn_params):
        print("\n⚠️  Des problèmes ont été détectés lors de la vérification.")
        sys.exit(1)

    # 6. Afficher le résumé
    print_summary()


if __name__ == "__main__":
    main()
