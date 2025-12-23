import pytest
from unittest.mock import Mock, MagicMock, patch
import docker
from models import Server, ServerState, GameImage, User
from services.docker_manager import SidecarManager


@pytest.fixture
def mock_docker_client():
    with patch('services.docker_manager.docker') as mock_docker:
        client = Mock()
        mock_docker.from_env.return_value = client
        yield client


@pytest.fixture
def sample_game_image():
    return GameImage(
        id=1,
        friendly_name="Test Game",
        docker_image="test/game:latest",
        default_internal_port=7777,
        min_ram="2g",
        min_cpu="1.0",
        protocol="tcp"
    )


@pytest.fixture
def sample_user():
    return User(
        id=1,
        email="test@example.com",
        credits=10.0
    )


@pytest.fixture
def sample_server(sample_user, sample_game_image):
    return Server(
        id=1,
        user_id=sample_user.id,
        game_image_id=sample_game_image.id,
        friendly_name="Test Server",
        state=ServerState.SLEEPING,
        env_vars={},
        auto_sleep=True
    )


@pytest.fixture
def sidecar_manager(mock_docker_client):
    return SidecarManager(
        webhook_secret="test-secret",
        backend_url="http://localhost:8000",
        gcs_bucket="test-bucket"
    )


class TestSidecarManagerDeploy:
    
    @pytest.mark.skip("Requires more complex mocking of socket and docker interactions")
    def test_deploy_creates_network(self, sidecar_manager, sample_server, sample_game_image, mock_docker_client):
        pass
    
    def test_deploy_returns_false_if_containers_exist(self, sidecar_manager, sample_server, sample_game_image, mock_docker_client):
        mock_existing = Mock()
        mock_docker_client.containers.get.return_value = mock_existing
        
        result = sidecar_manager.deploy(sample_server, sample_game_image)
        
        assert result is False


class TestSidecarManagerWake:
    
    def test_wake_starts_game_container(self, sidecar_manager, sample_server, mock_docker_client):
        mock_container = Mock()
        mock_container.status = "exited"
        mock_docker_client.containers.get.return_value = mock_container
        
        result = sidecar_manager.wake(sample_server)
        
        assert result is True
        mock_container.start.assert_called_once()
        assert sample_server.state == ServerState.RUNNING
    
    def test_wake_already_running(self, sidecar_manager, sample_server, mock_docker_client):
        sample_server.state = ServerState.RUNNING
        mock_container = Mock()
        mock_container.status = "running"
        mock_docker_client.containers.get.return_value = mock_container
        
        result = sidecar_manager.wake(sample_server)
        
        assert result is True
        mock_container.start.assert_not_called()


class TestSidecarManagerHibernate:
    
    def test_hibernate_stops_game_container(self, sidecar_manager, sample_server, mock_docker_client):
        sample_server.state = ServerState.RUNNING
        mock_container = Mock()
        mock_container.status = "running"
        mock_docker_client.containers.get.return_value = mock_container
        
        result = sidecar_manager.hibernate(sample_server)
        
        assert result is True
        mock_container.stop.assert_called_once_with(timeout=30)
        assert sample_server.state == ServerState.SLEEPING
    
    def test_hibernate_already_sleeping(self, sidecar_manager, sample_server, mock_docker_client):
        sample_server.state = ServerState.SLEEPING
        mock_container = Mock()
        mock_container.status = "exited"
        mock_docker_client.containers.get.return_value = mock_container
        
        result = sidecar_manager.hibernate(sample_server)
        
        assert result is True
        mock_container.stop.assert_not_called()


class TestSidecarManagerDelete:
    
    def test_delete_removes_all_resources(self, sidecar_manager, sample_server, mock_docker_client):
        sample_server.game_container_id = "game-123"
        sample_server.proxy_container_id = "proxy-123"
        sample_server.private_network_name = "net-1"
        
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container
        
        mock_network = Mock()
        mock_docker_client.networks.get.return_value = mock_network
        
        mock_volume = Mock()
        mock_docker_client.volumes.get.return_value = mock_volume
        
        result = sidecar_manager.delete(sample_server)
        
        assert result is True
        assert mock_container.remove.call_count == 2
        mock_network.remove.assert_called_once()
        mock_volume.remove.assert_called_once()


class TestSidecarManagerStats:
    
    def test_get_container_stats(self, sidecar_manager, sample_server, mock_docker_client):
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container
        
        mock_container.stats.return_value = {
            'cpu_stats': {
                'cpu_usage': {'total_usage': 1000000},
                'system_cpu_usage': 2000000
            },
            'precpu_stats': {
                'cpu_usage': {'total_usage': 500000},
                'system_cpu_usage': 1000000
            },
            'memory_stats': {
                'usage': 1073741824,
                'limit': 2147483648
            }
        }
        mock_container.status = 'running'
        
        stats = sidecar_manager.get_container_stats(sample_server)
        
        assert 'cpu_percent' in stats
        assert 'memory_percent' in stats
        assert stats['status'] == 'running'


class TestSidecarManagerLogs:
    
    def test_get_container_logs(self, sidecar_manager, sample_server, mock_docker_client):
        mock_container = Mock()
        mock_container.logs.return_value = b"Test log line 1\nTest log line 2\n"
        mock_docker_client.containers.get.return_value = mock_container
        
        logs = sidecar_manager.get_container_logs(sample_server)
        
        assert "Test log line 1" in logs
        assert "Test log line 2" in logs


@pytest.mark.asyncio
class TestLifecycleManager:
    
    async def test_wake_on_webhook_valid_token(self, sidecar_manager, sample_server, sample_user):
        from services.lifecycle import LifecycleManager
        
        sample_server.game_container_id = "game-123"
        sample_user.credits = 10.0
        sidecar_manager.wake = Mock(return_value=True)
        
        mock_session = Mock()
        mock_session.get = Mock(side_effect=lambda x, y=None: sample_server if x == Server else sample_user)
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        
        lifecycle = LifecycleManager(sidecar_manager, lambda: mock_session)
        
        result = await lifecycle.wake_on_webhook(sample_server.id, "test-secret")
        
        assert result is True
        sidecar_manager.wake.assert_called_once_with(sample_server)
    
    async def test_wake_on_webhook_invalid_token(self, sidecar_manager):
        from services.lifecycle import LifecycleManager
        
        lifecycle = LifecycleManager(sidecar_manager, lambda: Mock())
        
        result = await lifecycle.wake_on_webhook(1, "wrong-secret")
        
        assert result is False
