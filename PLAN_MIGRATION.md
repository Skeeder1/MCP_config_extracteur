# Plan de Migration : JSON vers PostgreSQL pour le Pipeline MCP

## 📋 Vue d'ensemble

**Objectif** : Migrer complètement le pipeline d'extraction MCP du stockage JSON vers une base de données PostgreSQL locale.

**Contexte** :
- Système actuel : Pipeline Python utilisant 3 fichiers JSON pour la persistence
- Système cible : PostgreSQL local avec 5 tables (schéma v2.0)
- Stratégie : Repartir de zéro (pas de migration des données existantes)

**Base de données cible** :
- Host: localhost:5432
- Database: mydb
- User: postgres
- Password: postgres

---

## 🎯 Principes de Migration

1. **Migration incrémentale** : Chaque phase est indépendante et testable
2. **Pas de perte de fonctionnalité** : Le pipeline doit continuer à fonctionner à chaque étape
3. **Traçabilité** : Garder l'historique des modifications
4. **Réversibilité** : Possibilité de rollback par phase

---

## 📊 Architecture Cible

```
PostgreSQL Database (mydb)
├── mcp_servers (table centrale)
│   ├── Colonnes GitHub (url, owner, repo, stars, forks, etc.)
│   ├── Categories/tags (UUID arrays, vides initialement)
│   └── Status (approved/pending/rejected)
├── mcp_configs (1:1 avec mcp_servers)
│   └── config_json (JSONB complet)
├── mcp_content (1:N avec mcp_servers)
│   └── README, about, faq, changelog
├── mcp_categories (référentiel, vide initialement)
└── mcp_tags (référentiel, vide initialement)
```

---

# PHASE 1 : Configuration et Schéma de Base de Données

## Objectif
Créer le schéma PostgreSQL complet et configurer la connexion à la base de données.

## Prompt pour Claude (Conversation 1)

```markdown
# PHASE 1 : Configuration et Schéma PostgreSQL

Contexte : Je migre mon pipeline MCP d'extraction depuis des fichiers JSON vers PostgreSQL.

Répertoire de travail : `/home/luffy/Github/extract_config`

## Tâche 1 : Créer le fichier de schéma SQL

Crée un fichier `database/schema.sql` basé sur le schéma décrit dans `DATABASE_MCPSPOT.md`.

Le fichier doit contenir :
1. Les 5 tables : mcp_servers, mcp_configs, mcp_content, mcp_categories, mcp_tags
2. Tous les index nécessaires (GIN pour arrays/JSONB, B-tree pour recherches)
3. Les contraintes (foreign keys, checks, unique)
4. Les valeurs par défaut

Structure du fichier :
```sql
-- Drop existing tables (pour pouvoir réexécuter le script)
DROP TABLE IF EXISTS mcp_content CASCADE;
DROP TABLE IF EXISTS mcp_configs CASCADE;
DROP TABLE IF EXISTS mcp_servers CASCADE;
DROP TABLE IF EXISTS mcp_categories CASCADE;
DROP TABLE IF EXISTS mcp_tags CASCADE;

-- Create tables...
```

## Tâche 2 : Mettre à jour le fichier .env

Ajoute les variables de connexion PostgreSQL dans `.env` :
```env
# PostgreSQL Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb
DB_USER=postgres
DB_PASSWORD=postgres
DB_POOL_MIN_SIZE=1
DB_POOL_MAX_SIZE=10
```

Conserve toutes les autres variables existantes.

## Tâche 3 : Créer un script d'initialisation

Crée `database/init_db.py` qui :
1. Lit le fichier schema.sql
2. Se connecte à PostgreSQL
3. Exécute le schéma
4. Affiche un message de confirmation

Utilise psycopg2 pour la connexion.

## Tâche 4 : Tester la connexion

Exécute le script d'initialisation et vérifie que :
- Les 5 tables sont créées
- Les index sont présents
- La connexion fonctionne

Commandes à exécuter :
```bash
python database/init_db.py
psql -h localhost -U postgres -d mydb -c "\dt"
```

## Critères de succès
- [ ] Fichier schema.sql créé avec les 5 tables
- [ ] Variables d'environnement ajoutées à .env
- [ ] Script init_db.py fonctionnel
- [ ] Tables créées dans PostgreSQL
- [ ] Connexion testée et validée
```

## Fichiers à créer
- `database/schema.sql` (nouveau)
- `database/init_db.py` (nouveau)
- `database/__init__.py` (nouveau, vide)

## Fichiers à modifier
- `.env` (ajouter variables DB)

## Tests de validation
```bash
# Vérifier que les tables existent
psql -h localhost -U postgres -d mydb -c "\dt"

# Vérifier la structure de mcp_servers
psql -h localhost -U postgres -d mydb -c "\d mcp_servers"
```

---

# PHASE 2 : Couche d'Accès aux Données (Data Access Layer)

## Objectif
Créer une couche d'abstraction pour toutes les opérations de base de données.

## Prompt pour Claude (Conversation 2)

```markdown
# PHASE 2 : Création de la Couche d'Accès aux Données

Contexte : Phase 1 terminée, les tables PostgreSQL sont créées. Je dois maintenant créer une couche d'accès aux données.

Répertoire de travail : `/home/luffy/Github/extract_config`

## Tâche 1 : Créer le gestionnaire de connexion

Crée `src/database/db_manager.py` avec une classe `DatabaseManager` qui :
- Gère le pool de connexions PostgreSQL (psycopg2)
- Lit les credentials depuis .env
- Fournit des méthodes de connexion/déconnexion
- Gère les transactions (begin/commit/rollback)
- Inclut un context manager pour les connexions

Exemple d'interface :
```python
class DatabaseManager:
    def __init__(self)
    def get_connection(self) -> connection
    def execute_query(self, query: str, params: tuple)
    def execute_many(self, query: str, params: list)
    def fetch_one(self, query: str, params: tuple)
    def fetch_all(self, query: str, params: tuple)
```

## Tâche 2 : Créer les repositories (pattern Repository)

Crée 5 fichiers dans `src/database/repositories/` :

### 2.1 `servers_repository.py`
```python
class ServersRepository:
    def insert_server(self, server_data: dict) -> str  # retourne UUID
    def get_server_by_github_url(self, github_url: str) -> dict | None
    def get_server_by_slug(self, slug: str) -> dict | None
    def update_server(self, server_id: str, updates: dict)
    def get_all_servers(self, status: str = None) -> list[dict]
    def server_exists(self, github_url: str) -> bool
```

### 2.2 `configs_repository.py`
```python
class ConfigsRepository:
    def insert_config(self, server_id: str, config_data: dict) -> str
    def get_config_by_server_id(self, server_id: str) -> dict | None
    def update_config(self, server_id: str, config_json: dict)
    def config_exists(self, server_id: str) -> bool
```

### 2.3 `content_repository.py`
```python
class ContentRepository:
    def insert_content(self, server_id: str, content_type: str, content: str) -> str
    def get_content_by_server(self, server_id: str) -> list[dict]
    def get_content_by_type(self, server_id: str, content_type: str) -> dict | None
    def update_content(self, content_id: str, content: str)
```

### 2.4 `categories_repository.py`
```python
class CategoriesRepository:
    def insert_category(self, slug: str, name: str, icon: str, color: str) -> str
    def get_all_categories(self) -> list[dict]
    def get_category_by_slug(self, slug: str) -> dict | None
```

### 2.5 `tags_repository.py`
```python
class TagsRepository:
    def insert_tag(self, slug: str, name: str, color: str) -> str
    def get_all_tags(self) -> list[dict]
    def get_tag_by_slug(self, slug: str) -> dict | None
```

## Tâche 3 : Créer un fichier de tests unitaires

Crée `tests/test_database.py` avec des tests pour :
- Connexion à la base de données
- Insert/Select sur chaque repository
- Gestion des transactions (rollback)
- Contraintes (foreign keys, unique)

Utilise pytest.

## Tâche 4 : Installer les dépendances

Ajoute à `requirements.txt` :
```
psycopg2-binary==2.9.9
pytest==7.4.3
```

## Critères de succès
- [ ] DatabaseManager créé et fonctionnel
- [ ] 5 repositories créés avec toutes les méthodes
- [ ] Tests unitaires passent
- [ ] Documentation des méthodes (docstrings)
- [ ] Gestion d'erreurs robuste
```

## Fichiers à créer
- `src/database/__init__.py` (nouveau)
- `src/database/db_manager.py` (nouveau)
- `src/database/repositories/__init__.py` (nouveau)
- `src/database/repositories/servers_repository.py` (nouveau)
- `src/database/repositories/configs_repository.py` (nouveau)
- `src/database/repositories/content_repository.py` (nouveau)
- `src/database/repositories/categories_repository.py` (nouveau)
- `src/database/repositories/tags_repository.py` (nouveau)
- `tests/test_database.py` (nouveau)

## Tests de validation
```bash
# Installer les dépendances
pip install psycopg2-binary pytest

# Exécuter les tests
pytest tests/test_database.py -v
```

---

# PHASE 3 : Migration du Crawler (Phase 1 du Pipeline)

## Objectif
Remplacer l'écriture dans `github_crawled_data.json` par des insertions dans PostgreSQL.

## Prompt pour Claude (Conversation 3)

```markdown
# PHASE 3 : Migration du Crawler vers PostgreSQL

Contexte : La couche d'accès aux données est prête. Je dois migrer `run_crawler.py` pour qu'il écrive dans PostgreSQL au lieu de JSON.

Répertoire de travail : `/home/luffy/Github/extract_config`

## Analyse préliminaire

Lis d'abord ces fichiers pour comprendre le code actuel :
- `run_crawler.py` (lignes 59-313 : load_existing + main)
- `src/github_crawler.py` (classe GitHubCrawler)

## Tâche 1 : Créer un service Crawler avec persistence DB

Crée `src/services/crawler_service.py` avec une classe `CrawlerService` qui :

```python
class CrawlerService:
    def __init__(self, db_manager: DatabaseManager):
        self.servers_repo = ServersRepository(db_manager)
        self.content_repo = ContentRepository(db_manager)
        self.crawler = GitHubCrawler()

    def process_server(self, server_input: dict) -> dict:
        """
        Crawl un serveur GitHub et l'enregistre dans la DB.

        Args:
            server_input: Dict avec github_url, slug, name, etc.

        Returns:
            Dict avec status (success/error) et server_id
        """
        # 1. Vérifier si le serveur existe déjà (par github_url)
        # 2. Si existe, vérifier la date de dernière MAJ (updated_at)
        # 3. Si récent (<7 jours), skip
        # 4. Sinon, crawler GitHub (fetch metadata + files)
        # 5. Insérer/Update dans mcp_servers
        # 6. Extraire README et insérer dans mcp_content (type='readme')
        # 7. Return status

    def get_processed_urls(self) -> set[str]:
        """Retourne l'ensemble des URLs déjà crawlées"""
        # SELECT github_url FROM mcp_servers

    def get_crawl_statistics(self) -> dict:
        """Statistiques du crawling"""
        # COUNT par status, nombre total, etc.
```

## Tâche 2 : Modifier run_crawler.py

Modifie `run_crawler.py` pour :

1. **Remplacer `load_existing_crawled_repos()`** :
   ```python
   # AVANT (ligne 59-120)
   def load_existing_crawled_repos() -> tuple[list, set]:
       # Lit github_crawled_data.json

   # APRÈS
   def get_processed_repos(crawler_service: CrawlerService) -> set[str]:
       return crawler_service.get_processed_urls()
   ```

2. **Modifier la boucle principale dans `main()`** :
   ```python
   # AVANT (ligne 171-277)
   for server in servers:
       repo_data = crawler.fetch_repo_data(...)
       repos.append(repo_data)

   # Écriture JSON
   json.dump(output, f)

   # APRÈS
   db_manager = DatabaseManager()
   crawler_service = CrawlerService(db_manager)

   for server in servers:
       result = crawler_service.process_server(server)
       # Pas d'écriture JSON, tout est dans la DB

   # Afficher les stats
   stats = crawler_service.get_crawl_statistics()
   ```

3. **Conserver la logique de déduplication** :
   - Utiliser `get_processed_urls()` pour skip les URLs déjà crawlées
   - Sauf si flag `--reset` est passé

4. **Gérer les erreurs** :
   - Transactions par serveur (commit/rollback individuel)
   - Logger les erreurs sans bloquer le pipeline

## Tâche 3 : Extraction du README

Dans `CrawlerService.process_server()`, ajoute la logique pour :
1. Extraire le contenu du README depuis `repo_data['files']['README.md']`
2. Insérer dans `mcp_content` avec `content_type='readme'`

## Tâche 4 : Tests

Crée `tests/test_crawler_service.py` pour tester :
- Insertion d'un nouveau serveur
- Skip d'un serveur existant
- Extraction et stockage du README
- Gestion d'erreurs GitHub API

## Tâche 5 : Mode compatibilité (optionnel)

Ajoute un flag `--output-json` pour continuer à générer le JSON en parallèle (pour transition douce) :
```python
if args.output_json:
    # Exporter la DB vers JSON
    export_to_json(crawler_service, config.output_file)
```

## Critères de succès
- [ ] CrawlerService créé et testé
- [ ] run_crawler.py modifié pour utiliser PostgreSQL
- [ ] README extrait et stocké dans mcp_content
- [ ] Déduplication fonctionnelle
- [ ] Stats affichées correctement
- [ ] Tests passent
```

## Fichiers à créer
- `src/services/__init__.py` (nouveau)
- `src/services/crawler_service.py` (nouveau)
- `tests/test_crawler_service.py` (nouveau)

## Fichiers à modifier
- `run_crawler.py` (refactoring majeur)

## Tests de validation
```bash
# Exécuter le crawler en mode test
python run_crawler.py --limit 5

# Vérifier l'insertion dans la DB
psql -h localhost -U postgres -d mydb -c "SELECT COUNT(*) FROM mcp_servers;"
psql -h localhost -U postgres -d mydb -c "SELECT COUNT(*) FROM mcp_content WHERE content_type='readme';"

# Vérifier les données
psql -h localhost -U postgres -d mydb -c "SELECT slug, name, github_stars FROM mcp_servers LIMIT 5;"
```

---

# PHASE 4 : Migration de l'Extractor (Phase 2 du Pipeline)

## Objectif
Remplacer la lecture de `github_crawled_data.json` et l'écriture dans `extracted_configs.json` par des opérations PostgreSQL.

## Prompt pour Claude (Conversation 4)

```markdown
# PHASE 4 : Migration de l'Extractor vers PostgreSQL

Contexte : Le crawler écrit maintenant dans PostgreSQL. Je dois migrer `run_extractor.py` pour qu'il lise depuis la DB et écrive les configs dans `mcp_configs`.

Répertoire de travail : `/home/luffy/Github/extract_config`

## Analyse préliminaire

Lis ces fichiers pour comprendre le flux :
- `run_extractor.py` (lignes 63-499 : load_existing + main_async)
- `src/llm_extractor.py`
- `src/llm_validator.py`

## Tâche 1 : Créer le service Extractor

Crée `src/services/extractor_service.py` avec :

```python
class ExtractorService:
    def __init__(self, db_manager: DatabaseManager):
        self.servers_repo = ServersRepository(db_manager)
        self.configs_repo = ConfigsRepository(db_manager)
        self.db_manager = db_manager
        self.llm_extractor = LLMExtractor()
        self.llm_validator = LLMValidator()

    def get_servers_to_process(self, limit: int = None) -> list[dict]:
        """
        Récupère les serveurs qui n'ont pas encore de config.

        Returns:
            Liste de dicts avec server_id, github_url, metadata, files
        """
        # SELECT serveurs qui n'ont pas d'entrée dans mcp_configs
        # JOIN avec mcp_content pour récupérer le README

    def process_server(self, server: dict) -> dict:
        """
        Extrait la config d'un serveur et l'enregistre.

        Args:
            server: Dict avec server_id, metadata, README content

        Returns:
            Dict avec status, config, validation result
        """
        # 1. Construire le prompt (PromptBuilder)
        # 2. Extraire config via LLM
        # 3. Insérer dans mcp_configs
        # 4. Return status

    async def process_batch(self, servers: list[dict]) -> list[dict]:
        """
        Traite un batch de serveurs avec validation LLM.

        Workflow:
        1. Extract configs en parallèle (asyncio.gather)
        2. Valider le batch via LLMValidator
        3. Mettre à jour les status dans mcp_servers
        4. Return results
        """

    def update_server_status(self, server_id: str, status: str, confidence: float):
        """Met à jour le status du serveur après validation"""
        # UPDATE mcp_servers SET status = ?, updated_at = NOW()

    def get_extraction_statistics(self) -> dict:
        """Statistiques d'extraction"""
        # COUNT par status (approved/pending/rejected)
```

## Tâche 2 : Modifier run_extractor.py

Refactore `run_extractor.py` :

1. **Remplacer `load_existing_extractions()`** :
   ```python
   # AVANT (ligne 63-124)
   def load_existing_extractions() -> tuple[list, set]:
       # Lit extracted_configs.json

   # APRÈS
   def get_servers_to_process(extractor_service: ExtractorService, limit: int) -> list[dict]:
       return extractor_service.get_servers_to_process(limit)
   ```

2. **Modifier `main_async()`** :
   ```python
   # AVANT (ligne 295-499)
   # Lecture de github_crawled_data.json
   # Écriture dans extracted_configs.json

   # APRÈS
   async def main_async():
       db_manager = DatabaseManager()
       extractor_service = ExtractorService(db_manager)

       # Récupérer les serveurs non traités
       servers = extractor_service.get_servers_to_process(limit=config.test_limit)

       # Traiter par batches
       for batch in batches(servers, config.batch_size):
           results = await extractor_service.process_batch(batch)
           # Les configs sont déjà en DB

       # Afficher stats
       stats = extractor_service.get_extraction_statistics()
   ```

3. **Mapping des données** :
   - Lire les serveurs depuis `mcp_servers` + README depuis `mcp_content`
   - Construire le prompt comme avant (avec metadata + files)
   - Extraire la config via LLM
   - Stocker dans `mcp_configs` avec `config_json` (JSONB)
   - Mettre à jour `mcp_servers.status` selon validation

## Tâche 3 : Gestion du status de validation

Mapper les résultats de validation vers `mcp_servers.status` :
```python
# Score LLM → Status DB
if score >= 7.0:
    status = 'approved'
elif score >= 5.0:
    status = 'pending'  # needs_review
else:
    status = 'rejected'
```

## Tâche 4 : Reconstruction du contexte README

Puisque les fichiers ne sont plus stockés en JSON, il faut :
1. Récupérer le README depuis `mcp_content` (type='readme')
2. Simuler la structure `files` pour le PromptBuilder :
   ```python
   files = {
       'README.md': content_from_db
   }
   ```

## Tâche 5 : Tests

Crée `tests/test_extractor_service.py` pour tester :
- Récupération des serveurs à traiter
- Extraction d'une config
- Validation et mise à jour du status
- Traitement par batch

## Critères de succès
- [ ] ExtractorService créé
- [ ] run_extractor.py migré vers PostgreSQL
- [ ] Configs stockées dans mcp_configs (JSONB)
- [ ] Status mis à jour dans mcp_servers
- [ ] Tests passent
- [ ] Stats correctes
```

## Fichiers à créer
- `src/services/extractor_service.py` (nouveau)
- `tests/test_extractor_service.py` (nouveau)

## Fichiers à modifier
- `run_extractor.py` (refactoring majeur)

## Tests de validation
```bash
# Exécuter l'extractor en mode test
python run_extractor.py --limit 5

# Vérifier les configs dans la DB
psql -h localhost -U postgres -d mydb -c "SELECT COUNT(*) FROM mcp_configs;"

# Vérifier les status
psql -h localhost -U postgres -d mydb -c "SELECT status, COUNT(*) FROM mcp_servers GROUP BY status;"

# Voir un exemple de config
psql -h localhost -U postgres -d mydb -c "SELECT s.name, c.config_json FROM mcp_servers s JOIN mcp_configs c ON c.server_id = s.id LIMIT 1;"
```

---

# PHASE 5 : Migration des Scripts de Validation

## Objectif
Migrer les scripts de validation pour qu'ils lisent depuis PostgreSQL au lieu des fichiers JSON.

## Prompt pour Claude (Conversation 5)

```markdown
# PHASE 5 : Migration des Scripts de Validation

Contexte : Le pipeline complet écrit maintenant dans PostgreSQL. Je dois migrer les scripts de validation et d'analyse.

Répertoire de travail : `/home/luffy/Github/extract_config`

## Tâche 1 : Migrer validate_extraction_output.py

Modifie `scripts/validate_extraction_output.py` :

```python
# AVANT
def validate_extraction_output(file_path: str):
    with open(file_path, 'r') as f:
        data = json.load(f)
    # Valide la structure JSON

# APRÈS
def validate_extraction_output(db_manager: DatabaseManager = None):
    """Valide les données dans PostgreSQL"""
    if db_manager is None:
        db_manager = DatabaseManager()

    configs_repo = ConfigsRepository(db_manager)
    servers_repo = ServersRepository(db_manager)

    # Récupérer toutes les extractions
    servers = servers_repo.get_all_servers()

    # Validation :
    # 1. Tous les serveurs ont-ils une config ?
    # 2. Les configs sont-elles valides (schema) ?
    # 3. Les status sont-ils cohérents ?

    # Afficher rapport
```

Nouvelles validations :
- Intégrité référentielle (foreign keys)
- Contraintes respectées
- Pas de NULL sur colonnes NOT NULL
- Configs JSONB valides

## Tâche 2 : Migrer analyze_extraction_quality.py

Modifie `scripts/analyze_extraction_quality.py` :

```python
# AVANT
def analyze_extraction_quality(file_path: str):
    with open(file_path, 'r') as f:
        data = json.load(f)
    # Analyse des stats

# APRÈS
def analyze_extraction_quality(db_manager: DatabaseManager = None):
    """Analyse qualité depuis PostgreSQL"""
    if db_manager is None:
        db_manager = DatabaseManager()

    servers_repo = ServersRepository(db_manager)
    configs_repo = ConfigsRepository(db_manager)

    # Requêtes SQL pour les stats :
    # - COUNT(*) par status
    # - AVG(github_stars) par status
    # - Distribution des langages
    # - Top 10 serveurs par stars
    # - Taux de succès

    # Afficher rapport détaillé
```

## Tâche 3 : Créer un script d'export JSON (optionnel)

Crée `scripts/export_to_json.py` pour exporter la DB vers JSON si besoin :

```python
def export_to_json(output_file: str):
    """Exporte la base de données vers JSON (compatibilité)"""
    db_manager = DatabaseManager()

    # Récupérer tous les serveurs avec configs
    # Formatter comme extracted_configs.json
    # Écrire dans output_file
```

Utile pour backup ou compatibilité temporaire.

## Tâche 4 : Tests

Crée `tests/test_validation_scripts.py` pour tester :
- validate_extraction_output() sur DB
- analyze_extraction_quality() génère stats correctes

## Critères de succès
- [ ] validate_extraction_output.py migré
- [ ] analyze_extraction_quality.py migré
- [ ] Scripts fonctionnent avec PostgreSQL
- [ ] Rapports générés correctement
- [ ] Tests passent
```

## Fichiers à modifier
- `scripts/validate_extraction_output.py`
- `scripts/analyze_extraction_quality.py`

## Fichiers à créer (optionnels)
- `scripts/export_to_json.py` (nouveau)
- `tests/test_validation_scripts.py` (nouveau)

## Tests de validation
```bash
# Valider les données
python scripts/validate_extraction_output.py

# Analyser la qualité
python scripts/analyze_extraction_quality.py

# Export JSON (si créé)
python scripts/export_to_json.py --output backup.json
```

---

# PHASE 6 : Nettoyage et Suppression des Fichiers JSON

## Objectif
Supprimer tous les fichiers JSON et le code associé, nettoyer le code archivé Supabase.

## Prompt pour Claude (Conversation 6)

```markdown
# PHASE 6 : Nettoyage et Suppression des Anciens Fichiers

Contexte : Tout le système utilise maintenant PostgreSQL. Je dois nettoyer les anciens fichiers JSON et le code obsolète.

Répertoire de travail : `/home/luffy/Github/extract_config`

## Tâche 1 : Supprimer les fichiers JSON de données

Supprime ces fichiers :
```bash
rm -f data/input/top_200_mcp_servers.json
rm -f data/output/github_crawled_data.json
rm -f data/output/extracted_configs.json
```

⚠️ **ATTENTION** : Avant de supprimer, faire un backup si des données importantes existent :
```bash
mkdir -p backups
cp data/output/*.json backups/
```

## Tâche 2 : Supprimer le code Supabase archivé

Supprime complètement :
```bash
rm -rf archive/
```

Contient `extract_mcp_servers.py` (code Supabase obsolète).

## Tâche 3 : Nettoyer les imports et références JSON

Cherche et supprime dans le code :
1. Imports de `json` non utilisés
2. Références à `config.input_file`, `config.output_file` (chemins JSON)
3. Fonctions `load_existing_*()` obsolètes

Fichiers à vérifier :
- `src/config.py` : Supprimer `input_file`, `output_file` des configs
- `run_crawler.py` : Supprimer imports JSON inutiles
- `run_extractor.py` : Supprimer imports JSON inutiles

## Tâche 4 : Mettre à jour .env

Dans `.env`, commenter ou supprimer :
```env
# Anciens chemins JSON (obsolètes)
# CRAWLER_INPUT_FILE=data/input/top_200_mcp_servers.json
# CRAWLER_OUTPUT_FILE=data/output/github_crawled_data.json
# EXTRACTOR_INPUT_FILE=data/output/github_crawled_data.json
# EXTRACTOR_OUTPUT_FILE=data/output/extracted_configs.json
```

## Tâche 5 : Nettoyer les répertoires vides

Supprime les répertoires vides :
```bash
# Seulement si vides
rmdir data/input/ 2>/dev/null || true
rmdir data/output/ 2>/dev/null || true
```

Ou conserve-les pour d'autres usages futurs.

## Tâche 6 : Mettre à jour .gitignore

Modifie `.gitignore` :
```
# Supprimer les lignes JSON obsolètes
# data/output/*.json  (si plus utilisé)

# Ajouter backups
backups/
```

## Critères de succès
- [ ] Fichiers JSON supprimés (avec backup)
- [ ] Dossier archive/ supprimé
- [ ] Imports JSON nettoyés
- [ ] .env mis à jour
- [ ] .gitignore mis à jour
- [ ] Aucune référence à des fichiers supprimés dans le code
```

## Fichiers à supprimer
- `data/input/top_200_mcp_servers.json`
- `data/output/github_crawled_data.json`
- `data/output/extracted_configs.json`
- `archive/extract_mcp_servers.py`
- `archive/README.md`

## Fichiers à modifier
- `.env` (nettoyer variables obsolètes)
- `.gitignore` (mettre à jour)
- `src/config.py` (supprimer file paths)

## Tests de validation
```bash
# Vérifier qu'aucun fichier JSON n'est référencé
grep -r "github_crawled_data.json" --include="*.py" .
grep -r "extracted_configs.json" --include="*.py" .
grep -r "top_200_mcp_servers.json" --include="*.py" .

# Devrait ne rien retourner (ou seulement commentaires/docs)
```

---

# PHASE 7 : Tests Complets et Documentation

## Objectif
Valider le système end-to-end et mettre à jour la documentation.

## Prompt pour Claude (Conversation 7)

```markdown
# PHASE 7 : Tests End-to-End et Documentation

Contexte : Le système complet est migré vers PostgreSQL. Je dois valider le pipeline end-to-end et mettre à jour la documentation.

Répertoire de travail : `/home/luffy/Github/extract_config`

## Tâche 1 : Créer un script de test end-to-end

Crée `tests/test_e2e_pipeline.py` qui :

```python
import pytest
from src.database.db_manager import DatabaseManager
from src.services.crawler_service import CrawlerService
from src.services.extractor_service import ExtractorService

@pytest.fixture
def clean_database():
    """Nettoie la DB avant chaque test"""
    db = DatabaseManager()
    # TRUNCATE toutes les tables
    yield db
    # Cleanup après test

def test_full_pipeline(clean_database):
    """Test du pipeline complet : crawl → extract → validate"""

    # 1. Préparer des serveurs de test
    test_servers = [
        {
            'slug': 'test-server-1',
            'name': 'test-server-1',
            'github_url': 'https://github.com/user/repo1',
            # ...
        }
    ]

    # 2. Exécuter le crawler
    crawler_service = CrawlerService(clean_database)
    for server in test_servers:
        result = crawler_service.process_server(server)
        assert result['status'] == 'success'

    # 3. Vérifier l'insertion
    servers = crawler_service.servers_repo.get_all_servers()
    assert len(servers) == len(test_servers)

    # 4. Exécuter l'extractor
    extractor_service = ExtractorService(clean_database)
    servers_to_process = extractor_service.get_servers_to_process()
    results = await extractor_service.process_batch(servers_to_process)

    # 5. Vérifier les configs
    for server in servers_to_process:
        config = extractor_service.configs_repo.get_config_by_server_id(server['id'])
        assert config is not None
        assert config['config_json']['command'] in ['npx', 'python', 'docker']

    # 6. Vérifier les status
    approved = extractor_service.servers_repo.get_all_servers(status='approved')
    assert len(approved) > 0
```

## Tâche 2 : Test du pipeline avec données réelles

Exécute le pipeline complet avec un petit ensemble de données :

```bash
# 1. Réinitialiser la base
python database/init_db.py

# 2. Créer un fichier de serveurs de test (5 serveurs)
cat > test_servers.json << EOF
{
  "servers": [
    {"github_url": "https://github.com/modelcontextprotocol/servers", "slug": "mcp-servers"},
    {"github_url": "https://github.com/blazickjp/mcp-simple-memory", "slug": "simple-memory"},
    {"github_url": "https://github.com/QuantGeekDev/coincap-mcp-server", "slug": "coincap"},
    {"github_url": "https://github.com/calclavia/mcp-obsidian", "slug": "obsidian"},
    {"github_url": "https://github.com/pierrebrunelle/mcp-server-fetch", "slug": "fetch"}
  ]
}
EOF

# 3. Exécuter le crawler (avec le nouveau système)
python run_crawler.py --limit 5

# 4. Vérifier les résultats
psql -h localhost -U postgres -d mydb -c "SELECT slug, name, github_stars, status FROM mcp_servers;"

# 5. Exécuter l'extractor
python run_extractor.py --limit 5

# 6. Vérifier les configs
psql -h localhost -U postgres -d mydb -c "SELECT s.slug, c.config_type, s.status FROM mcp_servers s LEFT JOIN mcp_configs c ON c.server_id = s.id;"

# 7. Valider
python scripts/validate_extraction_output.py

# 8. Analyser
python scripts/analyze_extraction_quality.py
```

## Tâche 3 : Mettre à jour README.md

Modifie `README.md` pour refléter la nouvelle architecture :

```markdown
# Extracteur de Configurations MCP

Pipeline Python automatisé pour extraire les configurations de démarrage des serveurs MCP depuis GitHub.

## Architecture

**Base de données** : PostgreSQL locale
- Host: localhost:5432
- Database: mydb

**Tables** :
- `mcp_servers` : Serveurs MCP avec métadonnées GitHub
- `mcp_configs` : Configurations d'installation (JSONB)
- `mcp_content` : Contenu (README, documentation)
- `mcp_categories` : Catégories (référentiel)
- `mcp_tags` : Tags (référentiel)

## Installation

1. Installer PostgreSQL et démarrer le service

2. Installer les dépendances Python :
```bash
pip install -r requirements.txt
```

3. Configurer `.env` :
```bash
cp .env.example .env
# Éditer avec vos credentials
```

4. Initialiser la base de données :
```bash
python database/init_db.py
```

## Utilisation

### Pipeline complet
```bash
# Crawler + Extraction
python extract.py pipeline --limit 10
```

### Phases individuelles
```bash
# Phase 1: Crawler GitHub
python run_crawler.py --limit 10

# Phase 2: Extraction LLM
python run_extractor.py --limit 10

# Validation
python scripts/validate_extraction_output.py

# Analyse qualité
python scripts/analyze_extraction_quality.py
```

## Résultats

Les données sont stockées dans PostgreSQL :
- Serveurs crawlés : `mcp_servers` + `mcp_content`
- Configurations extraites : `mcp_configs`
- Statut de validation : `mcp_servers.status` (approved/pending/rejected)

## Structure du projet

```
.
├── database/
│   ├── schema.sql              # Schéma PostgreSQL
│   └── init_db.py              # Script d'initialisation
├── src/
│   ├── database/               # Couche d'accès aux données
│   │   ├── db_manager.py
│   │   └── repositories/
│   ├── services/               # Services métier
│   │   ├── crawler_service.py
│   │   └── extractor_service.py
│   ├── github_crawler.py       # Crawler GitHub
│   ├── llm_extractor.py        # Extraction LLM
│   └── llm_validator.py        # Validation LLM
├── tests/                      # Tests unitaires
└── scripts/                    # Scripts utilitaires
```

## Migration depuis JSON

Si vous aviez l'ancien système JSON, consultez `MIGRATION.md`.
```

## Tâche 4 : Créer MIGRATION.md

Crée un document `MIGRATION.md` qui explique :
- Pourquoi la migration vers PostgreSQL
- Différences entre ancien et nouveau système
- Comment exporter/importer des données si besoin

## Tâche 5 : Mettre à jour requirements.txt

Vérifie que `requirements.txt` contient :
```
# Existing
anthropic==0.40.0
openai==1.59.5
python-dotenv==1.0.1
PyGithub==2.5.0
structlog==24.4.0

# New
psycopg2-binary==2.9.9
pytest==7.4.3
pytest-asyncio==0.23.5
```

## Critères de succès
- [ ] Tests e2e créés et passent
- [ ] Pipeline testé avec données réelles (5 serveurs)
- [ ] Toutes les données en DB
- [ ] README.md mis à jour
- [ ] MIGRATION.md créé
- [ ] requirements.txt à jour
- [ ] Tous les tests unitaires passent
```

## Fichiers à créer
- `tests/test_e2e_pipeline.py` (nouveau)
- `MIGRATION.md` (nouveau)

## Fichiers à modifier
- `README.md` (refonte complète)
- `requirements.txt` (ajouter psycopg2, pytest)

## Tests de validation finale
```bash
# Exécuter tous les tests
pytest tests/ -v

# Pipeline complet sur 5 serveurs
python extract.py pipeline --limit 5

# Vérifier la base de données
psql -h localhost -U postgres -d mydb -c "\dt"
psql -h localhost -U postgres -d mydb -c "SELECT COUNT(*) FROM mcp_servers;"
psql -h localhost -U postgres -d mydb -c "SELECT COUNT(*) FROM mcp_configs;"
psql -h localhost -U postgres -d mydb -c "SELECT COUNT(*) FROM mcp_content;"
```

---

# 📋 Récapitulatif des Phases

| Phase | Objectif | Fichiers Créés | Fichiers Modifiés | Tests |
|-------|----------|---------------|-------------------|-------|
| **1** | Schéma DB | schema.sql, init_db.py | .env | Connexion DB |
| **2** | Data Access Layer | db_manager.py, 5 repositories | - | Tests unitaires repos |
| **3** | Crawler → DB | crawler_service.py | run_crawler.py | Tests crawler service |
| **4** | Extractor → DB | extractor_service.py | run_extractor.py | Tests extractor service |
| **5** | Scripts validation | - | validate*.py, analyze*.py | Tests scripts |
| **6** | Nettoyage | - | .env, .gitignore, config.py | Grep recherche JSON |
| **7** | Tests E2E | test_e2e_pipeline.py, MIGRATION.md | README.md | Pipeline complet |

---

# 🚀 Ordre d'Exécution Recommandé

```
1. Phase 1 → Initialiser la base de données
2. Phase 2 → Créer la couche de données
3. Phase 3 → Migrer le crawler
   ├─ Tester avec --limit 5
   └─ Vérifier dans pgAdmin/psql
4. Phase 4 → Migrer l'extractor
   ├─ Tester avec --limit 5
   └─ Vérifier les configs
5. Phase 5 → Migrer les scripts
6. Phase 6 → Nettoyer (après validation complète)
7. Phase 7 → Tests finaux et documentation
```

---

# ⚠️ Points d'Attention

## Gestion des Transactions
- Utiliser des transactions par serveur (commit individuel)
- Rollback en cas d'erreur sans bloquer le pipeline
- Logs détaillés pour debugging

## Performance
- Index sur colonnes recherchées (github_url, slug, status)
- GIN index sur JSONB (config_json)
- Pool de connexions (max 10)

## Réversibilité
- Backup de la DB avant chaque phase : `pg_dump mydb > backup_phaseX.sql`
- Conservation temporaire des JSON jusqu'à Phase 7
- Script d'export JSON si besoin de rollback

## Déduplication
- Actuellement : Set d'URLs en mémoire
- PostgreSQL : Contrainte UNIQUE sur github_url
- Vérifier existence avant insert

## Erreurs Courantes
1. **Foreign key violation** : Vérifier que server_id existe avant insert config
2. **JSON parse error** : Valider JSONB avant insertion
3. **Connection pool exhausted** : Augmenter max_size ou fermer les connexions
4. **Unique constraint violation** : Utiliser INSERT ... ON CONFLICT DO UPDATE

---

# 📊 Métriques de Succès

À la fin de la migration, vous devriez avoir :
- ✅ 0 fichier JSON dans data/
- ✅ Toutes les données dans PostgreSQL
- ✅ Pipeline fonctionnel (crawl + extract)
- ✅ Tests passent (unitaires + e2e)
- ✅ Documentation à jour
- ✅ Aucune référence à des fichiers JSON supprimés

---

# 🔧 Commandes Utiles PostgreSQL

```sql
-- Voir toutes les tables
\dt

-- Compter les enregistrements
SELECT
    'mcp_servers' as table_name, COUNT(*) as count FROM mcp_servers
UNION ALL
SELECT 'mcp_configs', COUNT(*) FROM mcp_configs
UNION ALL
SELECT 'mcp_content', COUNT(*) FROM mcp_content;

-- Top 10 serveurs par stars
SELECT slug, name, github_stars, status
FROM mcp_servers
ORDER BY github_stars DESC
LIMIT 10;

-- Distribution des status
SELECT status, COUNT(*)
FROM mcp_servers
GROUP BY status;

-- Serveurs sans config
SELECT s.slug, s.name
FROM mcp_servers s
LEFT JOIN mcp_configs c ON c.server_id = s.id
WHERE c.id IS NULL;

-- Taille de la base
SELECT pg_size_pretty(pg_database_size('mydb'));
```

---

# 📝 Notes Finales

Ce plan de migration est conçu pour être **exécuté progressivement** sur plusieurs sessions de travail. Chaque phase est **indépendante** et peut être testée individuellement.

**Durée estimée** :
- Phase 1 : 30 min
- Phase 2 : 1-2 heures
- Phase 3 : 2-3 heures
- Phase 4 : 2-3 heures
- Phase 5 : 1 heure
- Phase 6 : 30 min
- Phase 7 : 1-2 heures

**Total : 8-12 heures** de développement (peut être réparti sur plusieurs jours)

Bonne chance avec la migration ! 🎯
