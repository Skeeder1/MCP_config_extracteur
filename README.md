# Extracteur de Configurations MCP

Pipeline Python automatisé pour extraire les configurations de démarrage des serveurs MCP depuis GitHub.

## Fonctionnalités

**Pipeline en 2 phases** :
- **Phase 1 (Crawler)** : Récupère les fichiers sources depuis GitHub (README, package.json, .env.example, etc.)
- **Phase 2 (Extractor)** : Extrait les configurations via LLM (Claude/OpenRouter)
- **Validation** : Vérifie la qualité et complétude des configurations extraites

**Résultats** :
- Commandes de démarrage
- Arguments
- Variables d'environnement avec métadonnées
- Commandes d'installation
- Score de confiance

## Installation

1. Installer les dépendances:
```bash
pip install -r requirements.txt
```

2. Configurer les variables d'environnement:
```bash
cp .env.example .env
# Éditer .env avec vos credentials (GitHub token, Anthropic API key, etc.)
```

## Utilisation

### Méthode Simplifiée (Recommandée)

```bash
# Pipeline complet (1 commande)
python extract.py pipeline

# Ou phases individuelles
python extract.py crawl              # Phase 1 seulement
python extract.py extract            # Phase 2 seulement
python extract.py validate           # Validation PostgreSQL
python extract.py analyze            # Analyse qualité PostgreSQL
```

### Méthode Classique (toujours supportée)

```bash
# Phase 1: Crawler GitHub
python run_crawler.py

# Phase 2: Extraction LLM
python run_extractor.py

# Validation manuelle
python scripts/validate_extraction_output.py
```

## Résultats de l'Extraction

Le pipeline stocke les données dans PostgreSQL:
- **mcp_servers** : Métadonnées GitHub crawlées
- **mcp_configs** : Configurations extraites avec validation
- **mcp_content** : Contenu des fichiers (README, etc.)
- Statut : `approved` (score ≥ 7.0), `pending` (5.0-7.0), `rejected` (< 5.0)
- Métadonnées : tokens utilisés, fichiers analysés, timestamp

## Structure du projet

```
.
├── extract.py              # 🎯 CLI unifiée (point d'entrée principal)
├── run_crawler.py          # Phase 1: GitHub crawler (legacy, toujours fonctionnel)
├── run_extractor.py        # Phase 2: LLM extractor (legacy, toujours fonctionnel)
├── src/
│   ├── github_crawler.py   # Récupération fichiers GitHub
│   ├── llm_provider.py     # Abstraction LLM (Anthropic/OpenRouter)
│   ├── llm_extractor.py    # Extraction via LLM
│   ├── prompt_builder.py   # Construction du prompt
│   ├── validator.py        # Validation des configs
│   ├── retry_utils.py      # Logique de retry centralisée
│   └── config.py           # Configuration Pydantic
├── scripts/
│   ├── validate_extraction_output.py  # Validation schéma
│   └── analyze_extraction_quality.py  # Analyse qualité/coûts
├── data/
│   └── input/              # Données source (top_200_mcp_servers.json)
├── database/
│   └── schema.sql          # Schéma PostgreSQL
├── config/
│   ├── extraction_prompt.txt  # Template du prompt LLM
│   └── validation_prompt.txt  # Template de validation
└── requirements.txt        # Dépendances Python
```

## Exemple de configuration extraite

```json
{
  "name": "filesystem",
  "install": null,
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"],
  "env": {
    "LOG_LEVEL": {
      "required": false,
      "description": "Logging verbosity level",
      "default": "INFO",
      "example": "DEBUG"
    }
  },
  "_llm_metadata": {
    "input_tokens": 2845,
    "output_tokens": 156,
    "model": "claude-sonnet-4-20250514",
    "provider": "anthropic"
  }
}
```

## Changelog Récent

### v0.2.0 - Simplification & CLI Unifiée
- ✅ **CLI unifiée** : `python extract.py pipeline` (1 commande au lieu de 4)
- ✅ **Code simplifié** : Élimination de 31 lignes de duplication
- ✅ **Constantes nommées** : Magic numbers remplacés par constantes explicites
- ✅ **Retry centralisé** : Logique de retry unifiée dans `retry_utils.py`
- ✅ **Rétrocompatibilité** : Anciens scripts toujours fonctionnels
