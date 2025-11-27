# Plan d’Extraction des Configurations MCP depuis GitHub

## 📋 Contexte du Projet

> **Note importante** : Ce plan utilise une approche **minimaliste et pragmatique**.
>
> - **3-6 fichiers maximum** extraits par repo (pas 15+)
> - **1 seul appel LLM** par extraction (pas de multi-agent)
> - **Architecture simple** : GitHub Crawler → LLM → Validator → Storage
> - **Fiabilité cible** : 85%+ (suffisant pour Phase 1)

### Objectif

Extraire automatiquement les configurations de démarrage et variables d’environnement de 10,000+ serveurs MCP hébergés sur GitHub pour alimenter la plateforme **MCP Hub**.

### Vision MCP Hub

- **Positionnement** : “Le Stripe des intégrations MCP” / “Le Hugging Face de l’écosystème MCP”
- **Modèle** : Plateforme hybride cloud/self-hosted pour serveurs Model Context Protocol
- **USP** : Auto-démarrage automatique des serveurs MCP - l’utilisateur ne fait que remplir les variables d’environnement

### Contrainte principale

L’utilisateur final ne doit avoir qu’à **remplir les variables d’environnement** pour que le serveur MCP se lance automatiquement sur MCP Hub.

-----

## 🎯 Objectifs de l’Extraction

### Ce qu’on extrait

1. **Commande de démarrage** : La commande exacte pour lancer le serveur MCP
1. **Arguments** : Les arguments de la commande
1. **Variables d’environnement** : Liste complète avec métadonnées (required, description, example, default)
1. **Commande d’installation** : Si nécessaire (pip install, docker pull, etc.)

### Ce qu’on N’extrait PAS (pour l’instant)

- Tools/Resources/Prompts exposés (découvert au runtime)
- Métriques de performance (RAM, CPU, temps de démarrage)
- Dépendances système (PostgreSQL, Redis, etc.)
- Configuration d’orchestration

*Ces éléments seront ajoutés dans une Phase 2 après le premier lancement du serveur.*

-----

## 📊 Format JSON de Configuration Cible

### Format Standard Unifié

```json
{
  "name": "server-name",
  "install": "commande d'installation complète" | null,
  "command": "commande de démarrage",
  "args": ["arg1", "arg2"],
  "env": {
    "VAR_NAME": {
      "required": true | false,
      "description": "Description claire de la variable",
      "default": "valeur par défaut" | null,
      "example": "exemple de valeur valide",
      "where_to_get": "URL où obtenir la clé" | null,
      "validation_regex": "^pattern$" | null
    }
  }
}
```

### Exemples par Type d’Installation

#### NPX (le plus courant)

```json
{
  "name": "filesystem-server",
  "install": null,
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"],
  "env": {}
}
```

#### NPM Global

```json
{
  "name": "custom-server",
  "install": "npm install -g @example/mcp-server",
  "command": "mcp-server",
  "args": ["--port", "3000"],
  "env": {
    "API_KEY": {
      "required": true,
      "description": "API key for external service",
      "default": null,
      "example": "sk-proj-xxx..."
    }
  }
}
```

#### Docker

```json
{
  "name": "postgres-mcp",
  "install": "docker pull mcp/postgres:latest",
  "command": "docker",
  "args": [
    "run",
    "--rm",
    "-i",
    "mcp/postgres:latest"
  ],
  "env": {
    "DATABASE_URL": {
      "required": true,
      "description": "PostgreSQL connection string",
      "default": null,
      "example": "postgresql://user:pass@localhost:5432/db"
    }
  }
}
```

#### Python/Pip

```json
{
  "name": "slack-server",
  "install": "pip install mcp-server-slack",
  "command": "python",
  "args": ["-m", "mcp_server_slack"],
  "env": {
    "SLACK_BOT_TOKEN": {
      "required": true,
      "description": "Slack Bot User OAuth Token",
      "default": null,
      "example": "xoxb-xxx...",
      "where_to_get": "https://api.slack.com/apps"
    },
    "SLACK_TEAM_ID": {
      "required": true,
      "description": "Slack workspace ID",
      "default": null,
      "example": "T01234567"
    }
  }
}
```

#### UV (Python moderne)

```json
{
  "name": "slack-server-uv",
  "install": "uv pip install mcp-server-slack",
  "command": "uvx",
  "args": ["mcp-server-slack"],
  "env": {
    "SLACK_BOT_TOKEN": {
      "required": true,
      "description": "Slack Bot Token",
      "default": null,
      "example": "xoxb-xxx..."
    }
  }
}
```

#### Build from Source

```json
{
  "name": "custom-build-server",
  "install": "git clone https://github.com/user/server && cd server && npm install && npm run build",
  "command": "node",
  "args": ["dist/index.js"],
  "env": {
    "API_KEY": {
      "required": true,
      "description": "API key",
      "default": null,
      "example": "key_xxx"
    }
  }
}
```

#### Cargo (Rust)

```json
{
  "name": "rust-mcp-server",
  "install": "cargo install mcp-server-rust",
  "command": "mcp-server-rust",
  "args": [],
  "env": {}
}
```

#### Go

```json
{
  "name": "go-mcp-server",
  "install": "go install github.com/user/mcp-server@latest",
  "command": "mcp-server",
  "args": [],
  "env": {}
}
```

-----

## 📂 Fichiers à Extraire de GitHub

### Stratégie Minimaliste : 3-6 fichiers maximum

#### Toujours Récupérer (3 fichiers de base)

1. **README.md** (1 seul fichier)
- Priorité : `README.md` > `README.rst` > `README.txt`
- Prendre le premier qui existe, ignorer les autres
1. **Fichier de build** (1 seul selon langage)
- Si langage = `JavaScript/TypeScript` : `package.json`
- Si langage = `Python` : `pyproject.toml`
- Si langage = `Rust` : `Cargo.toml`
- Si langage = `Go` : `go.mod`
- Détecter le langage via `repo.language` (métadonnée GitHub)
1. **Variables d’environnement** (1 seul fichier)
- Priorité : `.env.example` > `.env.template` > `.env.sample`
- Prendre le premier qui existe

#### Optionnel si Insuffisant (2-3 fichiers additionnels)

1. **Dockerfile** (si existe)
- Seulement si les 3 premiers ne donnent pas assez d’infos
- Révèle souvent la vraie commande de production
1. **docker-compose.yml** (si existe)
- Alternative à Dockerfile
- Priorité : `docker-compose.yml` > `docker-compose.yaml`
1. **Makefile** (dernier recours)
- Seulement si vraiment nécessaire
- Révèle les commandes de build/run

### Logique de Récupération

```python
def get_files_to_fetch(repo_language: str) -> List[str]:
    """Retourne la liste minimale de fichiers à récupérer"""

    files = []

    # 1. README (toujours)
    files.append("README.md")  # Essayer aussi .rst, .txt si 404

    # 2. Fichier de build (selon langage)
    build_files = {
        "JavaScript": "package.json",
        "TypeScript": "package.json",
        "Python": "pyproject.toml",
        "Rust": "Cargo.toml",
        "Go": "go.mod"
    }
    if repo_language in build_files:
        files.append(build_files[repo_language])

    # 3. Env vars (toujours essayer)
    files.append(".env.example")

    # 4-6. Optionnels (récupérer si disponibles)
    files.extend(["Dockerfile", "docker-compose.yml", "Makefile"])

    return files
```

**Total : 3 fichiers minimum, 6 fichiers maximum**

### Métadonnées GitHub à Récupérer

Récupérées via l’API (pas de fichiers) :

- `repo.name`
- `repo.description`
- `repo.language` ← **Important pour détecter quel fichier de build chercher**
- `repo.topics` (tags comme “mcp-server”, “ai”)
- `repo.stars` (indicateur de qualité)
- `repo.updated_at` (fraîcheur)

-----

## 🔄 Pipeline d’Extraction

### Phase 1 : Collecte des Données

#### Input : Base de données de liens GitHub

Format de la base de données source :

```json
{
  "metadata": {
    "extraction_date": "2025-11-26T19:17:13.392184+00:00",
    "total_servers": 200,
    "description": "Top 200 MCP servers by GitHub stars (deduplicated by repository)"
  },
  "servers": [
    {
      "slug": "postgres",
      "name": "Postgres",
      "display_name": "modelcontextprotocol/servers",
      "tagline": "Model Context Protocol Servers",
      "short_description": "Model Context Protocol Servers",
      "github_url": "https://github.com/modelcontextprotocol/servers",
      "github_stars": 73162,
      "github_forks": 8844,
      "github_owner": "modelcontextprotocol",
      "github_repo": "servers"
    },
    {
      "slug": "context7",
      "name": "Context7",
      "display_name": "upstash/context7",
      "tagline": "Context7 MCP Server -- Up-to-date code documentation for LLMs and AI code editors",
      "short_description": "Context7 MCP Server -- Up-to-date code documentation for LLMs and AI code editors",
      "github_url": "https://github.com/upstash/context7",
      "github_stars": 37752,
      "github_forks": 1873,
      "github_owner": "upstash",
      "github_repo": "context7"
    }
}

```

#### Étape 1.1 : Crawler GitHub

**Technologie** : GitHub REST API ou GraphQL API

**Code pseudo** :

```python
def get_files_to_fetch(repo_language: str) -> List[str]:
    """Retourne 3-6 fichiers à récupérer selon le langage"""
    files = []

    # 1. README (essayer dans l'ordre)
    files.extend(["README.md", "README.rst", "README.txt"])

    # 2. Fichier de build (1 seul selon langage)
    build_mapping = {
        "JavaScript": "package.json",
        "TypeScript": "package.json",
        "Python": "pyproject.toml",
        "Rust": "Cargo.toml",
        "Go": "go.mod"
    }
    if repo_language in build_mapping:
        files.append(build_mapping[repo_language])

    # 3. Env vars (essayer dans l'ordre)
    files.extend([".env.example", ".env.template"])

    # 4-6. Optionnels
    files.extend(["Dockerfile", "docker-compose.yml", "Makefile"])

    return files

for server in database.get_pending_servers():
    repo_url = server.github_url

    # Extraire owner/repo depuis URL
    owner, repo_name = parse_github_url(repo_url)

    # Récupérer métadonnées
    metadata = github_api.get_repo(owner, repo_name)

    # Récupérer fichiers (3-6 max)
    files_to_fetch = get_files_to_fetch(metadata["language"])
    files = {}

    for file_path in files_to_fetch:
        try:
            content = github_api.get_file_content(owner, repo_name, file_path)
            files[file_path] = content

            # Si README trouvé, ne pas essayer les autres variantes
            if "README" in file_path and content:
                break

        except FileNotFoundError:
            continue

    # Stocker temporairement
    extraction_jobs.create({
        "server_id": server.id,
        "metadata": metadata,
        "files": files
    })
```

**Fichiers récupérés réellement** : 3 minimum (README + build file + .env), 6 maximum

### Phase 2 : Extraction via LLM

#### Configuration LLM

- **Modèle** : Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- **Max tokens** : 4000 output tokens
- **Temperature** : 0 (déterministe)
- **Timeout** : 30 secondes

#### Prompt d’Extraction Complet

```
Tu analyses un serveur MCP hébergé sur GitHub pour extraire sa configuration de démarrage.

# MÉTADONNÉES DU REPOSITORY
Nom: {metadata.name}
Description: {metadata.description}
Topics: {metadata.topics}
Langage principal: {metadata.language}
Homepage: {metadata.homepage}

# FICHIERS DISPONIBLES

Note : Tu recevras entre 3 et 6 fichiers selon leur disponibilité dans le repo.
Les fichiers ci-dessous sont ceux qui ont été récupérés avec succès.

{files_content}

---

# OBJECTIF
Extraire la configuration de démarrage du serveur MCP dans un format JSON structuré.

# FORMAT DE SORTIE ATTENDU
{{
  "name": "nom-du-serveur",
  "install": "commande d'installation complète" ou null,
  "command": "commande de démarrage",
  "args": ["arg1", "arg2"],
  "env": {{
    "VAR_NAME": {{
      "required": true ou false,
      "description": "description claire",
      "default": "valeur par défaut" ou null,
      "example": "exemple de valeur",
      "where_to_get": "URL où obtenir la clé" ou null,
      "validation_regex": "regex de validation" ou null
    }}
  }}
}}

# RÈGLES D'EXTRACTION

## 1. Détermination du Type d'Installation

Analyse dans cet ordre :

**Docker** :
- Si Dockerfile ou docker-compose.yml existe
- Si README mentionne "docker run" ou "docker-compose"
- Format : command="docker", args=["run", "--rm", "-i", "image:tag"]

**NPM/NPX** :
- Si package.json existe
- Si package.json contient un champ "bin"
- Si le package est dans l'organisation @modelcontextprotocol
- Format NPX : command="npx", args=["-y", "@org/package"]
- Format NPM : install="npm install -g package", command="package-name"

**Python/Pip** :
- Si pyproject.toml ou requirements.txt existe
- Si pyproject.toml contient [project.scripts]
- Format : install="pip install package", command="python", args=["-m", "package_name"]

**UV (Python moderne)** :
- Si README mentionne "uvx" ou "uv pip"
- Format : install="uv pip install package", command="uvx", args=["package"]

**Cargo (Rust)** :
- Si Cargo.toml existe
- Format : install="cargo install package", command="package-name"

**Go** :
- Si go.mod existe
- Format : install="go install github.com/user/repo@latest", command="repo"

**Build from Source** :
- Si aucune méthode packagée n'existe
- Extraire les étapes de build du README
- Format : install="git clone && cd && build steps", command="./binary ou node dist/index.js"

## 2. Hiérarchie de Priorité pour les Sources

**Ordre de confiance (du plus fiable au moins fiable)** :

1. **Dockerfile CMD/ENTRYPOINT** → Vérité absolue
   - La commande exacte qui lance le serveur en production
   - Les ENV définissent les variables obligatoires

2. **docker-compose.yml** → Très fiable
   - Section "command" révèle la vraie commande
   - Section "environment" liste toutes les variables

3. **package.json (Node.js)** → Structure exacte
   - Champ "bin" → nom de la commande installée
   - Scripts "start" → comment lancer
   - Si @modelcontextprotocol/* → toujours utiliser npx -y

4. **pyproject.toml (Python)** → Entry point exact
   - [project.scripts] → nom de la commande
   - [tool.poetry.scripts] → idem pour Poetry

5. **.env.example** → Variables d'environnement réelles
   - Liste exhaustive des variables
   - Exemples de valeurs
   - Commentaires explicatifs

6. **README.md** → Contexte général
   - Instructions d'installation
   - Exemples d'utilisation
   - Mais souvent incomplet ou obsolète

## 3. Règles Spécifiques par Type

### NPX/NPM
- Si le package est @modelcontextprotocol/*, toujours : `command="npx", args=["-y", "package-name"]`
- Ne pas ajouter d'install pour NPX (null)
- Args supplémentaires depuis README (ex: chemins, --port, etc.)

### Docker
- args doit TOUJOURS commencer par : ["run", "--rm", "-i"]
- `--rm` : supprime le container après arrêt
- `-i` : mode interactif pour stdio
- NE PAS inclure `-e VAR=value` dans args (MCP Hub l'injectera automatiquement)
- Juste mettre le nom de l'image en dernier arg

### Python
- Si [project.scripts] existe, utiliser ce nom exactement
- Convertir dashes en underscores pour module name (ex: mcp-server → mcp_server)
- Si UV détecté : command="uvx" est plus moderne que python -m

### Variables d'Environnement
- `required=true` UNIQUEMENT si le serveur crash au démarrage sans cette variable
- `required=false` pour variables optionnelles avec comportement par défaut
- Extraire description depuis commentaires dans .env.example
- `where_to_get` : URL vers documentation d'API externe (ex: https://platform.openai.com/api-keys)

## 4. Gestion des Cas Ambigus

Si plusieurs méthodes d'installation existent (ex: NPM + Docker) :
- Choisir la plus simple : NPX > Docker > Pip > Build
- Mentionner l'alternative dans un champ "notes" si nécessaire

Si information manquante ou contradictoire :
- Ajouter un champ `"confidence": 0.0-1.0` au JSON
- Ajouter un champ `"warnings": ["warning1", "warning2"]`
- Si vraiment impossible : `{{"error": "raison", "requires_manual_review": true}}`

## 5. Cas Spéciaux

**SSE/WebSocket (serveurs HTTP)** :
- Si le serveur expose un endpoint HTTP (/sse ou websocket)
- Ajouter `"transport": "sse"` ou `"transport": "websocket"`
- La commande doit démarrer un serveur web
- Exemple : command="node", args=["server.js", "--port", "3000"]

**Arguments dynamiques** :
- Utiliser ${VAR_NAME} dans args pour indiquer injection de variable
- Exemple : args=["--api-key", "${API_KEY}"]

# EXEMPLES DE SORTIES ATTENDUES

## Exemple 1 : Serveur NPX simple
{{
  "name": "filesystem",
  "install": null,
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"],
  "env": {{}}
}}

## Exemple 2 : Serveur Docker avec env vars
{{
  "name": "postgres-mcp",
  "install": "docker pull mcp/postgres:latest",
  "command": "docker",
  "args": ["run", "--rm", "-i", "mcp/postgres:latest"],
  "env": {{
    "DATABASE_URL": {{
      "required": true,
      "description": "PostgreSQL connection string",
      "default": null,
      "example": "postgresql://user:pass@localhost:5432/db",
      "where_to_get": null,
      "validation_regex": "^postgresql://.+$"
    }}
  }}
}}

## Exemple 3 : Python avec plusieurs env vars
{{
  "name": "slack-server",
  "install": "pip install mcp-server-slack",
  "command": "python",
  "args": ["-m", "mcp_server_slack"],
  "env": {{
    "SLACK_BOT_TOKEN": {{
      "required": true,
      "description": "Slack Bot User OAuth Token",
      "default": null,
      "example": "xoxb-xxx...",
      "where_to_get": "https://api.slack.com/apps"
    }},
    "SLACK_TEAM_ID": {{
      "required": true,
      "description": "Slack workspace ID",
      "default": null,
      "example": "T01234567"
    }},
    "LOG_LEVEL": {{
      "required": false,
      "description": "Logging verbosity",
      "default": "INFO",
      "example": "DEBUG"
    }}
  }}
}}

## Exemple 4 : Build from source
{{
  "name": "custom-server",
  "install": "git clone https://github.com/user/server && cd server && npm install && npm run build",
  "command": "node",
  "args": ["dist/index.js"],
  "env": {{
    "API_KEY": {{
      "required": true,
      "description": "API key for service",
      "default": null,
      "example": "sk-xxx..."
    }}
  }}
}}

## Exemple 5 : Extraction incertaine
{{
  "name": "unclear-server",
  "install": "npm install -g unclear-server",
  "command": "unclear-server",
  "args": [],
  "env": {{}},
  "confidence": 0.6,
  "warnings": [
    "README doesn't specify env vars clearly",
    "No .env.example file found",
    "Installation steps might be incomplete"
  ]
}}

## Exemple 6 : Échec d'extraction
{{
  "error": "Unable to determine installation method - no package manager files found",
  "requires_manual_review": true,
  "partial_info": {{
    "name": "unknown-server",
    "suspected_language": "python"
  }}
}}

# VALIDATION FINALE

Avant de retourner le JSON, vérifie :
- [ ] Tous les champs requis sont présents (name, command, args, env)
- [ ] command est une commande valide (npx, python, docker, node, uvx, etc.)
- [ ] args est un array (peut être vide)
- [ ] env est un object (peut être vide)
- [ ] Chaque env var a au minimum : required, description, example
- [ ] Si install présent, c'est une commande shell valide
- [ ] Pas de caractères spéciaux non échappés dans les strings
- [ ] Le JSON est valide et parseable

# FORMAT DE RÉPONSE

RETOURNE UNIQUEMENT LE JSON, AUCUN TEXTE AVANT OU APRÈS.
PAS DE MARKDOWN, PAS DE BACKTICKS, JUSTE LE JSON RAW.
```

#### Gestion des Erreurs LLM

```python
def build_prompt(files: Dict[str, str], metadata: Dict) -> str:
    """Construit le prompt avec les fichiers disponibles"""

    # Construire la section des fichiers dynamiquement
    files_content = ""
    for filename, content in files.items():
        if content:  # Seulement si le fichier a été récupéré
            files_content += f"\n## {filename}\n{content}\n"

    # Insérer dans le template de prompt
    prompt_template = load_prompt_template()  # Charge le prompt complet

    prompt = prompt_template.format(
        name=metadata["name"],
        description=metadata["description"],
        topics=metadata["topics"],
        language=metadata["language"],
        homepage=metadata["homepage"],
        files_content=files_content
    )

    return prompt

def extract_with_llm(files, metadata):
    prompt = build_prompt(files, metadata)

    try:
        response = anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        json_text = response.content[0].text.strip()

        # Nettoyer si markdown présent
        json_text = json_text.replace("```json", "").replace("```", "").strip()

        config = json.loads(json_text)

        return config

    except json.JSONDecodeError as e:
        return {
            "error": f"Invalid JSON from LLM: {e}",
            "requires_manual_review": true,
            "raw_response": json_text
        }
    except Exception as e:
        return {
            "error": f"LLM extraction failed: {e}",
            "requires_manual_review": true
        }
```

### Phase 3 : Validation des Extractions

#### Validator

```python
def validate_config(config):
    """Valide qu'une config est bien formée et complète"""

    validation = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "confidence": 1.0
    }

    # Vérifications obligatoires
    if "error" in config:
        validation["valid"] = False
        validation["errors"].append(f"Extraction failed: {config['error']}")
        return validation

    required_fields = ["name", "command", "args", "env"]
    for field in required_fields:
        if field not in config:
            validation["valid"] = False
            validation["errors"].append(f"Missing required field: {field}")

    if not validation["valid"]:
        return validation

    # Validation de command
    valid_commands = ["npx", "npm", "python", "python3", "uvx", "uv", "docker", "node", "deno", "bun", "cargo", "go"]
    if config["command"] not in valid_commands and not config["command"].startswith("./"):
        validation["warnings"].append(f"Unusual command: {config['command']}")
        validation["confidence"] *= 0.8

    # Validation de args
    if not isinstance(config["args"], list):
        validation["valid"] = False
        validation["errors"].append("args must be an array")

    # Validation Docker spécifique
    if config["command"] == "docker":
        if len(config["args"]) < 2 or config["args"][0] != "run":
            validation["warnings"].append("Docker command should start with 'run'")
            validation["confidence"] *= 0.9

        if "-i" not in config["args"] and "--interactive" not in config["args"]:
            validation["warnings"].append("Docker command missing -i flag for stdio")
            validation["confidence"] *= 0.9

    # Validation NPX spécifique
    if config["command"] == "npx":
        if len(config["args"]) < 2 or config["args"][0] != "-y":
            validation["warnings"].append("NPX should use -y flag")
            validation["confidence"] *= 0.95

    # Validation Python spécifique
    if config["command"] in ["python", "python3"]:
        if len(config["args"]) < 2 or config["args"][0] != "-m":
            validation["warnings"].append("Python command should use -m flag")
            validation["confidence"] *= 0.9

    # Validation des env vars
    for var_name, var_config in config.get("env", {}).items():
        if not isinstance(var_config, dict):
            validation["valid"] = False
            validation["errors"].append(f"Env var {var_name} must be an object")
            continue

        required_var_fields = ["required", "description", "example"]
        for field in required_var_fields:
            if field not in var_config:
                validation["warnings"].append(f"Env var {var_name} missing field: {field}")
                validation["confidence"] *= 0.95

    # Confidence depuis LLM
    if "confidence" in config:
        validation["confidence"] *= config["confidence"]

    # Warnings depuis LLM
    if "warnings" in config:
        validation["warnings"].extend(config["warnings"])

    return validation
```

#### Seuils de Qualité

```python
QUALITY_THRESHOLDS = {
    "auto_approve": 0.9,      # Approuvé automatiquement
    "needs_review": 0.7,       # Nécessite review humaine
    "reject": 0.5              # Rejeté, réessayer ou manual
}

def categorize_extraction(config, validation):
    confidence = validation["confidence"]

    if confidence >= QUALITY_THRESHOLDS["auto_approve"]:
        return "approved"
    elif confidence >= QUALITY_THRESHOLDS["needs_review"]:
        return "needs_review"
    else:
        return "rejected"
```

### Phase 4 : Agrégation & Stockage

#### Format de Sortie Final

Un seul fichier JSON contenant toutes les configurations :

```json
{
  "metadata": {
    "generated_at": "2024-01-15T14:30:00Z",
    "total_servers": 10247,
    "extraction_stats": {
      "approved": 8734,
      "needs_review": 1201,
      "rejected": 312
    },
    "version": "1.0.0"
  },
  "servers": [
    {
      "id": "uuid-1",
      "github_url": "https://github.com/user/repo",
      "github_metadata": {
        "name": "repo",
        "description": "An MCP server for...",
        "stars": 245,
        "language": "TypeScript",
        "topics": ["mcp", "ai"],
        "last_updated": "2024-01-10T09:00:00Z"
      },
      "config": {
        "name": "example-server",
        "install": null,
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-example"],
        "env": {
          "API_KEY": {
            "required": true,
            "description": "API key",
            "default": null,
            "example": "sk-xxx..."
          }
        }
      },
      "extraction": {
        "status": "approved",
        "confidence": 0.95,
        "warnings": [],
        "extracted_at": "2024-01-15T10:15:00Z",
        "files_analyzed": ["README.md", "package.json", ".env.example"]
      }
    },
    {
      "id": "uuid-2",
      "github_url": "https://github.com/org/another",
      "github_metadata": {...},
      "config": {...},
      "extraction": {
        "status": "needs_review",
        "confidence": 0.75,
        "warnings": ["No .env.example found", "Installation steps unclear"],
        "extracted_at": "2024-01-15T10:20:00Z",
        "files_analyzed": ["README.md", "pyproject.toml"]
      }
    },
    {
      "id": "uuid-3",
      "github_url": "https://github.com/user/broken",
      "github_metadata": {...},
      "error": "Unable to determine installation method",
      "extraction": {
        "status": "rejected",
        "confidence": 0.3,
        "extracted_at": "2024-01-15T10:25:00Z",
        "requires_manual_review": true
      }
    }
  ]
}
```

#### Base de Données Résultante

Table : `mcp_servers_configs`

```sql
CREATE TABLE mcp_servers_configs (
    id UUID PRIMARY KEY,
    github_url TEXT NOT NULL UNIQUE,

    -- GitHub metadata
    repo_name TEXT,
    repo_description TEXT,
    repo_stars INTEGER,
    repo_language TEXT,
    repo_topics JSONB,

    -- Configuration extraite
    config JSONB,  -- Le JSON de config

    -- Statut d'extraction
    extraction_status TEXT CHECK (extraction_status IN ('approved', 'needs_review', 'rejected')),
    extraction_confidence FLOAT,
    extraction_warnings JSONB,
    extraction_error TEXT,

    -- Métadonnées
    extracted_at TIMESTAMP,
    files_analyzed TEXT[],

    -- Index
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index pour recherche
CREATE INDEX idx_extraction_status ON mcp_servers_configs(extraction_status);
CREATE INDEX idx_repo_language ON mcp_servers_configs(repo_language);
CREATE INDEX idx_repo_stars ON mcp_servers_configs(repo_stars DESC);
```

-----

## 💻 Implémentation Technique

### Architecture du Script

```
mcp-extractor/
├── src/
│   ├── main.py                 # Point d'entrée
│   ├── github_crawler.py       # Récupération fichiers GitHub
│   ├── llm_extractor.py        # Extraction via Claude
│   ├── validator.py            # Validation des configs
│   ├── storage.py              # Stockage résultats
│   └── utils.py                # Helpers
├── config/
│   ├── prompt_template.txt     # Template du prompt
│   └── config.yaml             # Configuration
├── data/
│   ├── input_urls.json         # Liste des repos à extraire
│   └── output_configs.json     # Résultats
├── requirements.txt
└── README.md
```

### Stack Technique

- **Language** : Python 3.11+
- **GitHub API** : `PyGithub` ou `requests`
- **LLM** : Anthropic Python SDK
- **Database** : Supabase (PostgreSQL)
- **Rate Limiting** : `ratelimit` library
- **Logging** : `structlog`
- **Config** : `pydantic` + `pydantic-settings`

### Dépendances

```txt
anthropic>=0.18.0
PyGithub>=2.1.1
pydantic>=2.5.0
pydantic-settings>=2.1.0
supabase>=2.3.0
structlog>=24.1.0
ratelimit>=2.2.1
python-dotenv>=1.0.0
tenacity>=8.2.3
```

### Configuration

```yaml
# config.yaml
github:
  token: ${GITHUB_TOKEN}
  rate_limit:
    requests_per_hour: 4500  # Marge de sécurité sous 5000

anthropic:
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-sonnet-4-20250514
  max_tokens: 4000
  temperature: 0
  timeout_seconds: 30

extraction:
  batch_size: 100  # Nombre de repos à traiter en parallèle
  retry_attempts: 3
  retry_delay_seconds: 5

  # Fichiers à récupérer (3-6 maximum)
  files:
    always:  # Toujours essayer de récupérer (3 fichiers)
      - README.md
      - README.rst  # Fallback si .md n'existe pas
      - README.txt  # Fallback si .rst n'existe pas
      - .env.example
      - .env.template  # Fallback si .example n'existe pas
      # + 1 fichier de build selon repo.language

    optional:  # Seulement si les 3 premiers insuffisants
      - Dockerfile
      - docker-compose.yml
      - Makefile

  # Mapping langage → fichier de build
  build_files:
    JavaScript: package.json
    TypeScript: package.json
    Python: pyproject.toml
    Rust: Cargo.toml
    Go: go.mod

validation:
  thresholds:
    auto_approve: 0.9
    needs_review: 0.7
    reject: 0.5

storage:
  output_file: data/output_configs.json
  database:
    enabled: true
    supabase_url: ${SUPABASE_URL}
    supabase_key: ${SUPABASE_KEY}
```

### Code Principal

```python
# src/main.py

import asyncio
from typing import List, Dict
import structlog
from github_crawler import GitHubCrawler
from llm_extractor import LLMExtractor
from validator import ConfigValidator
from storage import Storage

logger = structlog.get_logger()

class MCPConfigExtractor:
    def __init__(self, config):
        self.config = config
        self.crawler = GitHubCrawler(config.github)
        self.extractor = LLMExtractor(config.anthropic)
        self.validator = ConfigValidator(config.validation)
        self.storage = Storage(config.storage)

    async def process_repo(self, repo_url: str) -> Dict:
        """Traite un seul repository"""

        logger.info("processing_repo", repo_url=repo_url)

        try:
            # 1. Récupérer fichiers GitHub
            repo_data = await self.crawler.fetch_repo_files(repo_url)

            # 2. Extraire config via LLM
            config = await self.extractor.extract_config(
                files=repo_data["files"],
                metadata=repo_data["metadata"]
            )

            # 3. Valider
            validation = self.validator.validate(config)

            # 4. Catégoriser
            status = self._categorize(validation)

            result = {
                "github_url": repo_url,
                "github_metadata": repo_data["metadata"],
                "config": config if status != "rejected" else None,
                "extraction": {
                    "status": status,
                    "confidence": validation["confidence"],
                    "warnings": validation["warnings"],
                    "extracted_at": datetime.utcnow().isoformat(),
                    "files_analyzed": list(repo_data["files"].keys())
                }
            }

            if "error" in config:
                result["error"] = config["error"]

            logger.info("repo_processed",
                       repo_url=repo_url,
                       status=status,
                       confidence=validation["confidence"])

            return result

        except Exception as e:
            logger.error("repo_processing_failed",
                        repo_url=repo_url,
                        error=str(e))

            return {
                "github_url": repo_url,
                "error": f"Processing failed: {str(e)}",
                "extraction": {
                    "status": "rejected",
                    "confidence": 0.0,
                    "requires_manual_review": True,
                    "extracted_at": datetime.utcnow().isoformat()
                }
            }

    async def process_batch(self, repo_urls: List[str]) -> List[Dict]:
        """Traite un batch de repos en parallèle"""

        tasks = [self.process_repo(url) for url in repo_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("batch_task_failed", error=str(result))
            else:
                valid_results.append(result)

        return valid_results

    async def run(self, input_file: str):
        """Point d'entrée principal"""

        logger.info("extraction_started")

        # Charger liste de repos
        with open(input_file, 'r') as f:
            data = json.load(f)
            repo_urls = [server["github_url"] for server in data["mcp_servers"]]

        total = len(repo_urls)
        logger.info("total_repos", count=total)

        # Traiter par batches
        batch_size = self.config.extraction.batch_size
        all_results = []

        for i in range(0, total, batch_size):
            batch = repo_urls[i:i+batch_size]
            logger.info("processing_batch",
                       batch=i//batch_size + 1,
                       size=len(batch))

            results = await self.process_batch(batch)
            all_results.extend(results)

            # Sauvegarder progressivement
            await self.storage.save_batch(results)

            logger.info("batch_completed",
                       processed=len(all_results),
                       total=total,
                       progress=f"{len(all_results)/total*100:.1f}%")

        # Générer fichier final
        final_output = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "total_servers": total,
                "extraction_stats": self._compute_stats(all_results),
                "version": "1.0.0"
            },
            "servers": all_results
        }

        await self.storage.save_final(final_output)

        logger.info("extraction_completed", stats=final_output["metadata"]["extraction_stats"])

        return final_output

    def _categorize(self, validation):
        confidence = validation["confidence"]

        if confidence >= self.config.validation.thresholds.auto_approve:
            return "approved"
        elif confidence >= self.config.validation.thresholds.needs_review:
            return "needs_review"
        else:
            return "rejected"

    def _compute_stats(self, results):
        stats = {
            "approved": 0,
            "needs_review": 0,
            "rejected": 0
        }

        for result in results:
            status = result["extraction"]["status"]
            stats[status] += 1

        return stats


# Point d'entrée
if __name__ == "__main__":
    from config import load_config

    config = load_config("config/config.yaml")
    extractor = MCPConfigExtractor(config)

    asyncio.run(extractor.run("data/input_urls.json"))
```

-----

## 📊 Métriques & KPIs

### Objectifs de Performance

|Métrique                 |Cible                          |
|-------------------------|-------------------------------|
|Taux d’extraction réussie|≥ 85% (approved + needs_review)|
|Taux d’auto-approbation  |≥ 70%                          |
|Coût par extraction      |≤ $0.02                        |
|Temps par extraction     |≤ 10 secondes                  |
|Taux d’erreur LLM        |≤ 5%                           |

### Monitoring

```python
# Métriques à tracker
metrics = {
    "total_processed": 0,
    "approved": 0,
    "needs_review": 0,
    "rejected": 0,

    "by_language": {
        "TypeScript": {"total": 0, "approved": 0},
        "Python": {"total": 0, "approved": 0},
        # etc.
    },

    "by_install_method": {
        "npm": 0,
        "docker": 0,
        "pip": 0,
        # etc.
    },

    "average_confidence": 0.0,
    "total_cost": 0.0,
    "total_duration_seconds": 0.0
}
```

-----

## 🚀 Plan d’Exécution

### Phase 0 : Préparation (1 jour)

- [ ] Setup environnement Python
- [ ] Obtenir tokens API (GitHub, Anthropic)
- [ ] Configurer Supabase
- [ ] Préparer liste de repos test (100 repos)

### Phase 1 : Implémentation (3-5 jours)

- [ ] Implémenter GitHub crawler
- [ ] Implémenter LLM extractor avec prompt
- [ ] Implémenter validator
- [ ] Implémenter storage
- [ ] Tests unitaires

### Phase 2 : Test & Calibration (2 jours)

- [ ] Run sur 100 repos test
- [ ] Analyser résultats
- [ ] Ajuster prompt si nécessaire
- [ ] Ajuster seuils de validation
- [ ] Atteindre ≥85% de succès

### Phase 3 : Production (2-3 jours)

- [ ] Run sur 10,000 repos complets
- [ ] Monitoring en temps réel
- [ ] Gestion des erreurs
- [ ] Review manuelle des cas “needs_review”

### Phase 4 : Post-traitement (1 jour)

- [ ] Génération fichier JSON final
- [ ] Import dans Supabase
- [ ] Documentation des résultats
- [ ] Rapport de qualité

### Estimation Totale : 8-11 jours

-----

## 💰 Estimation des Coûts

### Coûts API

**GitHub API** : Gratuit (5000 req/h avec token)

**Claude Sonnet 4** :

- Input : $3 / 1M tokens
- Output : $15 / 1M tokens

**Par extraction** (estimation) :

- Input : ~5K tokens (fichiers) × $3/1M = $0.015
- Output : ~1K tokens (config JSON) × $15/1M = $0.015
- **Total par extraction** : ~$0.03

**Pour 10,000 repos** :

- Coût LLM : 10,000 × $0.03 = **$300**
- Avec retry (10% des cas) : $300 × 1.1 = **$330**

### Coûts Infrastructure

- Compute (VM Python) : $20/mois (suffisant)
- Supabase : Gratuit tier (500MB OK pour configs)
- Stockage JSON : Négligeable

**Total estimé : ~$350 pour extraction complète**

-----

## 🔍 Cas Limites & Gestion

### Repos sans documentation claire

- Confidence < 0.5
- Status : “rejected”
- Action : Manual review ou skip

### Repos multi-langages

- Détecter langage principal via GitHub metadata
- Si ambiguïté : extraire plusieurs configs (alternative_methods)

### Repos archived/deprecated

- Skip basé sur GitHub metadata
- Ou flag “archived”: true dans output

### Repos privés

- Skip (GitHub API retourne 404)

### Rate limiting

- GitHub : Backoff automatique
- Claude : Batch processing avec délais

### Timeout LLM

- Retry avec timeout augmenté
- Si échec 3× : status “rejected”

-----

## 📝 Outputs Attendus

### 1. Fichier JSON Principal

`data/mcp_configs_final.json` - Toutes les configurations

### 2. Fichiers par Statut

- `data/approved_configs.json` - Configs validées (≥90% confidence)
- `data/needs_review_configs.json` - Nécessitent review humaine
- `data/rejected_configs.json` - Échecs d’extraction

### 3. Rapport de Qualité

`reports/extraction_report.md` :

- Statistiques globales
- Répartition par langage
- Répartition par méthode d’installation
- Top erreurs rencontrées
- Recommendations

### 4. Base de Données Supabase

Table `mcp_servers_configs` peuplée et indexée

-----

## ✅ Critères de Succès

1. **≥ 85% d’extractions réussies** (approved + needs_review)
1. **≥ 70% d’auto-approbation** (approved)
1. **Coût total ≤ $400**
1. **Durée totale ≤ 48h**
1. **0 crash du script**
1. **Fichier JSON final valide et exploitable**

### Philosophie : Pragmatisme > Perfectionnisme

- **85% de fiabilité est suffisant** pour la Phase 1. Les 15% restants seront :
  - Flaggés pour review manuelle
  - Améliorés via feedback communautaire sur MCP Hub
  - Corrigés itérativement
- **3-6 fichiers suffisent** pour extraire l’essentiel. Ajouter plus de fichiers n’améliore pas significativement la précision mais augmente les coûts et la complexité.
- **Architecture simple (single-agent)** est préférable à un système multi-agent complexe. Si la fiabilité est < 85% après tests, on itère sur le prompt, pas sur l’architecture.

-----

## 🎯 Prochaines Étapes (Post-Extraction)

Une fois les configs extraites :

1. **Interface de review** pour cas “needs_review”
1. **Système de feedback** communautaire
1. **Tests d’exécution** réels des configs
1. **Métriques runtime** (RAM, CPU, temps de démarrage)
1. **Détection automatique** des tools/resources exposés
1. **Système de certification** (3 tiers)

-----

## 📚 Références

- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [Anthropic API Documentation](https://docs.anthropic.com)
- [GitHub REST API](https://docs.github.com/en/rest)
- [Claude Desktop Config Format](https://modelcontextprotocol.io/docs/tools/claude-desktop)

