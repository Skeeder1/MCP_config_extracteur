#!/usr/bin/env python3
"""
Script d'extraction des 200 serveurs MCP avec le plus d'étoiles GitHub.
Extrait depuis une base de données Supabase et génère un fichier JSON.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

from dotenv import load_dotenv
from supabase import create_client, Client


def load_config() -> tuple[str, str]:
    """
    Charge la configuration depuis les variables d'environnement.

    Returns:
        Tuple contenant (SUPABASE_URL, SUPABASE_KEY)

    Raises:
        ValueError: Si les variables d'environnement ne sont pas définies
    """
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url:
        raise ValueError(
            "SUPABASE_URL n'est pas définie. "
            "Veuillez créer un fichier .env basé sur .env.example"
        )

    if not supabase_key:
        raise ValueError(
            "SUPABASE_KEY n'est pas définie. "
            "Veuillez créer un fichier .env basé sur .env.example"
        )

    return supabase_url, supabase_key


def connect_to_supabase(url: str, key: str) -> Client:
    """
    Crée une connexion au client Supabase.

    Args:
        url: URL du projet Supabase
        key: Clé API anonyme Supabase

    Returns:
        Client Supabase initialisé

    Raises:
        Exception: Si la connexion échoue
    """
    try:
        client = create_client(url, key)
        return client
    except Exception as e:
        raise Exception(f"Erreur de connexion à Supabase: {e}")


def fetch_top_mcp_servers(client: Client, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Récupère les serveurs MCP avec le plus d'étoiles GitHub (dédupliqués par repo).

    Args:
        client: Client Supabase
        limit: Nombre de serveurs à récupérer (défaut: 200)

    Returns:
        Liste des serveurs MCP

    Raises:
        Exception: Si la requête échoue
    """
    try:
        # 1. Récupérer tous les serveurs
        print("   Récupération des serveurs MCP...")
        servers_response = client.table("mcp_servers") \
            .select("id, slug, name, display_name, tagline, short_description, install_count, favorite_count") \
            .execute()

        if not servers_response.data:
            return []

        # 2. Récupérer toutes les informations GitHub
        print("   Récupération des informations GitHub...")
        github_response = client.table("mcp_github_info") \
            .select("server_id, github_url, github_stars, github_forks, github_owner, github_repo") \
            .not_.is_("github_url", "null") \
            .execute()

        if not github_response.data:
            return []

        # 3. Créer un dictionnaire pour les infos GitHub indexées par server_id
        github_by_server = {
            item["server_id"]: item
            for item in github_response.data
        }

        # 4. Joindre les données et dédupliquer par github_url
        repos_dict = {}
        for server in servers_response.data:
            server_id = server["id"]
            github_info = github_by_server.get(server_id)

            if not github_info:
                continue

            github_url = github_info.get("github_url")
            if not github_url:
                continue

            github_stars = github_info.get("github_stars", 0)
            install_count = server.get("install_count", 0)
            favorite_count = server.get("favorite_count", 0)

            # Si ce repo n'existe pas encore ou si ce serveur a de meilleures métriques
            if github_url not in repos_dict or \
               install_count > repos_dict[github_url]["_install_count"] or \
               (install_count == repos_dict[github_url]["_install_count"] and
                favorite_count > repos_dict[github_url]["_favorite_count"]):

                repos_dict[github_url] = {
                    "slug": server.get("slug"),
                    "name": server.get("name"),
                    "display_name": server.get("display_name"),
                    "tagline": server.get("tagline", ""),
                    "short_description": server.get("short_description", ""),
                    "github_url": github_url,
                    "github_stars": github_stars,
                    "github_forks": github_info.get("github_forks", 0),
                    "github_owner": github_info.get("github_owner", ""),
                    "github_repo": github_info.get("github_repo", ""),
                    "_install_count": install_count,
                    "_favorite_count": favorite_count
                }

        # 5. Convertir en liste et trier par nombre d'étoiles
        print(f"   {len(repos_dict)} repositories uniques trouvés")
        deduplicated_servers = list(repos_dict.values())
        deduplicated_servers.sort(key=lambda x: x.get("github_stars", 0), reverse=True)

        # 6. Prendre les N premiers et retirer les champs internes
        top_servers = deduplicated_servers[:limit]
        for server in top_servers:
            server.pop("_install_count", None)
            server.pop("_favorite_count", None)

        return top_servers

    except Exception as e:
        raise Exception(f"Erreur lors de la récupération des données: {e}")


def create_json_output(servers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Crée la structure JSON de sortie avec métadonnées.

    Args:
        servers: Liste des serveurs MCP

    Returns:
        Dictionnaire contenant les métadonnées et la liste des serveurs
    """
    return {
        "metadata": {
            "extraction_date": datetime.now(timezone.utc).isoformat(),
            "total_servers": len(servers),
            "description": "Top 200 MCP servers by GitHub stars (deduplicated by repository)"
        },
        "servers": servers
    }


def save_to_json(data: Dict[str, Any], output_file: str = "top_200_mcp_servers.json"):
    """
    Sauvegarde les données dans un fichier JSON.

    Args:
        data: Données à sauvegarder
        output_file: Chemin du fichier de sortie (défaut: top_200_mcp_servers.json)
    """
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Fichier créé avec succès: {output_file}")
        print(f"✓ {data['metadata']['total_servers']} serveurs extraits")
    except Exception as e:
        raise Exception(f"Erreur lors de l'écriture du fichier JSON: {e}")


def main():
    """Fonction principale du script."""
    try:
        print("Démarrage de l'extraction des serveurs MCP...")

        # 1. Charger la configuration
        print("1. Chargement de la configuration...")
        supabase_url, supabase_key = load_config()
        print(f"   URL: {supabase_url}")

        # 2. Connexion à Supabase
        print("2. Connexion à Supabase...")
        client = connect_to_supabase(supabase_url, supabase_key)
        print("   ✓ Connecté")

        # 3. Récupération des données
        print("3. Récupération des 200 serveurs avec le plus d'étoiles...")
        servers = fetch_top_mcp_servers(client, limit=200)

        if not servers:
            print("   ⚠ Aucun serveur trouvé", file=sys.stderr)
            sys.exit(1)

        print(f"   ✓ {len(servers)} serveurs récupérés")

        # 4. Création de la structure JSON
        print("4. Création de la structure JSON...")
        output_data = create_json_output(servers)

        # 5. Sauvegarde dans un fichier
        print("5. Sauvegarde dans le fichier...")
        save_to_json(output_data)

        print("\n✓ Extraction terminée avec succès!")

    except ValueError as e:
        print(f"Erreur de configuration: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
