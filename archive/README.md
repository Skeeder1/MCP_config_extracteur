# Archive

Ce dossier contient les fichiers legacy qui ne sont plus utilisés dans le workflow actuel.

## extract_mcp_servers.py

Script original pour extraire les serveurs MCP depuis la base de données Supabase.

**Status** : Non utilisé dans le workflow actuel (Phase 1 + Phase 2).

Le workflow actuel démarre directement avec le fichier `data/input/top_200_mcp_servers.json` déjà préparé.

### Workflow Actuel

```bash
# Phase 1: Crawler GitHub
python run_crawler.py

# Phase 2: Extraction LLM
python run_extractor.py
```

ou simplement :

```bash
# Pipeline complet
python extract.py pipeline
```

### Historique

Ce script était utilisé pour :
- Se connecter à Supabase
- Récupérer les serveurs MCP
- Les dédupliquer par repository GitHub
- Les trier par nombre d'étoiles
- Générer `top_200_mcp_servers.json`

Le fichier résultant est maintenant maintenu manuellement dans `data/input/`.
