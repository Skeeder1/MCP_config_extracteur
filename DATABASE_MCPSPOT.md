# 🗄️ MCPspot Database Schema v2.0 - Documentation Complète

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture Globale](#architecture-globale)
3. [Tables Détaillées](#tables-détaillées)
4. [Relations et Cardinalités](#relations-et-cardinalités)
5. [Exemples de Données](#exemples-de-données)
6. [Requêtes SQL Courantes](#requêtes-sql-courantes)
7. [Index et Optimisations](#index-et-optimisations)
8. [Règles de Validation](#règles-de-validation)

---

## Vue d'ensemble

### Informations Générales

| Propriété | Valeur |
|-----------|--------|
| **Version du Schema** | v2.0 (Décembre 2025) |
| **Base de Données** | PostgreSQL 17.6.1 (Supabase) |
| **Région** | eu-west-1 |
| **Nombre de Tables** | 5 tables |
| **Philosophie** | Minimaliste, Performant, Évolutif |

### Objectifs de Conception

- ✅ **Simplicité** : Réduction de 12 tables → 5 tables
- ✅ **Performance** : Moins de JOINs, colonnes essentielles seulement
- ✅ **Clarté** : Structure intuitive et facile à comprendre
- ✅ **Évolutivité** : Facile d'ajouter des colonnes sans refonte majeure
- ✅ **Pragmatisme** : GitHub intégré directement dans mcp_servers

### Statistiques Actuelles

| Table | Lignes | Taille Estimée |
|-------|--------|----------------|
| mcp_servers | 835 | ~200 KB |
| mcp_configs | 636 | ~150 KB |
| mcp_content | 835 | ~2 MB |
| mcp_categories | ~20 | ~5 KB |
| mcp_tags | ~50 | ~10 KB |
| **TOTAL** | **~2,376 lignes** | **~2.4 MB** |

---

## Architecture Globale

### Schéma Relationnel Complet

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DATABASE: mcpspot_v2                                  │
│                     PostgreSQL 17.6.1 (Supabase)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        │                             │                             │
┌───────▼────────┐            ┌───────▼────────┐          ┌────────▼───────┐
│                │            │                │          │                │
│  mcp_configs   │◄───────────│  mcp_servers   │─────────►│  mcp_content   │
│                │   1:1      │     (CORE)     │   1:N    │                │
│  - server_id   │            │                │          │  - server_id   │
│  - config_json │            │  - id (PK)     │          │  - content     │
│                │            │  - slug        │          │  - type        │
└────────────────┘            │  - name        │          └────────────────┘
                              │  - github_*    │
                              │  - categories  │──┐
                              │  - tags        │──┤
                              │                │  │
                              └────────┬───────┘  │
                                       │          │
                    ┌──────────────────┴─────┐    │
                    │                        │    │
                    │                        │    │
            ┌───────▼──────┐         ┌───────▼────▼───┐
            │              │         │                 │
            │ mcp_tags     │         │ mcp_categories  │
            │              │         │                 │
            │ - id (PK)    │         │ - id (PK)       │
            │ - slug       │         │ - slug          │
            │ - name       │         │ - name          │
            │ - color      │         │ - icon          │
            │              │         │ - color         │
            └──────────────┘         └─────────────────┘

═══════════════════════════════════════════════════════════════════════════════

LÉGENDE:
  ◄─────► = Foreign Key (1:1 ou 1:N)
  ──┐     = Array Reference (UUID[])
    └──►  = Référence via categories/tags arrays

═══════════════════════════════════════════════════════════════════════════════
```

### Diagramme des Relations

```
mcp_servers (1) ──────────── (1) mcp_configs
     │
     ├─────────────────────── (N) mcp_content
     │
     ├─────── categories[] ──► (N) mcp_categories
     │
     └─────── tags[] ─────────► (N) mcp_tags
```

### Types de Relations

| Relation | Type | Description |
|----------|------|-------------|
| `mcp_servers` → `mcp_configs` | 1:1 | Un serveur a UNE configuration |
| `mcp_servers` → `mcp_content` | 1:N | Un serveur a PLUSIEURS contenus (readme, about...) |
| `mcp_servers` → `mcp_categories` | N:M | Un serveur dans PLUSIEURS catégories via array |
| `mcp_servers` → `mcp_tags` | N:M | Un serveur a PLUSIEURS tags via array |

---

## Tables Détaillées

### 1️⃣ Table CORE: `mcp_servers`

**Rôle** : Point central du système - stocke toutes les informations essentielles sur chaque serveur MCP, y compris les métadonnées GitHub.

**Lignes** : 835

**Colonnes** : 24

#### Structure Complète

```sql
CREATE TABLE mcp_servers (
    -- 🔑 IDENTIFIANTS
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                TEXT UNIQUE NOT NULL,
    name                TEXT NOT NULL,
    display_name        TEXT NOT NULL,
    
    -- 📝 DESCRIPTION
    tagline             TEXT DEFAULT '',
    description         TEXT DEFAULT '',
    logo_url            TEXT,
    homepage_url        TEXT,
    
    -- 🔗 GITHUB (Informations essentielles)
    github_url          TEXT NOT NULL,
    github_owner        TEXT NOT NULL,
    github_repo         TEXT NOT NULL,
    github_stars        INTEGER DEFAULT 0,
    github_forks        INTEGER DEFAULT 0,
    github_last_commit  TIMESTAMPTZ,
    primary_language    TEXT,
    license             TEXT,
    
    -- 📊 STATISTIQUES
    install_count       INTEGER DEFAULT 0,
    favorite_count      INTEGER DEFAULT 0,
    tools_count         INTEGER DEFAULT 0,
    
    -- 🏷️ TAXONOMIE (Arrays PostgreSQL)
    categories          UUID[] DEFAULT '{}',
    tags                UUID[] DEFAULT '{}',
    
    -- ⚙️ MÉTADONNÉES
    status              TEXT DEFAULT 'approved' CHECK (status IN ('approved', 'pending', 'rejected')),
    creator_username    TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX idx_servers_slug ON mcp_servers(slug);
CREATE INDEX idx_servers_github_stars ON mcp_servers(github_stars DESC);
CREATE INDEX idx_servers_install_count ON mcp_servers(install_count DESC);
CREATE INDEX idx_servers_status ON mcp_servers(status);
CREATE INDEX idx_servers_categories ON mcp_servers USING GIN(categories);
CREATE INDEX idx_servers_tags ON mcp_servers USING GIN(tags);
```

#### Détail des Colonnes

| Colonne | Type | NULL | Default | Description | Exemple |
|---------|------|------|---------|-------------|---------|
| **IDENTIFIANTS** |
| `id` | UUID | NO | gen_random_uuid() | Identifiant unique | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `slug` | TEXT | NO | - | URL-friendly identifier (UNIQUE) | `brave-search` |
| `name` | TEXT | NO | - | Nom technique du serveur | `brave-search` |
| `display_name` | TEXT | NO | - | Nom d'affichage | `Brave Search MCP Server` |
| **DESCRIPTION** |
| `tagline` | TEXT | YES | `''` | Phrase d'accroche courte | `Search the web with Brave` |
| `description` | TEXT | YES | `''` | Description complète | `A Model Context Protocol server that enables...` |
| `logo_url` | TEXT | YES | NULL | URL du logo | `https://cdn.mcpspot.com/logos/brave.png` |
| `homepage_url` | TEXT | YES | NULL | Site web officiel | `https://brave.com` |
| **GITHUB** |
| `github_url` | TEXT | NO | - | URL complète du repo | `https://github.com/brave/brave-search-mcp` |
| `github_owner` | TEXT | NO | - | Propriétaire du repo | `brave` |
| `github_repo` | TEXT | NO | - | Nom du repository | `brave-search-mcp` |
| `github_stars` | INTEGER | NO | 0 | Nombre d'étoiles | `856` |
| `github_forks` | INTEGER | NO | 0 | Nombre de forks | `124` |
| `github_last_commit` | TIMESTAMPTZ | YES | NULL | Date du dernier commit | `2025-11-25 10:30:00+00` |
| `primary_language` | TEXT | YES | NULL | Langage principal | `TypeScript` |
| `license` | TEXT | YES | NULL | Type de licence | `MIT` |
| **STATISTIQUES** |
| `install_count` | INTEGER | NO | 0 | Nombre d'installations | `1247` |
| `favorite_count` | INTEGER | NO | 0 | Nombre de favoris | `89` |
| `tools_count` | INTEGER | NO | 0 | Nombre d'outils | `3` |
| **TAXONOMIE** |
| `categories` | UUID[] | NO | `{}` | IDs des catégories | `{uuid1, uuid2}` |
| `tags` | UUID[] | NO | `{}` | IDs des tags | `{uuid3, uuid4, uuid5}` |
| **MÉTADONNÉES** |
| `status` | TEXT | NO | `'approved'` | Statut de modération | `approved` / `pending` / `rejected` |
| `creator_username` | TEXT | YES | NULL | Créateur du serveur | `brave` |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Date de création | `2025-01-15 14:30:00+00` |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Dernière mise à jour | `2025-11-27 18:45:00+00` |

#### Contraintes

- `slug` doit suivre le pattern `^[a-z0-9-]+$`
- `status` doit être dans `['approved', 'pending', 'rejected']`
- `github_stars` >= 0
- `install_count` >= 0

---

### 2️⃣ Table CONFIG: `mcp_configs`

**Rôle** : Stocke la configuration d'installation (npm/docker) pour chaque serveur.

**Lignes** : 636

**Colonnes** : 6

#### Structure Complète

```sql
CREATE TABLE mcp_configs (
    -- 🔑 IDENTIFIANTS
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id       UUID UNIQUE NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    
    -- ⚙️ CONFIGURATION
    config_type     TEXT NOT NULL CHECK (config_type IN ('npm', 'docker', 'python', 'binary')),
    config_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- 📅 TIMESTAMPS
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX idx_configs_server_id ON mcp_configs(server_id);
CREATE INDEX idx_configs_type ON mcp_configs(config_type);
CREATE INDEX idx_configs_json ON mcp_configs USING GIN(config_json);
```

#### Détail des Colonnes

| Colonne | Type | NULL | Default | Description | Exemple |
|---------|------|------|---------|-------------|---------|
| `id` | UUID | NO | gen_random_uuid() | Identifiant unique | `b2c3d4e5-f6a7-8901-bcde-f12345678901` |
| `server_id` | UUID | NO | - | Référence à mcp_servers (UNIQUE) | `a1b2c3d4-...` |
| `config_type` | TEXT | NO | - | Type de déploiement | `npm` / `docker` / `python` / `binary` |
| `config_json` | JSONB | NO | `{}` | Configuration complète en JSON | Voir exemples ci-dessous |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Date de création | `2025-01-15 14:30:00+00` |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Dernière modification | `2025-11-27 18:45:00+00` |

#### Structure `config_json` - Type NPM

```json
{
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-brave-search"
  ],
  "env": {
    "BRAVE_API_KEY": {
      "required": true,
      "label": "Brave API Key",
      "type": "secret",
      "description": "Your Brave Search API key",
      "get_url": "https://brave.com/search/api",
      "example": "BSA..."
    }
  },
  "runtime": "node",
  "min_node_version": "18.0.0"
}
```

#### Structure `config_json` - Type Docker

```json
{
  "command": "docker",
  "args": [
    "run",
    "-it",
    "--rm",
    "postgres-mcp:latest"
  ],
  "image": "postgres-mcp",
  "tag": "latest",
  "ports": {
    "5432": "5432"
  },
  "volumes": {
    "/data": "/var/lib/postgresql/data"
  },
  "env": {
    "POSTGRES_PASSWORD": {
      "required": true,
      "label": "PostgreSQL Password",
      "type": "secret"
    },
    "POSTGRES_USER": {
      "required": false,
      "label": "PostgreSQL User",
      "type": "text",
      "default": "postgres"
    }
  },
  "network_mode": "bridge"
}
```

---

### 3️⃣ Table CONTENT: `mcp_content`

**Rôle** : Stocke le contenu textuel/documentation de chaque serveur (README, About, FAQ...).

**Lignes** : 835

**Colonnes** : 5

#### Structure Complète

```sql
CREATE TABLE mcp_content (
    -- 🔑 IDENTIFIANTS
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id       UUID NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    
    -- 📝 CONTENU
    content_type    TEXT NOT NULL CHECK (content_type IN ('readme', 'about', 'faq', 'changelog')),
    content         TEXT NOT NULL DEFAULT '',
    
    -- 📅 TIMESTAMP
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX idx_content_server_id ON mcp_content(server_id);
CREATE INDEX idx_content_type ON mcp_content(content_type);
CREATE INDEX idx_content_server_type ON mcp_content(server_id, content_type);
```

#### Détail des Colonnes

| Colonne | Type | NULL | Default | Description | Exemple |
|---------|------|------|---------|-------------|---------|
| `id` | UUID | NO | gen_random_uuid() | Identifiant unique | `e5f6a7b8-c9d0-1234-efab-345678901234` |
| `server_id` | UUID | NO | - | Référence à mcp_servers | `a1b2c3d4-...` |
| `content_type` | TEXT | NO | - | Type de contenu | `readme` / `about` / `faq` / `changelog` |
| `content` | TEXT | NO | `''` | Contenu markdown | `# Brave Search MCP Server\n\n## Installation...` |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Dernière modification | `2025-11-27 18:45:00+00` |

#### Types de Contenu

| Type | Description | Utilisation |
|------|-------------|-------------|
| `readme` | README complet du GitHub | Documentation d'installation et d'usage |
| `about` | Description détaillée | Présentation des fonctionnalités |
| `faq` | Questions fréquentes | Réponses aux questions communes |
| `changelog` | Historique des versions | Suivi des modifications |

---

### 4️⃣ Table RÉFÉRENTIEL: `mcp_categories`

**Rôle** : Référentiel des catégories pour organiser les serveurs.

**Lignes** : ~20

**Colonnes** : 5

#### Structure Complète

```sql
CREATE TABLE mcp_categories (
    -- 🔑 IDENTIFIANTS
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug    TEXT UNIQUE NOT NULL,
    
    -- 📝 INFORMATIONS
    name    TEXT NOT NULL,
    icon    TEXT,
    color   TEXT
);

-- Index
CREATE INDEX idx_categories_slug ON mcp_categories(slug);
```

#### Détail des Colonnes

| Colonne | Type | NULL | Default | Description | Exemple |
|---------|------|------|---------|-------------|---------|
| `id` | UUID | NO | gen_random_uuid() | Identifiant unique | `b8c9d0e1-f2a3-4567-bcde-678901234567` |
| `slug` | TEXT | NO | - | Identifiant URL (UNIQUE) | `data-analysis` |
| `name` | TEXT | NO | - | Nom d'affichage | `Data Analysis` |
| `icon` | TEXT | YES | NULL | Emoji ou URL d'icône | `📊` ou `chart-bar` |
| `color` | TEXT | YES | NULL | Couleur hexadécimale | `#3B82F6` |

#### Exemples de Catégories

| slug | name | icon | color |
|------|------|------|-------|
| `search-web` | Search & Web | 🔍 | `#10B981` |
| `data-analysis` | Data Analysis | 📊 | `#3B82F6` |
| `productivity` | Productivity | ⚡ | `#F59E0B` |
| `development` | Development | 💻 | `#8B5CF6` |
| `communication` | Communication | 💬 | `#EC4899` |
| `database` | Database | 🗄️ | `#06B6D4` |
| `ai-ml` | AI & Machine Learning | 🤖 | `#F43F5E` |

---

### 5️⃣ Table RÉFÉRENTIEL: `mcp_tags`

**Rôle** : Référentiel des tags pour étiqueter les serveurs.

**Lignes** : ~50

**Colonnes** : 4

#### Structure Complète

```sql
CREATE TABLE mcp_tags (
    -- 🔑 IDENTIFIANTS
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug    TEXT UNIQUE NOT NULL,
    
    -- 📝 INFORMATIONS
    name    TEXT NOT NULL,
    color   TEXT
);

-- Index
CREATE INDEX idx_tags_slug ON mcp_tags(slug);
```

#### Détail des Colonnes

| Colonne | Type | NULL | Default | Description | Exemple |
|---------|------|------|---------|-------------|---------|
| `id` | UUID | NO | gen_random_uuid() | Identifiant unique | `c9d0e1f2-a3b4-5678-cdef-789012345678` |
| `slug` | TEXT | NO | - | Identifiant URL (UNIQUE) | `api-integration` |
| `name` | TEXT | NO | - | Nom d'affichage | `API Integration` |
| `color` | TEXT | YES | NULL | Couleur hexadécimale | `#6366F1` |

#### Exemples de Tags

| slug | name | color |
|------|------|-------|
| `free` | Free | `#10B981` |
| `api-key-required` | API Key Required | `#EF4444` |
| `official` | Official | `#3B82F6` |
| `typescript` | TypeScript | `#3178C6` |
| `python` | Python | `#3776AB` |
| `docker` | Docker | `#2496ED` |
| `npm` | NPM | `#CB3837` |
| `realtime` | Real-time | `#F59E0B` |

---

## Relations et Cardinalités

### Table des Relations

| Relation | Type | Description | Implémentation |
|----------|------|-------------|----------------|
| `mcp_servers` → `mcp_configs` | 1:1 | Un serveur a UNE configuration | Foreign Key `server_id` UNIQUE |
| `mcp_servers` → `mcp_content` | 1:N | Un serveur a PLUSIEURS contenus | Foreign Key `server_id` |
| `mcp_servers` ↔ `mcp_categories` | N:M | Serveurs et catégories | Array `categories UUID[]` |
| `mcp_servers` ↔ `mcp_tags` | N:M | Serveurs et tags | Array `tags UUID[]` |

### Diagramme de Cardinalité

```
mcp_servers (1) ──────────────── (0..1) mcp_configs
     │                                    [UNIQUE constraint]
     │
     ├──────────────────────────── (0..N) mcp_content
     │                                    [Multiple rows per server]
     │
     ├─── categories[] ───────────► (0..N) mcp_categories
     │    [Array of UUIDs]                [Referenced by ID]
     │
     └─── tags[] ─────────────────► (0..N) mcp_tags
          [Array of UUIDs]                [Referenced by ID]
```

### Exemples de Relations

#### Un serveur avec plusieurs contenus (1:N)

```
brave-search (server_id: a1b2...)
    ├─ README   (content_type: readme)
    ├─ About    (content_type: about)
    └─ FAQ      (content_type: faq)
```

#### Un serveur avec catégories et tags (N:M via Arrays)

```
brave-search (server_id: a1b2...)
    ├─ categories: [cat-uuid-1, cat-uuid-2]
    │   └─ Correspond à: ["Search & Web", "Data Analysis"]
    │
    └─ tags: [tag-uuid-1, tag-uuid-2, tag-uuid-3]
        └─ Correspond à: ["free", "api-key-required", "typescript"]
```

---

## Exemples de Données

### Exemple Complet: Serveur "brave-search"

#### Table `mcp_servers`

```sql
INSERT INTO mcp_servers (
    id, slug, name, display_name, tagline, description,
    logo_url, homepage_url,
    github_url, github_owner, github_repo, github_stars, github_forks,
    github_last_commit, primary_language, license,
    install_count, favorite_count, tools_count,
    categories, tags,
    status, creator_username, created_at, updated_at
) VALUES (
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'brave-search',
    'brave-search',
    'Brave Search MCP Server',
    'Search the web with Brave',
    'A Model Context Protocol server that enables AI assistants to perform web searches using the Brave Search API.',
    'https://cdn.mcpspot.com/logos/brave.png',
    'https://brave.com',
    'https://github.com/brave/brave-search-mcp',
    'brave',
    'brave-search-mcp',
    856,
    124,
    '2025-11-25 10:30:00+00',
    'TypeScript',
    'MIT',
    1247,
    89,
    3,
    ARRAY['b8c9d0e1-f2a3-4567-bcde-678901234567'::uuid, 'f1e2d3c4-b5a6-7890-1234-567890abcdef'::uuid],
    ARRAY['c9d0e1f2-a3b4-5678-cdef-789012345678'::uuid, 'd0e1f2a3-b4c5-6789-0123-456789abcdef'::uuid],
    'approved',
    'brave',
    '2025-01-15 14:30:00+00',
    '2025-11-27 18:45:00+00'
);
```

#### Table `mcp_configs`

```sql
INSERT INTO mcp_configs (
    id, server_id, config_type, config_json, created_at, updated_at
) VALUES (
    'b2c3d4e5-f6a7-8901-bcde-f12345678901',
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'npm',
    '{
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {
            "BRAVE_API_KEY": {
                "required": true,
                "label": "Brave API Key",
                "type": "secret",
                "description": "Your Brave Search API key",
                "get_url": "https://brave.com/search/api",
                "example": "BSA..."
            }
        },
        "runtime": "node",
        "min_node_version": "18.0.0"
    }'::jsonb,
    '2025-01-15 14:30:00+00',
    '2025-11-27 18:45:00+00'
);
```

#### Table `mcp_content`

```sql
-- README
INSERT INTO mcp_content (
    id, server_id, content_type, content, updated_at
) VALUES (
    'e5f6a7b8-c9d0-1234-efab-345678901234',
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'readme',
    '# Brave Search MCP Server

## Installation

```bash
npm install @modelcontextprotocol/server-brave-search
```

## Configuration

Set your `BRAVE_API_KEY` environment variable...

## Usage

This server provides the following tools:
- `brave_search`: Search the web
- `brave_news`: Search for news articles
- `brave_images`: Search for images
',
    '2025-11-27 18:45:00+00'
);

-- About
INSERT INTO mcp_content (
    id, server_id, content_type, content, updated_at
) VALUES (
    'f6a7b8c9-d0e1-2345-fabc-456789012345',
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'about',
    'This server provides integration with Brave Search API, allowing AI assistants to perform web searches, news searches, and image searches. It respects user privacy and does not track searches.',
    '2025-11-27 18:45:00+00'
);
```

#### Tables Référentiels

```sql
-- Categories
INSERT INTO mcp_categories (id, slug, name, icon, color) VALUES
('b8c9d0e1-f2a3-4567-bcde-678901234567', 'search-web', 'Search & Web', '🔍', '#10B981'),
('f1e2d3c4-b5a6-7890-1234-567890abcdef', 'data-analysis', 'Data Analysis', '📊', '#3B82F6');

-- Tags
INSERT INTO mcp_tags (id, slug, name, color) VALUES
('c9d0e1f2-a3b4-5678-cdef-789012345678', 'free', 'Free', '#10B981'),
('d0e1f2a3-b4c5-6789-0123-456789abcdef', 'api-key-required', 'API Key Required', '#EF4444');
```

---

## Requêtes SQL Courantes

### 1. Récupérer un serveur complet avec toutes ses données

```sql
SELECT 
    s.*,
    cfg.config_json,
    json_agg(DISTINCT c.*) FILTER (WHERE c.id IS NOT NULL) as categories_full,
    json_agg(DISTINCT t.*) FILTER (WHERE t.id IS NOT NULL) as tags_full,
    json_agg(DISTINCT cnt.*) FILTER (WHERE cnt.id IS NOT NULL) as content_sections
FROM mcp_servers s
LEFT JOIN mcp_configs cfg ON cfg.server_id = s.id
LEFT JOIN mcp_categories c ON c.id = ANY(s.categories)
LEFT JOIN mcp_tags t ON t.id = ANY(s.tags)
LEFT JOIN mcp_content cnt ON cnt.server_id = s.id
WHERE s.slug = 'brave-search'
GROUP BY s.id, cfg.id;
```

### 2. Lister tous les serveurs approuvés avec leurs stats

```sql
SELECT 
    s.slug,
    s.display_name,
    s.tagline,
    s.github_stars,
    s.install_count,
    s.primary_language,
    array_length(s.categories, 1) as category_count,
    array_length(s.tags, 1) as tag_count
FROM mcp_servers s
WHERE s.status = 'approved'
ORDER BY s.github_stars DESC
LIMIT 20;
```

### 3. Chercher des serveurs par catégorie

```sql
SELECT 
    s.slug,
    s.display_name,
    s.github_stars,
    c.name as category_name
FROM mcp_servers s
JOIN mcp_categories c ON c.id = ANY(s.categories)
WHERE c.slug = 'data-analysis'
ORDER BY s.github_stars DESC;
```

### 4. Chercher des serveurs par tag

```sql
SELECT 
    s.slug,
    s.display_name,
    s.github_stars,
    array_agg(t.name) as all_tags
FROM mcp_servers s
JOIN mcp_tags t ON t.id = ANY(s.tags)
WHERE EXISTS (
    SELECT 1 
    FROM mcp_tags tag 
    WHERE tag.id = ANY(s.tags) 
    AND tag.slug = 'typescript'
)
GROUP BY s.id
ORDER BY s.github_stars DESC;
```

### 5. Compter les serveurs par catégorie

```sql
SELECT 
    c.name,
    c.slug,
    COUNT(*) as server_count
FROM mcp_categories c
JOIN mcp_servers s ON c.id = ANY(s.categories)
WHERE s.status = 'approved'
GROUP BY c.id, c.name, c.slug
ORDER BY server_count DESC;
```

### 6. Top serveurs par étoiles GitHub

```sql
SELECT 
    s.slug,
    s.display_name,
    s.github_url,
    s.github_stars,
    s.github_forks,
    s.primary_language,
    s.github_last_commit
FROM mcp_servers s
WHERE s.status = 'approved'
ORDER BY s.github_stars DESC
LIMIT 10;
```

### 7. Serveurs récemment mis à jour

```sql
SELECT 
    s.slug,
    s.display_name,
    s.github_last_commit,
    s.updated_at,
    s.github_stars
FROM mcp_servers s
WHERE s.status = 'approved'
  AND s.github_last_commit > NOW() - INTERVAL '7 days'
ORDER BY s.github_last_commit DESC;
```

### 8. Chercher dans le contenu README

```sql
SELECT 
    s.slug,
    s.display_name,
    cnt.content
FROM mcp_servers s
JOIN mcp_content cnt ON cnt.server_id = s.id
WHERE cnt.content_type = 'readme'
  AND cnt.content ILIKE '%search%'
ORDER BY s.github_stars DESC;
```

### 9. Récupérer la configuration d'un serveur

```sql
SELECT 
    s.slug,
    s.display_name,
    cfg.config_type,
    cfg.config_json
FROM mcp_servers s
JOIN mcp_configs cfg ON cfg.server_id = s.id
WHERE s.slug = 'brave-search';
```

### 10. Statistiques globales

```sql
SELECT 
    COUNT(*) as total_servers,
    SUM(install_count) as total_installs,
    AVG(github_stars) as avg_stars,
    COUNT(DISTINCT unnest(categories)) as total_categories,
    COUNT(DISTINCT unnest(tags)) as total_tags
FROM mcp_servers
WHERE status = 'approved';
```

---

## Index et Optimisations

### Index Créés

#### Table `mcp_servers`

```sql
-- Index uniques
CREATE UNIQUE INDEX idx_servers_slug ON mcp_servers(slug);

-- Index de performance
CREATE INDEX idx_servers_github_stars ON mcp_servers(github_stars DESC);
CREATE INDEX idx_servers_install_count ON mcp_servers(install_count DESC);
CREATE INDEX idx_servers_status ON mcp_servers(status);
CREATE INDEX idx_servers_updated_at ON mcp_servers(updated_at DESC);

-- Index GIN pour arrays
CREATE INDEX idx_servers_categories ON mcp_servers USING GIN(categories);
CREATE INDEX idx_servers_tags ON mcp_servers USING GIN(tags);

-- Index composite
CREATE INDEX idx_servers_status_stars ON mcp_servers(status, github_stars DESC);
```

#### Table `mcp_configs`

```sql
CREATE UNIQUE INDEX idx_configs_server_id ON mcp_configs(server_id);
CREATE INDEX idx_configs_type ON mcp_configs(config_type);
CREATE INDEX idx_configs_json ON mcp_configs USING GIN(config_json);
```

#### Table `mcp_content`

```sql
CREATE INDEX idx_content_server_id ON mcp_content(server_id);
CREATE INDEX idx_content_type ON mcp_content(content_type);
CREATE INDEX idx_content_server_type ON mcp_content(server_id, content_type);

-- Full-text search (optionnel)
CREATE INDEX idx_content_fulltext ON mcp_content USING GIN(to_tsvector('english', content));
```

#### Tables Référentiels

```sql
-- mcp_categories
CREATE UNIQUE INDEX idx_categories_slug ON mcp_categories(slug);

-- mcp_tags
CREATE UNIQUE INDEX idx_tags_slug ON mcp_tags(slug);
```

### Stratégies d'Optimisation

#### 1. Utilisation des Arrays PostgreSQL

Les relations N:M sont implémentées via des arrays UUID[] au lieu de tables de jonction :

**Avantages** :
- ✅ Pas de JOINs supplémentaires pour les associations simples
- ✅ Index GIN pour recherches rapides
- ✅ Moins de tables = architecture simplifiée

**Requête optimisée** :
```sql
-- Avec array (rapide)
SELECT * FROM mcp_servers WHERE '123-uuid'::uuid = ANY(categories);

-- Équivalent avec table de jonction (plus lent)
SELECT s.* FROM mcp_servers s 
JOIN mcp_server_categories sc ON sc.server_id = s.id 
WHERE sc.category_id = '123-uuid';
```

#### 2. JSONB pour configuration flexible

Utilisation de JSONB au lieu de colonnes multiples :

**Avantages** :
- ✅ Flexibilité : ajouter des champs sans ALTER TABLE
- ✅ Index GIN pour recherche dans le JSON
- ✅ Validation côté application

**Exemple de requête** :
```sql
-- Chercher dans le JSON
SELECT * FROM mcp_configs 
WHERE config_json->>'command' = 'npx';

-- Chercher dans un sous-objet
SELECT * FROM mcp_configs 
WHERE config_json->'env'->'BRAVE_API_KEY'->>'required' = 'true';
```

#### 3. Partitionnement (Future)

Pour scale au-delà de 10K+ serveurs :

```sql
-- Partitionner par status
CREATE TABLE mcp_servers_approved PARTITION OF mcp_servers 
FOR VALUES IN ('approved');

CREATE TABLE mcp_servers_pending PARTITION OF mcp_servers 
FOR VALUES IN ('pending');
```

---

## Règles de Validation

### Contraintes de Base de Données

#### Table `mcp_servers`

```sql
-- Slug format
CHECK (slug ~ '^[a-z0-9-]+$')

-- Status valide
CHECK (status IN ('approved', 'pending', 'rejected'))

-- Compteurs positifs
CHECK (github_stars >= 0)
CHECK (github_forks >= 0)
CHECK (install_count >= 0)
CHECK (favorite_count >= 0)
CHECK (tools_count >= 0)

-- URLs valides (optionnel)
CHECK (github_url ~ '^https://github\.com/[^/]+/[^/]+$')
```

#### Table `mcp_configs`

```sql
-- Config type valide
CHECK (config_type IN ('npm', 'docker', 'python', 'binary'))

-- JSON valide (automatique avec JSONB)
CHECK (jsonb_typeof(config_json) = 'object')
```

#### Table `mcp_content`

```sql
-- Content type valide
CHECK (content_type IN ('readme', 'about', 'faq', 'changelog'))

-- Contenu non vide
CHECK (length(content) > 0)
```

### Validation Côté Application

#### Validation du slug

```typescript
const SLUG_REGEX = /^[a-z0-9-]+$/;

function validateSlug(slug: string): boolean {
    return SLUG_REGEX.test(slug) && 
           slug.length >= 3 && 
           slug.length <= 100 &&
           !slug.startsWith('-') &&
           !slug.endsWith('-');
}
```

#### Validation de l'URL GitHub

```typescript
function validateGithubUrl(url: string): boolean {
    const pattern = /^https:\/\/github\.com\/[^\/]+\/[^\/]+$/;
    return pattern.test(url);
}
```

#### Validation config_json

```typescript
interface ConfigNPM {
    command: 'npx' | 'node' | 'npm';
    args: string[];
    env?: Record<string, {
        required: boolean;
        label: string;
        type: 'secret' | 'text' | 'number';
        description?: string;
        get_url?: string;
        example?: string;
    }>;
    runtime?: string;
    min_node_version?: string;
}

function validateConfigNPM(config: unknown): config is ConfigNPM {
    // Validation avec Zod ou autre
    return true; // Simplification
}
```

---

## Migrations

### Migration depuis v1.0 (12 tables) → v2.0 (5 tables)

#### Étape 1 : Créer les nouvelles tables

```sql
-- Créer mcp_servers avec colonnes GitHub intégrées
CREATE TABLE mcp_servers_v2 AS
SELECT 
    s.id,
    s.slug,
    s.name,
    s.display_name,
    s.tagline,
    s.short_description as description,
    s.logo_url,
    s.homepage_url,
    
    -- GitHub depuis mcp_github_info
    gh.github_url,
    gh.github_owner,
    gh.github_repo,
    gh.github_stars,
    gh.github_forks,
    gh.github_last_commit,
    gh.primary_language,
    gh.license,
    
    -- Stats
    s.install_count,
    s.favorite_count,
    s.tools_count,
    
    -- Categories et tags depuis junction tables
    ARRAY(SELECT category_id FROM mcp_server_categories WHERE server_id = s.id) as categories,
    ARRAY(SELECT tag_id FROM mcp_server_tags WHERE server_id = s.id) as tags,
    
    -- Metadata
    s.status,
    s.creator_username,
    s.created_at,
    s.updated_at
FROM mcp_servers s
LEFT JOIN mcp_github_info gh ON gh.server_id = s.id;
```

#### Étape 2 : Migrer les configs

```sql
-- Fusionner mcp_config_npm et mcp_config_docker
CREATE TABLE mcp_configs_v2 AS
SELECT 
    id,
    server_id,
    'npm' as config_type,
    jsonb_build_object(
        'command', command,
        'args', args,
        'env', env_descriptions,
        'runtime', runtime
    ) as config_json,
    created_at,
    updated_at
FROM mcp_config_npm
UNION ALL
SELECT 
    id,
    server_id,
    'docker' as config_type,
    jsonb_build_object(
        'command', 'docker',
        'args', docker_command,
        'image', docker_image,
        'tag', docker_tag,
        'ports', ports,
        'volumes', volumes,
        'env', env_descriptions,
        'network_mode', network_mode
    ) as config_json,
    created_at,
    updated_at
FROM mcp_config_docker;
```

#### Étape 3 : Renommer et nettoyer

```sql
-- Supprimer anciennes tables
DROP TABLE mcp_github_info;
DROP TABLE mcp_npm_info;
DROP TABLE mcp_config_npm;
DROP TABLE mcp_config_docker;
DROP TABLE mcp_server_categories;
DROP TABLE mcp_server_tags;
DROP TABLE mcp_tool_parameters;

-- Renommer nouvelles tables
ALTER TABLE mcp_servers_v2 RENAME TO mcp_servers;
ALTER TABLE mcp_configs_v2 RENAME TO mcp_configs;
ALTER TABLE mcp_markdown_content RENAME TO mcp_content;

-- Recréer les index
-- (Voir section "Index et Optimisations")
```

---

## Maintenance

### Tâches Régulières

#### Mise à jour des statistiques PostgreSQL

```sql
-- Analyser les tables
ANALYZE mcp_servers;
ANALYZE mcp_configs;
ANALYZE mcp_content;
ANALYZE mcp_categories;
ANALYZE mcp_tags;

-- Vacuum complet (à faire hors heures de pointe)
VACUUM FULL ANALYZE mcp_servers;
```

#### Synchronisation GitHub

```sql
-- Identifier les serveurs à mettre à jour (>7 jours)
SELECT 
    id,
    slug,
    github_url,
    github_last_commit,
    updated_at
FROM mcp_servers
WHERE updated_at < NOW() - INTERVAL '7 days'
ORDER BY github_stars DESC
LIMIT 100;
```

#### Nettoyage des serveurs obsolètes

```sql
-- Serveurs archivés sur GitHub
UPDATE mcp_servers
SET status = 'rejected'
WHERE github_url IN (
    -- Liste des repos archivés à identifier via GitHub API
);
```

### Backup

```bash
# Backup quotidien
pg_dump -h host -U user -d mcpspot_v2 -F c -f backup_$(date +%Y%m%d).dump

# Restore
pg_restore -h host -U user -d mcpspot_v2 backup_20251127.dump
```

---

## Glossaire

| Terme | Définition |
|-------|------------|
| **MCP** | Model Context Protocol - Protocole standard pour connecter des outils à des LLMs |
| **Serveur MCP** | Application qui expose des outils/ressources via le protocole MCP |
| **Slug** | Identifiant URL-friendly unique (ex: `brave-search`) |
| **UUID** | Universal Unique Identifier - Format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| **JSONB** | Type PostgreSQL pour stocker du JSON de manière binaire et indexable |
| **GIN Index** | Generalized Inverted Index - Index PostgreSQL pour arrays et JSONB |
| **Foreign Key (FK)** | Clé étrangère - Référence vers une autre table |
| **Primary Key (PK)** | Clé primaire - Identifiant unique d'une ligne |

---

## Changelog

### v2.0 (Décembre 2025)

**Changements majeurs** :
- ✅ Réduction de 12 tables → 5 tables
- ✅ Intégration GitHub directement dans `mcp_servers`
- ✅ Fusion npm/docker config dans `mcp_configs` avec JSONB
- ✅ Simplification taxonomie avec arrays UUID[]
- ✅ Suppression des tables de jonction
- ✅ Focus sur données essentielles uniquement

**Bénéfices** :
- 🚀 Performance : -40% de JOINs
- 📉 Complexité : Structure plus simple
- 🔧 Maintenance : Moins de tables à gérer
- 📊 Queries : Plus rapides et lisibles

---

## Support

Pour toute question sur ce schéma :
- 📧 Email: dev@mcpspot.com
- 💬 Discord: discord.gg/mcpspot
- 📖 Docs: docs.mcpspot.com/database

---

**Dernière mise à jour** : 2025-12-01  
**Version** : 2.0  
**Auteur** : MCPspot Team
