"""
Tests unitaires pour la couche d'accès aux données (Data Access Layer).

Tests couverts :
- DatabaseManager: Connexion, transactions, queries
- ServersRepository: CRUD sur mcp_servers
- ConfigsRepository: CRUD sur mcp_configs
- ContentRepository: CRUD sur mcp_content
- CategoriesRepository: CRUD sur mcp_categories
- TagsRepository: CRUD sur mcp_tags
- Contraintes d'intégrité (foreign keys, unique)
"""

import pytest
import uuid
from datetime import datetime
from dotenv import load_dotenv

from src.database.db_manager import DatabaseManager
from src.database.repositories.servers_repository import ServersRepository
from src.database.repositories.configs_repository import ConfigsRepository
from src.database.repositories.content_repository import ContentRepository
from src.database.repositories.categories_repository import CategoriesRepository
from src.database.repositories.tags_repository import TagsRepository

# Charger les variables d'environnement
load_dotenv()


# =====================================================
# FIXTURES
# =====================================================

@pytest.fixture(scope="function")
def db_manager():
    """Fixture pour obtenir un DatabaseManager."""
    # Reset le singleton pour chaque test
    DatabaseManager._instance = None
    DatabaseManager._pool = None

    manager = DatabaseManager()
    yield manager

    # Cleanup après le test
    manager.close_pool()
    DatabaseManager._instance = None
    DatabaseManager._pool = None


@pytest.fixture(scope="function")
def clean_database(db_manager):
    """
    Fixture pour nettoyer la base de données avant chaque test.
    Supprime toutes les données des tables (TRUNCATE).
    """
    # Nettoyer avant le test
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE mcp_content CASCADE;")
        cursor.execute("TRUNCATE TABLE mcp_configs CASCADE;")
        cursor.execute("TRUNCATE TABLE mcp_servers CASCADE;")
        cursor.execute("TRUNCATE TABLE mcp_categories CASCADE;")
        cursor.execute("TRUNCATE TABLE mcp_tags CASCADE;")
        conn.commit()

    yield db_manager

    # Nettoyer après le test (optionnel)
    # On pourrait aussi garder les données pour inspection


@pytest.fixture
def servers_repo(clean_database):
    """Fixture pour ServersRepository."""
    return ServersRepository(clean_database)


@pytest.fixture
def configs_repo(clean_database):
    """Fixture pour ConfigsRepository."""
    return ConfigsRepository(clean_database)


@pytest.fixture
def content_repo(clean_database):
    """Fixture pour ContentRepository."""
    return ContentRepository(clean_database)


@pytest.fixture
def categories_repo(clean_database):
    """Fixture pour CategoriesRepository."""
    return CategoriesRepository(clean_database)


@pytest.fixture
def tags_repo(clean_database):
    """Fixture pour TagsRepository."""
    return TagsRepository(clean_database)


# =====================================================
# TESTS - DatabaseManager
# =====================================================

class TestDatabaseManager:
    """Tests pour DatabaseManager."""

    def test_connection(self, db_manager):
        """Test de connexion basique."""
        with db_manager.get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            assert result == (1,)

    def test_execute_query(self, db_manager):
        """Test d'exécution de requête."""
        result = db_manager.execute_query(
            "SELECT COUNT(*) FROM mcp_servers;"
        )
        assert isinstance(result, int)

    def test_fetch_one(self, db_manager):
        """Test de fetch_one."""
        result = db_manager.fetch_one("SELECT 1 AS value;")
        assert result is not None
        assert result['value'] == 1

    def test_fetch_all(self, db_manager):
        """Test de fetch_all."""
        results = db_manager.fetch_all("SELECT 1 UNION SELECT 2;")
        assert len(results) == 2

    def test_transaction_commit(self, clean_database):
        """Test de transaction avec commit."""
        servers_repo = ServersRepository(clean_database)

        # Insérer un serveur dans une transaction
        server_data = {
            'slug': 'test-server',
            'name': 'Test Server',
            'github_url': 'https://github.com/test/repo',
            'github_owner': 'test',
            'github_repo': 'repo',
        }

        server_id = servers_repo.insert_server(server_data)
        assert server_id is not None

        # Vérifier que le serveur existe
        server = servers_repo.get_server_by_slug('test-server')
        assert server is not None
        assert server['name'] == 'Test Server'

    def test_transaction_rollback(self, clean_database):
        """Test de transaction avec rollback."""
        with clean_database.get_connection() as conn:
            cursor = conn.cursor()

            # Insérer un serveur
            cursor.execute("""
                INSERT INTO mcp_servers (slug, name, display_name, github_url, github_owner, github_repo)
                VALUES ('rollback-test', 'Rollback Test', 'Rollback Test', 'https://github.com/test/rollback', 'test', 'rollback')
                RETURNING id;
            """)
            server_id = cursor.fetchone()[0]

            # Rollback (ne pas commit)
            conn.rollback()

        # Vérifier que le serveur n'existe pas
        servers_repo = ServersRepository(clean_database)
        server = servers_repo.get_server_by_slug('rollback-test')
        assert server is None


# =====================================================
# TESTS - ServersRepository
# =====================================================

class TestServersRepository:
    """Tests pour ServersRepository."""

    def test_insert_server(self, servers_repo):
        """Test d'insertion d'un serveur."""
        server_data = {
            'slug': 'test-mcp-server',
            'name': 'Test MCP Server',
            'description': 'A test MCP server',
            'github_url': 'https://github.com/testuser/test-mcp-server',
            'github_owner': 'testuser',
            'github_repo': 'test-mcp-server',
            'github_stars': 42,
            'github_forks': 7,
            'github_language': 'Python',
            'github_license': 'MIT',
            'status': 'pending'
        }

        server_id = servers_repo.insert_server(server_data)
        assert server_id is not None
        assert isinstance(uuid.UUID(server_id), uuid.UUID)

    def test_get_server_by_github_url(self, servers_repo):
        """Test de récupération par github_url."""
        # Insérer un serveur
        server_data = {
            'slug': 'github-url-test',
            'name': 'GitHub URL Test',
            'github_url': 'https://github.com/user/repo',
            'github_owner': 'user',
            'github_repo': 'repo',
        }
        servers_repo.insert_server(server_data)

        # Récupérer par URL
        server = servers_repo.get_server_by_github_url('https://github.com/user/repo')
        assert server is not None
        assert server['slug'] == 'github-url-test'

    def test_get_server_by_slug(self, servers_repo):
        """Test de récupération par slug."""
        # Insérer
        server_data = {
            'slug': 'slug-test',
            'name': 'Slug Test',
            'github_url': 'https://github.com/test/slug',
            'github_owner': 'test',
            'github_repo': 'slug',
        }
        servers_repo.insert_server(server_data)

        # Récupérer
        server = servers_repo.get_server_by_slug('slug-test')
        assert server is not None
        assert server['name'] == 'Slug Test'

    def test_update_server(self, servers_repo):
        """Test de mise à jour d'un serveur."""
        # Insérer
        server_data = {
            'slug': 'update-test',
            'name': 'Update Test',
            'github_url': 'https://github.com/test/update',
            'github_owner': 'test',
            'github_repo': 'update',
            'github_stars': 10
        }
        server_id = servers_repo.insert_server(server_data)

        # Mettre à jour
        updates = {
            'github_stars': 100,
            'status': 'approved'
        }
        servers_repo.update_server(server_id, updates)

        # Vérifier
        server = servers_repo.get_server_by_slug('update-test')
        assert server['github_stars'] == 100
        assert server['status'] == 'approved'

    def test_server_exists(self, servers_repo):
        """Test de vérification d'existence."""
        url = 'https://github.com/test/exists'

        # Pas encore inséré
        assert servers_repo.server_exists(url) is False

        # Insérer
        server_data = {
            'slug': 'exists-test',
            'name': 'Exists Test',
            'github_url': url,
            'github_owner': 'test',
            'github_repo': 'exists',
        }
        servers_repo.insert_server(server_data)

        # Maintenant existe
        assert servers_repo.server_exists(url) is True

    def test_get_all_servers(self, servers_repo):
        """Test de récupération de tous les serveurs."""
        # Insérer 3 serveurs
        for i in range(3):
            server_data = {
                'slug': f'server-{i}',
                'name': f'Server {i}',
                'github_url': f'https://github.com/test/repo{i}',
                'github_owner': 'test',
                'github_repo': f'repo{i}',
                'status': 'approved' if i % 2 == 0 else 'pending'
            }
            servers_repo.insert_server(server_data)

        # Récupérer tous
        all_servers = servers_repo.get_all_servers()
        assert len(all_servers) == 3

        # Récupérer par status
        approved = servers_repo.get_all_servers(status='approved')
        assert len(approved) == 2

        pending = servers_repo.get_all_servers(status='pending')
        assert len(pending) == 1

    def test_unique_constraint_github_url(self, servers_repo):
        """Test de la contrainte unique sur github_url."""
        server_data = {
            'slug': 'unique-test',
            'name': 'Unique Test',
            'github_url': 'https://github.com/unique/test',
            'github_owner': 'unique',
            'github_repo': 'test',
        }

        # Premier insert OK
        servers_repo.insert_server(server_data)

        # Deuxième insert devrait échouer (même URL)
        server_data['slug'] = 'unique-test-2'
        with pytest.raises(Exception):  # psycopg2.IntegrityError
            servers_repo.insert_server(server_data)


# =====================================================
# TESTS - ConfigsRepository
# =====================================================

class TestConfigsRepository:
    """Tests pour ConfigsRepository."""

    def test_insert_config(self, servers_repo, configs_repo):
        """Test d'insertion d'une configuration."""
        # D'abord insérer un serveur
        server_data = {
            'slug': 'config-test',
            'name': 'Config Test',
            'github_url': 'https://github.com/test/config',
            'github_owner': 'test',
            'github_repo': 'config',
        }
        server_id = servers_repo.insert_server(server_data)

        # Insérer la config
        config_data = {
            'command': 'npx',
            'args': ['-y', '@test/mcp-server'],
            'env': {'NODE_ENV': 'production'}
        }

        config_id = configs_repo.insert_config(server_id, config_data)
        assert config_id is not None

    def test_get_config_by_server_id(self, servers_repo, configs_repo):
        """Test de récupération de config par server_id."""
        # Insérer serveur + config
        server_data = {
            'slug': 'get-config-test',
            'name': 'Get Config Test',
            'github_url': 'https://github.com/test/getconfig',
            'github_owner': 'test',
            'github_repo': 'getconfig',
        }
        server_id = servers_repo.insert_server(server_data)

        config_data = {
            'command': 'python',
            'args': ['-m', 'test_server']
        }
        configs_repo.insert_config(server_id, config_data)

        # Récupérer
        config = configs_repo.get_config_by_server_id(server_id)
        assert config is not None
        assert config['config_type'] == 'inferred'
        assert config['config_json']['command'] == 'python'

    def test_update_config(self, servers_repo, configs_repo):
        """Test de mise à jour de configuration."""
        # Insérer
        server_data = {
            'slug': 'update-config-test',
            'name': 'Update Config Test',
            'github_url': 'https://github.com/test/updateconfig',
            'github_owner': 'test',
            'github_repo': 'updateconfig',
        }
        server_id = servers_repo.insert_server(server_data)

        config_data = {'command': 'node', 'args': ['index.js']}
        configs_repo.insert_config(server_id, config_data)

        # Mettre à jour
        new_config = {'command': 'npx', 'args': ['-y', '@org/server']}
        configs_repo.update_config(server_id, new_config)

        # Vérifier
        config = configs_repo.get_config_by_server_id(server_id)
        assert config['config_json']['command'] == 'npx'

    def test_config_exists(self, servers_repo, configs_repo):
        """Test de vérification d'existence de config."""
        # Insérer serveur
        server_data = {
            'slug': 'config-exists-test',
            'name': 'Config Exists Test',
            'github_url': 'https://github.com/test/configexists',
            'github_owner': 'test',
            'github_repo': 'configexists',
        }
        server_id = servers_repo.insert_server(server_data)

        # Pas de config
        assert configs_repo.config_exists(server_id) is False

        # Insérer config
        config_data = {'command': 'docker', 'args': ['run']}
        configs_repo.insert_config(server_id, config_data)

        # Config existe
        assert configs_repo.config_exists(server_id) is True

    def test_foreign_key_constraint(self, configs_repo):
        """Test de la contrainte de clé étrangère."""
        # Essayer d'insérer une config avec un server_id inexistant
        fake_server_id = str(uuid.uuid4())
        config_data = {'command': 'test'}

        with pytest.raises(Exception):  # psycopg2.IntegrityError (foreign key violation)
            configs_repo.insert_config(fake_server_id, config_data)


# =====================================================
# TESTS - ContentRepository
# =====================================================

class TestContentRepository:
    """Tests pour ContentRepository."""

    def test_insert_content(self, servers_repo, content_repo):
        """Test d'insertion de contenu."""
        # Insérer serveur
        server_data = {
            'slug': 'content-test',
            'name': 'Content Test',
            'github_url': 'https://github.com/test/content',
            'github_owner': 'test',
            'github_repo': 'content',
        }
        server_id = servers_repo.insert_server(server_data)

        # Insérer README
        content_id = content_repo.insert_content(
            server_id=server_id,
            content_type='readme',
            content='# Test Server\n\nThis is a test README.'
        )
        assert content_id is not None

    def test_get_content_by_server(self, servers_repo, content_repo):
        """Test de récupération de tous les contenus d'un serveur."""
        # Insérer serveur
        server_data = {
            'slug': 'multi-content-test',
            'name': 'Multi Content Test',
            'github_url': 'https://github.com/test/multicontent',
            'github_owner': 'test',
            'github_repo': 'multicontent',
        }
        server_id = servers_repo.insert_server(server_data)

        # Insérer plusieurs contenus
        content_repo.insert_content(server_id, 'readme', '# README')
        content_repo.insert_content(server_id, 'about', 'About this server')
        content_repo.insert_content(server_id, 'faq', 'Frequently asked questions')

        # Récupérer tous les contenus
        contents = content_repo.get_content_by_server(server_id)
        assert len(contents) == 3

        content_types = {c['content_type'] for c in contents}
        assert content_types == {'readme', 'about', 'faq'}

    def test_get_content_by_type(self, servers_repo, content_repo):
        """Test de récupération d'un contenu par type."""
        # Insérer
        server_data = {
            'slug': 'type-content-test',
            'name': 'Type Content Test',
            'github_url': 'https://github.com/test/typecontent',
            'github_owner': 'test',
            'github_repo': 'typecontent',
        }
        server_id = servers_repo.insert_server(server_data)

        readme_content = '# My Server\n\nAwesome MCP server.'
        content_repo.insert_content(server_id, 'readme', readme_content)

        # Récupérer le README
        content = content_repo.get_content_by_type(server_id, 'readme')
        assert content is not None
        assert content['content'] == readme_content

        # Récupérer un type inexistant
        faq = content_repo.get_content_by_type(server_id, 'faq')
        assert faq is None

    def test_update_content(self, servers_repo, content_repo):
        """Test de mise à jour de contenu."""
        # Insérer
        server_data = {
            'slug': 'update-content-test',
            'name': 'Update Content Test',
            'github_url': 'https://github.com/test/updatecontent',
            'github_owner': 'test',
            'github_repo': 'updatecontent',
        }
        server_id = servers_repo.insert_server(server_data)

        content_id = content_repo.insert_content(server_id, 'readme', 'Old README')

        # Mettre à jour
        new_content = '# Updated README\n\nNew content!'
        content_repo.update_content(content_id, new_content)

        # Vérifier
        content = content_repo.get_content_by_type(server_id, 'readme')
        assert content['content'] == new_content


# =====================================================
# TESTS - CategoriesRepository
# =====================================================

class TestCategoriesRepository:
    """Tests pour CategoriesRepository."""

    def test_insert_category(self, categories_repo):
        """Test d'insertion d'une catégorie."""
        category_id = categories_repo.insert_category(
            slug='ai-ml',
            name='AI & Machine Learning',
            icon='🤖',
            color='blue'
        )
        assert category_id is not None

    def test_get_all_categories(self, categories_repo):
        """Test de récupération de toutes les catégories."""
        # Insérer plusieurs catégories
        categories_repo.insert_category('data', 'Data', '📊', 'green')
        categories_repo.insert_category('web', 'Web', '🌐', 'red')
        categories_repo.insert_category('dev-tools', 'Dev Tools', '🛠️', 'yellow')

        # Récupérer toutes
        all_categories = categories_repo.get_all_categories()
        assert len(all_categories) == 3

    def test_get_category_by_slug(self, categories_repo):
        """Test de récupération d'une catégorie par slug."""
        categories_repo.insert_category('testing', 'Testing', '🧪', 'purple')

        category = categories_repo.get_category_by_slug('testing')
        assert category is not None
        assert category['name'] == 'Testing'
        assert category['icon'] == '🧪'

    def test_unique_slug_constraint(self, categories_repo):
        """Test de la contrainte unique sur slug."""
        categories_repo.insert_category('unique', 'Unique', '✨', 'pink')

        # Essayer d'insérer le même slug
        with pytest.raises(Exception):
            categories_repo.insert_category('unique', 'Another Name', '🔥', 'orange')


# =====================================================
# TESTS - TagsRepository
# =====================================================

class TestTagsRepository:
    """Tests pour TagsRepository."""

    def test_insert_tag(self, tags_repo):
        """Test d'insertion d'un tag."""
        tag_id = tags_repo.insert_tag(
            slug='python',
            name='Python',
            color='blue'
        )
        assert tag_id is not None

    def test_get_all_tags(self, tags_repo):
        """Test de récupération de tous les tags."""
        tags_repo.insert_tag('javascript', 'JavaScript', 'yellow')
        tags_repo.insert_tag('typescript', 'TypeScript', 'blue')
        tags_repo.insert_tag('rust', 'Rust', 'orange')

        all_tags = tags_repo.get_all_tags()
        assert len(all_tags) == 3

    def test_get_tag_by_slug(self, tags_repo):
        """Test de récupération d'un tag par slug."""
        tags_repo.insert_tag('docker', 'Docker', 'cyan')

        tag = tags_repo.get_tag_by_slug('docker')
        assert tag is not None
        assert tag['name'] == 'Docker'

    def test_unique_slug_constraint(self, tags_repo):
        """Test de la contrainte unique sur slug."""
        tags_repo.insert_tag('api', 'API', 'green')

        with pytest.raises(Exception):
            tags_repo.insert_tag('api', 'Another API', 'red')


# =====================================================
# EXECUTION
# =====================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
