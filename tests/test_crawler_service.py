"""
Tests unitaires pour CrawlerService.

Tests couverts :
- Insertion d'un nouveau serveur
- Skip d'un serveur existant récent
- Extraction et stockage du README
- Gestion d'erreurs de crawl
- Statistiques de crawling
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.database.db_manager import DatabaseManager
from src.services.crawler_service import CrawlerService

# Charger les variables d'environnement
load_dotenv()


# =====================================================
# FIXTURES
# =====================================================

@pytest.fixture(scope="function")
def db_manager():
    """Fixture pour obtenir un DatabaseManager."""
    # Reset le singleton
    DatabaseManager._instance = None
    DatabaseManager._pool = None

    manager = DatabaseManager()
    yield manager

    # Cleanup
    manager.close_pool()
    DatabaseManager._instance = None
    DatabaseManager._pool = None


@pytest.fixture(scope="function")
def clean_database(db_manager):
    """Fixture pour nettoyer la base de données avant chaque test."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE mcp_content CASCADE;")
        cursor.execute("TRUNCATE TABLE mcp_configs CASCADE;")
        cursor.execute("TRUNCATE TABLE mcp_servers CASCADE;")
        cursor.execute("TRUNCATE TABLE mcp_categories CASCADE;")
        cursor.execute("TRUNCATE TABLE mcp_tags CASCADE;")
        conn.commit()

    yield db_manager


@pytest.fixture
def mock_crawler():
    """Fixture pour un GitHubCrawler mocké."""
    crawler = Mock()
    crawler.check_rate_limit = Mock()
    return crawler


@pytest.fixture
def crawler_service(clean_database, mock_crawler):
    """Fixture pour CrawlerService avec crawler mocké."""
    service = CrawlerService(clean_database, "fake_token")

    # Remplacer le crawler réel par le mock
    service.crawler = mock_crawler

    return service


# =====================================================
# MOCK DATA
# =====================================================

def create_mock_repo_data(github_url: str, has_readme: bool = True, has_error: bool = False):
    """Crée des données mockées de repo_data."""
    if has_error:
        return {
            'github_url': github_url,
            'error': 'GitHub API error 404: Not Found',
            'metadata': None,
            'files': {},
            'files_count': 0
        }

    files = {}
    if has_readme:
        files['README.md'] = '# Test Server\n\nThis is a test MCP server.'

    return {
        'github_url': github_url,
        'metadata': {
            'name': 'test-server',
            'full_name': 'testuser/test-server',
            'description': 'A test MCP server',
            'language': 'Python',
            'topics': ['mcp', 'test'],
            'stars': 42,
            'forks': 7,
            'homepage': 'https://example.com',
            'default_branch': 'main',
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-12-01T00:00:00Z'
        },
        'files': files,
        'files_count': len(files)
    }


# =====================================================
# TESTS - CrawlerService
# =====================================================

class TestCrawlerService:
    """Tests pour CrawlerService."""

    def test_process_server_new_success(self, crawler_service):
        """Test d'insertion d'un nouveau serveur avec succès."""
        server_input = {
            'slug': 'new-test-server',
            'name': 'New Test Server',
            'github_url': 'https://github.com/testuser/new-server'
        }

        # Mock du crawl réussi
        repo_data = create_mock_repo_data(server_input['github_url'], has_readme=True)
        crawler_service.crawler.fetch_repo_data_with_retry = Mock(return_value=repo_data)

        # Process
        result = crawler_service.process_server(server_input)

        # Vérifications
        assert result['status'] == 'success'
        assert 'server_id' in result
        assert result['readme_stored'] is True
        assert result['files_count'] == 1

        # Vérifier que le serveur est dans la DB
        server = crawler_service.servers_repo.get_server_by_github_url(server_input['github_url'])
        assert server is not None
        assert server['slug'] == 'new-test-server'
        assert server['github_stars'] == 42

        # Vérifier que le README est stocké
        content = crawler_service.content_repo.get_content_by_type(server['id'], 'readme')
        assert content is not None
        assert 'Test Server' in content['content']

    def test_process_server_skip_recent(self, crawler_service):
        """Test de skip d'un serveur mis à jour récemment."""
        # 1. Insérer un serveur récent
        server_data = {
            'slug': 'recent-server',
            'name': 'Recent Server',
            'github_url': 'https://github.com/testuser/recent',
            'github_owner': 'testuser',
            'github_repo': 'recent'
        }
        server_id = crawler_service.servers_repo.insert_server(server_data)

        # 2. Essayer de le re-crawler
        server_input = {
            'slug': 'recent-server',
            'name': 'Recent Server',
            'github_url': 'https://github.com/testuser/recent'
        }

        result = crawler_service.process_server(server_input, force_update=False)

        # Devrait être skippé (mis à jour il y a moins de 7 jours)
        assert result['status'] == 'skipped'
        assert result['server_id'] == server_id
        assert 'recently updated' in result['message'].lower() or 'skip' in result['message'].lower()

    def test_process_server_force_update(self, crawler_service):
        """Test de force update d'un serveur récent."""
        # 1. Insérer un serveur
        server_data = {
            'slug': 'force-server',
            'name': 'Force Server',
            'github_url': 'https://github.com/testuser/force',
            'github_owner': 'testuser',
            'github_repo': 'force',
            'github_stars': 10
        }
        server_id = crawler_service.servers_repo.insert_server(server_data)

        # 2. Re-crawler avec force_update=True
        server_input = {
            'slug': 'force-server',
            'name': 'Force Server',
            'github_url': 'https://github.com/testuser/force'
        }

        repo_data = create_mock_repo_data(server_input['github_url'])
        repo_data['metadata']['stars'] = 100  # Update stars
        crawler_service.crawler.fetch_repo_data_with_retry = Mock(return_value=repo_data)

        result = crawler_service.process_server(server_input, force_update=True)

        # Devrait être mis à jour
        assert result['status'] == 'success'
        assert result['server_id'] == server_id

        # Vérifier que les étoiles sont à jour
        server = crawler_service.servers_repo.get_server_by_github_url(server_input['github_url'])
        assert server['github_stars'] == 100

    def test_process_server_crawl_error_existing(self, crawler_service):
        """Test de gestion d'erreur de crawl pour un serveur existant."""
        # 1. Insérer un serveur
        server_data = {
            'slug': 'existing-server',
            'name': 'Existing Server',
            'github_url': 'https://github.com/testuser/existing',
            'github_owner': 'testuser',
            'github_repo': 'existing'
        }
        server_id = crawler_service.servers_repo.insert_server(server_data)

        # 2. Crawler échoue
        server_input = {
            'slug': 'existing-server',
            'name': 'Existing Server',
            'github_url': 'https://github.com/testuser/existing'
        }

        error_data = create_mock_repo_data(server_input['github_url'], has_error=True)
        crawler_service.crawler.fetch_repo_data_with_retry = Mock(return_value=error_data)

        result = crawler_service.process_server(server_input, force_update=True)

        # Devrait retourner error mais garder le serveur existant
        assert result['status'] == 'error'
        assert result['server_id'] == server_id
        assert 'error' in result
        assert 'already exists' in result['message'].lower()

    def test_process_server_crawl_error_new(self, crawler_service):
        """Test de gestion d'erreur de crawl pour un nouveau serveur."""
        server_input = {
            'slug': 'error-server',
            'name': 'Error Server',
            'github_url': 'https://github.com/testuser/error'
        }

        # Crawler échoue
        error_data = create_mock_repo_data(server_input['github_url'], has_error=True)
        crawler_service.crawler.fetch_repo_data_with_retry = Mock(return_value=error_data)

        result = crawler_service.process_server(server_input)

        # Devrait créer le serveur avec status='rejected'
        assert result['status'] == 'error'
        assert 'server_id' in result
        assert 'rejected' in result['message'].lower()

        # Vérifier le status dans la DB
        server = crawler_service.servers_repo.get_server_by_github_url(server_input['github_url'])
        assert server is not None
        assert server['status'] == 'rejected'

    def test_process_server_no_readme(self, crawler_service):
        """Test d'un serveur sans README."""
        server_input = {
            'slug': 'no-readme-server',
            'name': 'No README Server',
            'github_url': 'https://github.com/testuser/no-readme'
        }

        # Crawler réussi mais pas de README
        repo_data = create_mock_repo_data(server_input['github_url'], has_readme=False)
        crawler_service.crawler.fetch_repo_data_with_retry = Mock(return_value=repo_data)

        result = crawler_service.process_server(server_input)

        # Devrait réussir mais README non stocké
        assert result['status'] == 'success'
        assert result['readme_stored'] is False

        # Vérifier qu'il n'y a pas de README dans la DB
        server = crawler_service.servers_repo.get_server_by_github_url(server_input['github_url'])
        content = crawler_service.content_repo.get_content_by_type(server['id'], 'readme')
        assert content is None

    def test_get_processed_urls(self, crawler_service):
        """Test de récupération des URLs crawlées."""
        # Insérer 3 serveurs
        urls = [
            'https://github.com/user/repo1',
            'https://github.com/user/repo2',
            'https://github.com/user/repo3'
        ]

        for i, url in enumerate(urls):
            server_data = {
                'slug': f'server-{i}',
                'name': f'Server {i}',
                'github_url': url,
                'github_owner': 'user',
                'github_repo': f'repo{i}'
            }
            crawler_service.servers_repo.insert_server(server_data)

        # Récupérer les URLs
        processed_urls = crawler_service.get_processed_urls()

        assert len(processed_urls) == 3
        assert all(url in processed_urls for url in urls)

    def test_get_crawl_statistics(self, crawler_service):
        """Test de calcul des statistiques."""
        # Insérer des serveurs avec différents status
        servers_data = [
            {'slug': 'server-1', 'name': 'Server 1', 'github_url': 'https://github.com/user/repo1',
             'github_owner': 'user', 'github_repo': 'repo1', 'github_stars': 100, 'status': 'approved'},
            {'slug': 'server-2', 'name': 'Server 2', 'github_url': 'https://github.com/user/repo2',
             'github_owner': 'user', 'github_repo': 'repo2', 'github_stars': 50, 'status': 'approved'},
            {'slug': 'server-3', 'name': 'Server 3', 'github_url': 'https://github.com/user/repo3',
             'github_owner': 'user', 'github_repo': 'repo3', 'github_stars': 0, 'status': 'pending'}
        ]

        server_ids = []
        for data in servers_data:
            server_id = crawler_service.servers_repo.insert_server(data)
            server_ids.append(server_id)

        # Ajouter des README à 2 serveurs
        crawler_service.content_repo.insert_content(server_ids[0], 'readme', '# Server 1')
        crawler_service.content_repo.insert_content(server_ids[1], 'readme', '# Server 2')

        # Récupérer les stats
        stats = crawler_service.get_crawl_statistics()

        assert stats['total_servers'] == 3
        assert stats['by_status']['approved'] == 2
        assert stats['by_status']['pending'] == 1
        assert stats['with_readme'] == 2
        assert stats['avg_stars'] == 75.0  # (100 + 50) / 2

    def test_process_server_missing_github_url(self, crawler_service):
        """Test avec github_url manquant."""
        server_input = {
            'slug': 'invalid-server',
            'name': 'Invalid Server'
            # github_url manquant
        }

        result = crawler_service.process_server(server_input)

        assert result['status'] == 'error'
        assert 'github_url' in result['error'].lower()


# =====================================================
# EXECUTION
# =====================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
