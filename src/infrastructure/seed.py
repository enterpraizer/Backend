import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.settings import settings
from src.infrastructure.models.users import User, Roles
from src.infrastructure.models.tenant import Tenant
from src.infrastructure.models.resource_quota import ResourceQuota
from src.infrastructure.models.resource_usage import ResourceUsage
from src.infrastructure.models.virtual_machine import VirtualMachine, VMStatus

ADMIN_PASSWORD_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36q8F1/DQnTRPTwS.sBB6Ge"

ADMIN_EMAIL = "admin@cloudiaas.local"
ADMIN_USERNAME = "admin"

DEMO_TENANT_NAME = "Demo Tenant"
DEMO_TENANT_SLUG = "demo-tenant"


async def seed(session: AsyncSession) -> None:
    existing = (await session.execute(select(User).where(User.email == ADMIN_EMAIL))).scalar_one_or_none()
    if existing:
        print(f"[seed] Admin user already exists (id={existing.id}), skipping.")
        admin = existing
    else:
        admin = User(
            id=uuid.uuid4(),
            email=ADMIN_EMAIL,
            username=ADMIN_USERNAME,
            hashed_password=ADMIN_PASSWORD_HASH,
            first_name="Cloud",
            last_name="Admin",
            is_active=True,
            is_verified=True,
            role=Roles.ADMIN,
        )
        session.add(admin)
        await session.flush()
        print(f"[seed] Created admin user  id={admin.id}  email={admin.email}")

    existing_t = (await session.execute(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))).scalar_one_or_none()
    if existing_t:
        print(f"[seed] Demo tenant already exists (id={existing_t.id}), skipping.")
        tenant = existing_t
    else:
        tenant = Tenant(
            id=uuid.uuid4(),
            name=DEMO_TENANT_NAME,
            slug=DEMO_TENANT_SLUG,
            owner_id=admin.id,
            is_active=True,
        )
        session.add(tenant)
        await session.flush()
        print(f"[seed] Created tenant       id={tenant.id}  slug={tenant.slug}")

    existing_q = (await session.execute(select(ResourceQuota).where(ResourceQuota.tenant_id == tenant.id))).scalar_one_or_none()
    if not existing_q:
        quota = ResourceQuota(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            max_vcpu=8,
            max_ram_mb=16384,
            max_disk_gb=200,
            max_vms=5,
        )
        session.add(quota)
        print(f"[seed] Created quota        tenant_id={tenant.id}")

    existing_u = (await session.execute(select(ResourceUsage).where(ResourceUsage.tenant_id == tenant.id))).scalar_one_or_none()
    if not existing_u:
        usage = ResourceUsage(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            used_vcpu=0,
            used_ram_mb=0,
            used_disk_gb=0,
            used_vms=0,
        )
        session.add(usage)
        print(f"[seed] Created usage record tenant_id={tenant.id}")

    vms_data = [
        dict(name="web-server-01", vcpu=2, ram_mb=2048, disk_gb=20),
        dict(name="db-server-01",  vcpu=4, ram_mb=8192, disk_gb=100),
    ]
    for vm_data in vms_data:
        existing_vm = (await session.execute(
            select(VirtualMachine).where(
                VirtualMachine.tenant_id == tenant.id,
                VirtualMachine.name == vm_data["name"],
            )
        )).scalar_one_or_none()
        if not existing_vm:
            vm = VirtualMachine(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                owner_id=admin.id,
                status=VMStatus.STOPPED,
                container_id=f"mock-{str(uuid.uuid4())[:8]}",
                container_name=f"vm-{tenant.id!s:.8}-seed",
                ip_address="10.0.0.1",
                **vm_data,
            )
            session.add(vm)
            print(f"[seed] Created VM           name={vm_data['name']}  vcpu={vm_data['vcpu']}  ram={vm_data['ram_mb']}MB")

    await session.commit()
    print("[seed] Done ✓")


async def main() -> None:
    engine = create_async_engine(settings.db.url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
