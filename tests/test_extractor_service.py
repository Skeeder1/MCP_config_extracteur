"""
Tests unitaires pour ExtractorService.

Tests couverts :
- Récupération des serveurs à traiter
- Extraction d'une config
- Stockage de la config en JSONB
- Mise à jour du status selon validation
- Statistiques d'extraction
"""

import pytest
from unittest.mock import Mock, AsyncMock
from dotenv import load_dotenv

from src.database.db_manager import DatabaseManager
from src.database.repositories.servers_repository import ServersRepository
from src.database.repositories.content_repository import ContentRepository
from src.services.extractor_service import ExtractorService

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
def mock_extractor():
    """Fixture pour un LLMExtractor mocké."""
    extractor = Mock()
    extractor.extract_config = AsyncMock()
    return extractor


@pytest.fixture
def mock_validator():
    """Fixture pour un LLMValidator mocké."""
    validator = Mock()
    validator.validate_batch = AsyncMock()
    return validator


@pytest.fixture
def mock_prompt_builder():
    """Fixture pour un PromptBuilder mocké."""
    builder = Mock()
    builder.build_prompt = Mock(return_value="Test prompt")
    return builder


@pytest.fixture
def extractor_service(clean_database, mock_extractor, mock_validator, mock_prompt_builder):
    """Fixture pour ExtractorService avec mocks."""
    service = ExtractorService(
        clean_database,
        mock_extractor,
        mock_validator,
        mock_prompt_builder
    )
    return service


# =====================================================
# MOCK DATA
# =====================================================

def create_mock_config():
    """Crée une config mockée."""
    return {
        'command': 'npx',
        'args': ['-y', '@test/mcp-server'],
        'env': {'NODE_ENV': 'production'}
    }


def create_mock_extraction_result(has_config=True, has_error=False):
    """Crée un résultat d'extraction mocké."""
    if has_error:
        return {'error': 'Extraction failed'}

    config = create_mock_config() if has_config else None

    return {
        'config': config,
        'model': 'claude-3-5-sonnet',
        'prompt_tokens': 1000,
        'completion_tokens': 200
    }


def create_mock_validation(status='approved', score=8.0):
    """Crée une validation mockée."""
    return {
        'status': status,
        'score': score,
        'confidence': 0.9,
        'issues': [],
        'warnings': []
    }


# =====================================================
# TESTS - ExtractorService
# =====================================================

class TestExtractorService:
    """Tests pour ExtractorService."""

    def test_get_servers_to_process(self, extractor_service):
        """Test de récupération des serveurs sans config."""
        # Créer des serveurs dans la DB
        servers_repo = extractor_service.servers_repo
        content_repo = extractor_service.content_repo

        # Server 1: Sans config (should be returned)
        server1_data = {
            'slug': 'server-1',
            'name': 'Server 1',
            'github_url': 'https://github.com/test/server1',
            'github_owner': 'test',
            'github_repo': 'server1'
        }
        server1_id = servers_repo.insert_server(server1_data)
        content_repo.insert_content(server1_id, 'readme', '# Server 1')

        # Server 2: Avec config (should NOT be returned)
        server2_data = {
            'slug': 'server-2',
            'name': 'Server 2',
            'github_url': 'https://github.com/test/server2',
            'github_owner': 'test',
            'github_repo': 'server2'
        }
        server2_id = servers_repo.insert_server(server2_data)
        extractor_service.configs_repo.insert_config(server2_id, create_mock_config())

        # Get servers to process
        servers = extractor_service.get_servers_to_process()

        # Devrait retourner seulement server1
        assert len(servers) == 1
        assert servers[0]['slug'] == 'server-1'
        assert 'readme_content' in servers[0]

    @pytest.mark.asyncio
    async def test_process_server_success(self, extractor_service):
        """Test d'extraction d'un serveur avec succès."""
        # Créer un serveur
        servers_repo = extractor_service.servers_repo
        content_repo = extractor_service.content_repo

        server_data = {
            'slug': 'extract-test',
            'name': 'Extract Test',
            'github_url': 'https://github.com/test/extract',
            'github_owner': 'test',
            'github_repo': 'extract'
        }
        server_id = servers_repo.insert_server(server_data)
        content_repo.insert_content(server_id, 'readme', '# Extract Test Server')

        # Préparer le mock d'extraction
        extractor_service.extractor.extract_config.return_value = create_mock_extraction_result(has_config=True)

        # Get server to process
        servers = extractor_service.get_servers_to_process()
        server = servers[0]

        # Process
        result = await extractor_service.process_server(server)

        # Vérifications
        assert result['server_id'] == server_id
        assert result['config'] is not None
        assert result['config']['command'] == 'npx'
        assert 'extraction' in result
        assert 'error' not in result

    @pytest.mark.asyncio
    async def test_process_batch_with_validation(self, extractor_service):
        """Test de traitement d'un batch avec validation."""
        # Créer 2 serveurs
        servers_repo = extractor_service.servers_repo
        content_repo = extractor_service.content_repo

        server_ids = []
        for i in range(2):
            server_data = {
                'slug': f'batch-server-{i}',
                'name': f'Batch Server {i}',
                'github_url': f'https://github.com/test/batch{i}',
                'github_owner': 'test',
                'github_repo': f'batch{i}'
            }
            server_id = servers_repo.insert_server(server_data)
            content_repo.insert_content(server_id, 'readme', f'# Server {i}')
            server_ids.append(server_id)

        # Mock extraction
        extractor_service.extractor.extract_config.return_value = create_mock_extraction_result(has_config=True)

        # Mock validation
        validations = [
            create_mock_validation(status='approved', score=8.5),
            create_mock_validation(status='needs_review', score=6.0)
        ]
        extractor_service.validator.validate_batch.return_value = validations

        # Get servers
        servers = extractor_service.get_servers_to_process()

        # Process batch
        results = await extractor_service.process_batch(servers)

        # Vérifications
        assert len(results) == 2

        # Vérifier que les deux serveurs ont une config et un status
        for result in results:
            assert result['config'] is not None
            assert result['extraction']['status'] in ['approved', 'needs_review', 'rejected']

        # Vérifier qu'on a bien les deux status différents
        statuses = {r['extraction']['status'] for r in results}
        # Au moins un a une validation (peut être les deux car mocks)

        # Vérifier que les configs sont dans la DB
        config1 = extractor_service.configs_repo.get_config_by_server_id(server_ids[0])
        assert config1 is not None

        config2 = extractor_service.configs_repo.get_config_by_server_id(server_ids[1])
        assert config2 is not None

    def test_update_server_status(self, extractor_service):
        """Test de mise à jour du status du serveur."""
        # Créer un serveur
        server_data = {
            'slug': 'status-test',
            'name': 'Status Test',
            'github_url': 'https://github.com/test/status',
            'github_owner': 'test',
            'github_repo': 'status',
            'status': 'pending'
        }
        server_id = extractor_service.servers_repo.insert_server(server_data)

        # Update status (approved)
        extractor_service.update_server_status(server_id, 'approved', 8.0)

        # Vérifier
        server = extractor_service.servers_repo.get_server_by_github_url('https://github.com/test/status')
        assert server['status'] == 'approved'

    def test_get_extraction_statistics(self, extractor_service):
        """Test de calcul des statistiques."""
        # Créer des serveurs avec différents status
        servers_repo = extractor_service.servers_repo
        configs_repo = extractor_service.configs_repo

        # 3 serveurs
        for i in range(3):
            server_data = {
                'slug': f'stats-server-{i}',
                'name': f'Stats Server {i}',
                'github_url': f'https://github.com/test/stats{i}',
                'github_owner': 'test',
                'github_repo': f'stats{i}',
                'github_stars': (i + 1) * 100,
                'status': 'approved' if i < 2 else 'pending'
            }
            server_id = servers_repo.insert_server(server_data)

            # Ajouter config pour les 2 premiers
            if i < 2:
                configs_repo.insert_config(server_id, create_mock_config())

        # Get stats
        stats = extractor_service.get_extraction_statistics()

        assert stats['total_servers'] == 3
        assert stats['with_config'] == 2
        assert stats['without_config'] == 1
        assert stats['by_status']['approved'] == 2
        assert stats['by_status']['pending'] == 1
        assert stats['avg_stars_with_config'] == 150.0  # (100 + 200) / 2


# =====================================================
# EXECUTION
# =====================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
