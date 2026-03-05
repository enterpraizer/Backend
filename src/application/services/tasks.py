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
from src.infrastructure.models.vm_metrics import VmMetrics  # noqa: F401 — needed for relationship resolution
from src.infrastructure.models.vm_suggestion import VmSuggestion  # noqa: F401 — needed for relationship resolution
from src.settings import settings

logger = logging.getLogger(__name__)

# Synchronous engine for Celery workers — asyncpg not supported
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


@celery_app.task(name="collect_vm_metrics")
def collect_vm_metrics() -> None:
    """
    Periodic task (every 5min): simulate and store metrics for all RUNNING VMs.
    Uses a sync SQLAlchemy session — writes directly to vm_metrics table.
    """
    import asyncio
    from uuid import uuid4
    from datetime import datetime, timezone
    import math, random

    with Session(_sync_engine) as session:
        vms = session.execute(
            select(VirtualMachine).where(VirtualMachine.status == VMStatus.RUNNING)
        ).scalars().all()

        for vm in vms:
            age_hours = (datetime.now(timezone.utc) - vm.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            base_cpu = random.uniform(5, 80)
            daily_cycle = 10 * math.sin(2 * math.pi * age_hours / 24)
            cpu_pct = max(1.0, min(99.0, base_cpu + daily_cycle + random.uniform(-5, 5)))
            ram_pct = min(99.0, random.uniform(20, 85) + random.uniform(-5, 5))
            disk_pct = min(99.0, 30 + (age_hours * 0.1) + random.uniform(-2, 2))

            from src.infrastructure.models.vm_metrics import VmMetrics
            session.add(VmMetrics(
                id=uuid4(),
                vm_id=vm.id,
                cpu_pct=round(cpu_pct, 1),
                ram_pct=round(ram_pct, 1),
                disk_pct=round(disk_pct, 1),
            ))

        session.commit()
        logger.info("collect_vm_metrics: recorded metrics for %d VMs", len(vms))


@celery_app.task(name="analyze_vm_optimizations")
def analyze_vm_optimizations() -> None:
    """
    Periodic task (hourly): for each RUNNING VM, run LLM optimization analysis.
    Skips VMs that already received a suggestion in the last 24h.
    """
    import asyncio
    from datetime import datetime, timedelta, timezone

    with Session(_sync_engine) as session:
        vms = session.execute(
            select(VirtualMachine).where(VirtualMachine.status == VMStatus.RUNNING)
        ).scalars().all()

        skipped = 0
        analyzed = 0
        for vm in vms:
            # Skip if a pending suggestion was created in last 30 min (avoid spam)
            from src.infrastructure.models.vm_suggestion import VmSuggestion
            from src.infrastructure.models.vm_suggestion import SuggestionStatus
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
            recent = session.execute(
                select(VmSuggestion).where(
                    VmSuggestion.vm_id == vm.id,
                    VmSuggestion.created_at >= cutoff,
                    VmSuggestion.status == SuggestionStatus.PENDING,
                ).limit(1)
            ).scalar_one_or_none()

            if recent:
                skipped += 1
                continue

            # Compute averages from last 7 days of metrics
            from src.infrastructure.models.vm_metrics import VmMetrics
            import math
            week_ago = datetime.now(timezone.utc) - timedelta(hours=168)
            metrics = session.execute(
                select(VmMetrics).where(
                    VmMetrics.vm_id == vm.id,
                    VmMetrics.recorded_at >= week_ago,
                )
            ).scalars().all()

            if len(metrics) < 1:
                skipped += 1
                continue

            avg_cpu = sum(m.cpu_pct for m in metrics) / len(metrics)
            avg_ram = sum(m.ram_pct for m in metrics) / len(metrics)
            max_disk = max(m.disk_pct for m in metrics)

            prompt = (
                f"VM: {vm.vcpu} vCPU / {vm.ram_mb} MB RAM / {vm.disk_gb} GB disk\n"
                f"7-day averages: CPU={avg_cpu:.1f}% RAM={avg_ram:.1f}% Disk max={max_disk:.1f}%\n"
                "Suggest an optimization if there is a clear opportunity."
            )

            from src.application.services.llm_service import LLMService
            result = asyncio.get_event_loop().run_until_complete(
                LLMService().suggest_optimization(prompt)
            )

            if result.get("confidence", 0) >= 0.7:
                from src.infrastructure.models.vm_suggestion import VmSuggestion as VmSugg
                import uuid
                session.add(VmSugg(
                    id=uuid.uuid4(),
                    vm_id=vm.id,
                    tenant_id=vm.tenant_id,
                    suggestion_text=result["text"],
                    suggested_config=result.get("config"),
                    confidence=result["confidence"],
                ))
                analyzed += 1

        session.commit()
        logger.info(
            "analyze_vm_optimizations: analyzed=%d skipped=%d", analyzed, skipped
        )


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


@celery_app.task(name="send_weekly_ai_report")
def send_weekly_ai_report() -> None:
    """
    Weekly task (every Monday 9:00 MSK): send email digest of pending AI recommendations
    to each tenant owner who has at least one pending VmSuggestion.
    """
    from src.infrastructure.models.vm_suggestion import VmSuggestion as Sugg, SuggestionStatus
    from src.infrastructure.models.tenant import Tenant
    from src.infrastructure.models.users import User

    with Session(_sync_engine) as session:
        # Fetch all pending suggestions joined with VM, Tenant, User (owner)
        rows = session.execute(
            select(Sugg, VirtualMachine, Tenant, User)
            .join(VirtualMachine, Sugg.vm_id == VirtualMachine.id)
            .join(Tenant, Sugg.tenant_id == Tenant.id)
            .join(User, Tenant.owner_id == User.id)
            .where(Sugg.status == SuggestionStatus.PENDING)
            .order_by(Tenant.id, VirtualMachine.id)
        ).all()

    if not rows:
        logger.info("send_weekly_ai_report: no pending suggestions, skipping")
        return

    # Group by user email → {vm_name → [suggestion]}
    from collections import defaultdict
    by_user: dict[str, dict] = defaultdict(lambda: {"name": "", "vms": defaultdict(list)})
    for sugg, vm, tenant, user in rows:
        rec = by_user[user.email]
        rec["name"] = user.first_name or user.username
        rec["vms"][f"{vm.name} (ID: {str(vm.id)[:8]})"].append({
            "text": sugg.suggestion_text,
            "confidence": int(sugg.confidence * 100),
            "vm_id": str(vm.id),
            "tenant_slug": tenant.slug,
        })

    sent = 0
    for email_addr, data in by_user.items():
        try:
            html = _build_weekly_email_html(data["name"], data["vms"])
            msg = EmailMessage()
            msg["From"] = settings.email.username
            msg["To"] = email_addr
            msg["Subject"] = "☁️ Еженедельный отчёт ИИ-рекомендаций — CloudIaaS"
            msg.set_content(
                "Ваш почтовый клиент не поддерживает HTML. "
                "Откройте приложение CloudIaaS для просмотра рекомендаций.",
                subtype="plain",
            )
            msg.add_alternative(html, subtype="html")

            with smtplib.SMTP(host=settings.email.host, port=settings.email.port) as smtp:
                smtp.starttls()
                smtp.login(settings.email.username, settings.email.password.get_secret_value())
                smtp.send_message(msg)
            sent += 1
        except Exception as exc:
            logger.error("send_weekly_ai_report: failed to send to %s — %s", email_addr, exc)

    logger.info("send_weekly_ai_report: sent digest to %d users", sent)


def _build_weekly_email_html(user_name: str, vms: dict) -> str:
    """Build HTML body for the weekly AI recommendations digest email."""
    vm_blocks = ""
    for vm_label, suggestions in vms.items():
        cards = ""
        for s in suggestions:
            confidence_color = "#16a34a" if s["confidence"] >= 80 else "#d97706" if s["confidence"] >= 60 else "#dc2626"
            vm_url = f"{settings.frontend_url}/vms/{s['vm_id']}"
            cards += f"""
            <div style="background:#fef9c3;border-left:4px solid #f59e0b;border-radius:6px;padding:14px 16px;margin-bottom:12px;">
              <p style="margin:0 0 8px 0;font-size:14px;color:#1c1917;">🤖 {s['text']}</p>
              <span style="display:inline-block;background:{confidence_color};color:#fff;border-radius:12px;padding:2px 10px;font-size:12px;font-weight:600;">
                Уверенность: {s['confidence']}%
              </span>
            </div>"""
        vm_blocks += f"""
        <div style="margin-bottom:24px;">
          <h3 style="margin:0 0 10px 0;font-size:15px;color:#4f46e5;">🖥 {vm_label}</h3>
          {cards}
          <a href="{settings.frontend_url}/vms/{suggestions[0]['vm_id']}"
             style="display:inline-block;margin-top:6px;background:#4f46e5;color:#fff;padding:8px 18px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600;">
            Открыть VM →
          </a>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>ИИ-рекомендации CloudIaaS</title></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#6d28d9,#4f46e5);padding:28px 32px;">
            <h1 style="margin:0;color:#fff;font-size:22px;">✨ Еженедельные рекомендации ИИ</h1>
            <p style="margin:6px 0 0;color:#c4b5fd;font-size:14px;">CloudIaaS · Автоматический анализ ваших виртуальных машин</p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:28px 32px;">
            <p style="margin:0 0 20px;font-size:15px;color:#374151;">
              Привет, <strong>{user_name}</strong>! 👋<br>
              Вот что ИИ рекомендует для ваших виртуальных машин за последнюю неделю:
            </p>
            {vm_blocks}
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
            <p style="margin:0;font-size:13px;color:#6b7280;">
              Вы получили это письмо, потому что являетесь владельцем рабочего пространства в CloudIaaS.<br>
              Для управления уведомлениями перейдите в 
              <a href="{settings.frontend_url}/profile" style="color:#4f46e5;">настройки профиля</a>.
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f1f5f9;padding:16px 32px;text-align:center;">
            <p style="margin:0;font-size:12px;color:#9ca3af;">© 2025 CloudIaaS · Автоматическое сообщение</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
