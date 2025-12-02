-- =====================================================
-- MCPspot Database Schema v2.0
-- PostgreSQL 17.6.1 Compatible
-- =====================================================
-- Description: Schéma complet pour le stockage des serveurs MCP,
--              configurations, contenu, catégories et tags
-- =====================================================

-- Drop existing tables (pour pouvoir réexécuter le script)
DROP TABLE IF EXISTS mcp_content CASCADE;
DROP TABLE IF EXISTS mcp_configs CASCADE;
DROP TABLE IF EXISTS mcp_servers CASCADE;
DROP TABLE IF EXISTS mcp_categories CASCADE;
DROP TABLE IF EXISTS mcp_tags CASCADE;

-- =====================================================
-- TABLE 1: mcp_categories (Référentiel)
-- =====================================================
CREATE TABLE mcp_categories (
    -- Identifiants
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,

    -- Informations
    name            TEXT NOT NULL,
    icon            TEXT,
    color           TEXT
);

-- Index
CREATE INDEX idx_categories_slug ON mcp_categories(slug);

COMMENT ON TABLE mcp_categories IS 'Référentiel des catégories pour organiser les serveurs MCP';

-- =====================================================
-- TABLE 2: mcp_tags (Référentiel)
-- =====================================================
CREATE TABLE mcp_tags (
    -- Identifiants
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,

    -- Informations
    name            TEXT NOT NULL,
    color           TEXT
);

-- Index
CREATE INDEX idx_tags_slug ON mcp_tags(slug);

COMMENT ON TABLE mcp_tags IS 'Référentiel des tags pour étiqueter les serveurs MCP';

-- =====================================================
-- TABLE 3: mcp_servers (TABLE CENTRALE)
-- =====================================================
CREATE TABLE mcp_servers (
    -- Identifiants
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                TEXT UNIQUE NOT NULL,
    name                TEXT NOT NULL,
    display_name        TEXT NOT NULL,

    -- Description
    tagline             TEXT DEFAULT '',
    description         TEXT DEFAULT '',
    logo_url            TEXT,
    homepage_url        TEXT,

    -- GitHub (Informations essentielles)
    github_url          TEXT UNIQUE NOT NULL,
    github_owner        TEXT NOT NULL,
    github_repo         TEXT NOT NULL,
    github_stars        INTEGER DEFAULT 0 CHECK (github_stars >= 0),
    github_forks        INTEGER DEFAULT 0 CHECK (github_forks >= 0),
    github_last_commit  TIMESTAMPTZ,
    primary_language    TEXT,
    license             TEXT,

    -- Statistiques
    install_count       INTEGER DEFAULT 0 CHECK (install_count >= 0),
    favorite_count      INTEGER DEFAULT 0 CHECK (favorite_count >= 0),
    tools_count         INTEGER DEFAULT 0 CHECK (tools_count >= 0),

    -- Taxonomie (Arrays PostgreSQL)
    categories          UUID[] DEFAULT '{}',
    tags                UUID[] DEFAULT '{}',

    -- Métadonnées
    status              TEXT DEFAULT 'approved' CHECK (status IN ('approved', 'pending', 'rejected')),
    creator_username    TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour mcp_servers
CREATE INDEX idx_servers_slug ON mcp_servers(slug);
CREATE INDEX idx_servers_github_url ON mcp_servers(github_url);
CREATE INDEX idx_servers_github_stars ON mcp_servers(github_stars DESC);
CREATE INDEX idx_servers_install_count ON mcp_servers(install_count DESC);
CREATE INDEX idx_servers_status ON mcp_servers(status);
CREATE INDEX idx_servers_updated_at ON mcp_servers(updated_at DESC);
CREATE INDEX idx_servers_status_stars ON mcp_servers(status, github_stars DESC);

-- Index GIN pour arrays
CREATE INDEX idx_servers_categories ON mcp_servers USING GIN(categories);
CREATE INDEX idx_servers_tags ON mcp_servers USING GIN(tags);

COMMENT ON TABLE mcp_servers IS 'Table centrale stockant toutes les informations sur les serveurs MCP';
COMMENT ON COLUMN mcp_servers.status IS 'Statut de validation: approved, pending, rejected';
COMMENT ON COLUMN mcp_servers.categories IS 'Array d''UUIDs référençant mcp_categories';
COMMENT ON COLUMN mcp_servers.tags IS 'Array d''UUIDs référençant mcp_tags';

-- =====================================================
-- TABLE 4: mcp_configs (Configuration 1:1)
-- =====================================================
CREATE TABLE mcp_configs (
    -- Identifiants
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id       UUID UNIQUE NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,

    -- Configuration
    config_type     TEXT NOT NULL CHECK (config_type IN ('npm', 'docker', 'python', 'binary', 'inferred', 'other')),
    config_json     JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour mcp_configs
CREATE INDEX idx_configs_server_id ON mcp_configs(server_id);
CREATE INDEX idx_configs_type ON mcp_configs(config_type);
CREATE INDEX idx_configs_json ON mcp_configs USING GIN(config_json);

COMMENT ON TABLE mcp_configs IS 'Configurations d''installation (npm/docker/python/binary) en JSONB';
COMMENT ON COLUMN mcp_configs.config_json IS 'Configuration complète en JSONB (command, args, env, etc.)';

-- =====================================================
-- TABLE 5: mcp_content (Contenu 1:N)
-- =====================================================
CREATE TABLE mcp_content (
    -- Identifiants
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id       UUID NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,

    -- Contenu
    content_type    TEXT NOT NULL CHECK (content_type IN ('readme', 'about', 'faq', 'changelog')),
    content         TEXT NOT NULL DEFAULT '',

    -- Timestamp
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour mcp_content
CREATE INDEX idx_content_server_id ON mcp_content(server_id);
CREATE INDEX idx_content_type ON mcp_content(content_type);
CREATE INDEX idx_content_server_type ON mcp_content(server_id, content_type);

-- Full-text search (optionnel mais utile)
CREATE INDEX idx_content_fulltext ON mcp_content USING GIN(to_tsvector('english', content));

COMMENT ON TABLE mcp_content IS 'Contenu textuel/documentation (README, about, FAQ, changelog)';
COMMENT ON COLUMN mcp_content.content_type IS 'Type de contenu: readme, about, faq, changelog';

-- =====================================================
-- TRIGGERS pour updated_at automatique
-- =====================================================

-- Fonction trigger pour mettre à jour updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger sur mcp_servers
CREATE TRIGGER update_mcp_servers_updated_at
    BEFORE UPDATE ON mcp_servers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger sur mcp_configs
CREATE TRIGGER update_mcp_configs_updated_at
    BEFORE UPDATE ON mcp_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger sur mcp_content
CREATE TRIGGER update_mcp_content_updated_at
    BEFORE UPDATE ON mcp_content
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- CONTRAINTES ADDITIONNELLES
-- =====================================================

-- Contrainte sur le format du slug (lowercase, alphanumeric, hyphens only)
ALTER TABLE mcp_servers ADD CONSTRAINT check_slug_format
    CHECK (slug ~ '^[a-z0-9-]+$');

ALTER TABLE mcp_categories ADD CONSTRAINT check_category_slug_format
    CHECK (slug ~ '^[a-z0-9-]+$');

ALTER TABLE mcp_tags ADD CONSTRAINT check_tag_slug_format
    CHECK (slug ~ '^[a-z0-9-]+$');

-- Contrainte sur le format de l'URL GitHub
ALTER TABLE mcp_servers ADD CONSTRAINT check_github_url_format
    CHECK (github_url ~ '^https://github\.com/[^/]+/[^/]+/?$');

-- =====================================================
-- VUES UTILES (optionnel)
-- =====================================================

-- Vue pour récupérer les serveurs avec leurs configs
CREATE OR REPLACE VIEW v_servers_with_configs AS
SELECT
    s.*,
    c.config_type,
    c.config_json,
    c.created_at as config_created_at,
    c.updated_at as config_updated_at
FROM mcp_servers s
LEFT JOIN mcp_configs c ON c.server_id = s.id;

COMMENT ON VIEW v_servers_with_configs IS 'Vue combinant serveurs et leurs configurations';

-- Vue pour les statistiques globales
CREATE OR REPLACE VIEW v_global_statistics AS
SELECT
    COUNT(*) as total_servers,
    COUNT(*) FILTER (WHERE status = 'approved') as approved_servers,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_servers,
    COUNT(*) FILTER (WHERE status = 'rejected') as rejected_servers,
    SUM(install_count) as total_installs,
    AVG(github_stars) as avg_stars,
    MAX(github_stars) as max_stars,
    COUNT(DISTINCT primary_language) as total_languages
FROM mcp_servers;

COMMENT ON VIEW v_global_statistics IS 'Statistiques globales sur tous les serveurs';

-- =====================================================
-- DONNÉES INITIALES (optionnel - pour tests)
-- =====================================================

-- Vous pouvez ajouter ici des catégories/tags par défaut si nécessaire
-- Exemple:
-- INSERT INTO mcp_categories (slug, name, icon, color) VALUES
--     ('search-web', 'Search & Web', '🔍', '#10B981'),
--     ('data-analysis', 'Data Analysis', '📊', '#3B82F6');

-- =====================================================
-- FIN DU SCHÉMA
-- =====================================================

-- Afficher un résumé
DO $$
BEGIN
    RAISE NOTICE 'Schema created successfully!';
    RAISE NOTICE 'Tables: mcp_servers, mcp_configs, mcp_content, mcp_categories, mcp_tags';
    RAISE NOTICE 'Views: v_servers_with_configs, v_global_statistics';
END $$;
