from uuid import UUID

import docker
from docker.errors import DockerException, NotFound

from src.infrastructure.models.virtual_machine import VMStatus

HYPERVISOR_IMAGE = "alpine:latest"

_STATUS_MAP = {
    "running": VMStatus.RUNNING,
    "exited": VMStatus.STOPPED,
    "created": VMStatus.PENDING,
    "paused": VMStatus.STOPPED,
}


class HypervisorService:
    def __init__(self) -> None:
        try:
            self._client = docker.from_env()
        except DockerException:
            self._client = None  # graceful degradation if Docker not available

    def _container_name(self, vm_id: UUID, tenant_id: UUID) -> str:
        return f"vm-{str(tenant_id)[:8]}-{str(vm_id)[:8]}"

    async def provision_vm(
        self,
        vm_id: UUID,
        tenant_id: UUID,
        name: str,
        vcpu: int,
        ram_mb: int,
        disk_gb: int,
    ) -> dict:
        """Spawn a Docker container simulating a VM."""
        container_name = self._container_name(vm_id, tenant_id)
        if not self._client:
            return {
                "container_id": "mock-" + str(vm_id)[:8],
                "container_name": container_name,
                "ip_address": "10.0.0.1",
            }

        volume_name = f"vm-{vm_id}-disk"
        container = self._client.containers.run(
            image=HYPERVISOR_IMAGE,
            name=container_name,
            command="sleep infinity",
            nano_cpus=vcpu * 1_000_000_000,
            mem_limit=f"{ram_mb}m",
            volumes={volume_name: {"bind": "/data", "mode": "rw"}},
            detach=True,
            labels={
                "tenant_id": str(tenant_id),
                "vm_id": str(vm_id),
                "managed_by": "cloudiaas",
            },
        )
        # Reload to get fresh network info after container start
        container.reload()
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        ip = next(iter(networks.values()), {}).get("IPAddress", "") or "10.0.0.1"
        return {
            "container_id": container.id,
            "container_name": container.name,
            "ip_address": ip,
        }

    async def start_vm(self, container_id: str) -> VMStatus:
        if not self._client or container_id.startswith("mock-"):
            return VMStatus.RUNNING
        container = self._client.containers.get(container_id)
        container.start()
        return VMStatus.RUNNING

    async def stop_vm(self, container_id: str) -> VMStatus:
        if not self._client or container_id.startswith("mock-"):
            return VMStatus.STOPPED
        container = self._client.containers.get(container_id)
        container.stop(timeout=10)
        return VMStatus.STOPPED

    async def terminate_vm(self, container_id: str, vm_id: UUID) -> None:
        """Stop + remove container + remove disk volume."""
        if not self._client or container_id.startswith("mock-"):
            return
        try:
            container = self._client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove(force=True)
        except NotFound:
            pass
        try:
            volume = self._client.volumes.get(f"vm-{vm_id}-disk")
            volume.remove()
        except NotFound:
            pass

    async def get_vm_status(self, container_id: str) -> VMStatus:
        if not self._client or container_id.startswith("mock-"):
            return VMStatus.RUNNING
        try:
            container = self._client.containers.get(container_id)
            return _STATUS_MAP.get(container.status, VMStatus.STOPPED)
        except NotFound:
            return VMStatus.TERMINATED

    async def list_tenant_containers(self, tenant_id: UUID) -> list[dict]:
        """List all containers belonging to this tenant via label filter."""
        if not self._client:
            return []
        containers = self._client.containers.list(
            all=True, filters={"label": f"tenant_id={tenant_id}"}
        )
        return [{"id": c.id, "name": c.name, "status": c.status} for c in containers]
