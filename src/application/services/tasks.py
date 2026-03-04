import logging
import smtplib
from email.message import EmailMessage
from uuid import UUID

from celery import shared_task
from sqlalchemy import create_engine, update, select
from sqlalchemy.orm import Session

from src.application.services.celery_config import celery_app
from src.application.services.hypervisor_service import HypervisorService
from src.infrastructure.models.virtual_machine import VirtualMachine, VMStatus
from src.settings import settings

logger = logging.getLogger(__name__)

# Synchronous DB engine for Celery workers (no async)
_sync_url = settings.db.url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
_sync_engine = create_engine(_sync_url, pool_pre_ping=True)


@shared_task
def send_confirmation_email(to_email: str, token: str) -> None:
    confirmation_url = f"{settings.frontend_url}/auth/register_confirm?token={token}"

    text = f"""Спасибо за регистрацию!
Для подтверждения регистрации перейдите по ссылке: {confirmation_url}
"""

    message = EmailMessage()
    message.set_content(text)
    message["From"] = settings.email.username
    message["To"] = to_email
    message["Subject"] = "Подтверждение регистрации"

    with smtplib.SMTP(host=settings.email.host, port=settings.email.port) as smtp:
        smtp.starttls()
        smtp.login(
            user=settings.email.username,
            password=settings.email.password.get_secret_value(),
        )
        smtp.send_message(msg=message)


@celery_app.task(name="sync_vm_statuses")
def sync_vm_statuses() -> None:
    """
    Periodic task (every 60s): sync VM statuses from Docker to DB.
    Queries RUNNING/PENDING VMs, checks actual container state, updates on mismatch.
    """
    hypervisor = HypervisorService()

    with Session(_sync_engine) as session:
        rows = session.execute(
            select(VirtualMachine).where(
                VirtualMachine.status.in_([VMStatus.RUNNING, VMStatus.PENDING])
            )
        ).scalars().all()

        for vm in rows:
            if not vm.container_id:
                continue

            import asyncio
            actual_status = asyncio.get_event_loop().run_until_complete(
                hypervisor.get_vm_status(vm.container_id)
            )

            if actual_status != vm.status:
                logger.warning(
                    "VM %s status mismatch: DB=%s actual=%s — updating",
                    vm.id, vm.status, actual_status,
                )
                session.execute(
                    update(VirtualMachine)
                    .where(VirtualMachine.id == vm.id)
                    .values(status=actual_status)
                )

        session.commit()


@celery_app.task(name="cleanup_terminated_vms")
def cleanup_terminated_vms() -> None:
    """
    Periodic task (every hour): hard-delete VMs with status=TERMINATED older than 24h.
    """
    with Session(_sync_engine) as session:
        deleted = session.execute(
            select(VirtualMachine).where(VirtualMachine.status == VMStatus.TERMINATED)
        ).scalars().all()

        from datetime import datetime, timedelta
        threshold = datetime.utcnow() - timedelta(hours=24)
        count = 0
        for vm in deleted:
            if vm.updated_at and vm.updated_at < threshold:
                session.delete(vm)
                count += 1

        session.commit()
        if count:
            logger.info("cleanup_terminated_vms: removed %d old terminated VMs", count)


@celery_app.task(name="provision_vm_async")
def provision_vm_async(
    vm_id: str,
    tenant_id: str,
    name: str,
    vcpu: int,
    ram_mb: int,
    disk_gb: int,
) -> None:
    """
    Async VM provisioning via Celery for non-blocking API response.
    Updates VM status from PENDING → RUNNING after Docker container starts.
    """
    import asyncio
    hypervisor = HypervisorService()

    result = asyncio.get_event_loop().run_until_complete(
        hypervisor.provision_vm(
            vm_id=UUID(vm_id),
            tenant_id=UUID(tenant_id),
            name=name,
            vcpu=vcpu,
            ram_mb=ram_mb,
            disk_gb=disk_gb,
        )
    )

    with Session(_sync_engine) as session:
        session.execute(
            update(VirtualMachine)
            .where(VirtualMachine.id == UUID(vm_id))
            .values(
                status=VMStatus.RUNNING,
                container_id=result["container_id"],
                container_name=result["container_name"],
                ip_address=result["ip_address"],
            )
        )
        session.commit()

    logger.info("provision_vm_async: VM %s provisioned → RUNNING", vm_id)
