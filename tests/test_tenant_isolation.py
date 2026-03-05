"""
Critical multi-tenant isolation tests.
Each test verifies that one tenant cannot access, modify, or see another tenant's resources.
"""
import pytest
from tests.conftest import _create_vm, VM_PAYLOAD


# ── VM isolation ───────────────────────────────────────────────────────────────

async def test_tenant_cannot_see_other_tenant_vms(client, tenant_a, tenant_b):
    """GET /vms/{vm_a_id} by tenant_b must return 404 — not 403, to avoid leaking existence."""
    vm = await _create_vm(client, tenant_a["headers"])
    vm_a_id = vm["id"]

    resp = await client.get(f"/vms/{vm_a_id}", headers=tenant_b["headers"])
    assert resp.status_code == 404, (
        f"Expected 404 (not leak existence), got {resp.status_code}: {resp.text}"
    )


async def test_tenant_cannot_stop_other_tenant_vm(client, tenant_a, tenant_b):
    """POST /vms/{vm_a_id}/stop by tenant_b must return 404."""
    vm = await _create_vm(client, tenant_a["headers"])
    vm_a_id = vm["id"]

    resp = await client.post(f"/vms/{vm_a_id}/stop", headers=tenant_b["headers"])
    assert resp.status_code == 404, (
        f"Expected 404, got {resp.status_code}: {resp.text}"
    )


# ── Network isolation ──────────────────────────────────────────────────────────

async def test_tenant_network_isolation(client, tenant_a, tenant_b):
    """Tenant B's network list must NOT include networks created by Tenant A."""
    # Create a network for tenant_a
    net_resp = await client.post(
        "/networks",
        json={"name": "net-alpha", "cidr": "10.0.0.0/24", "is_public": False},
        headers=tenant_a["headers"],
    )
    assert net_resp.status_code == 201, net_resp.text

    # Tenant B lists networks — must NOT see tenant_a's network
    list_resp = await client.get("/networks", headers=tenant_b["headers"])
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    network_names = [n["name"] for n in items]
    assert "net-alpha" not in network_names, (
        f"Tenant B should not see Tenant A's network. Got: {network_names}"
    )


# ── Quota enforcement ──────────────────────────────────────────────────────────

async def test_quota_enforcement(client, tenant_a, admin):
    """Admin sets max_vms=2; third VM creation must return 429."""
    tid = tenant_a["tenant_id"]

    # Admin sets quota max_vms=2
    quota_resp = await client.patch(
        f"/admin/tenants/{tid}/quota",
        json={"max_vms": 2},
        headers=admin["headers"],
    )
    assert quota_resp.status_code == 200, f"Quota update failed: {quota_resp.text}"

    # First two VMs should succeed
    vm1 = await client.post("/vms", json={**VM_PAYLOAD, "name": "vm-1"}, headers=tenant_a["headers"])
    assert vm1.status_code == 201, f"VM1 creation failed: {vm1.text}"

    vm2 = await client.post("/vms", json={**VM_PAYLOAD, "name": "vm-2"}, headers=tenant_a["headers"])
    assert vm2.status_code == 201, f"VM2 creation failed: {vm2.text}"

    # Third VM must be rejected (quota exceeded)
    vm3 = await client.post("/vms", json={**VM_PAYLOAD, "name": "vm-3"}, headers=tenant_a["headers"])
    assert vm3.status_code == 429, (
        f"Expected 429 (quota exceeded), got {vm3.status_code}: {vm3.text}"
    )


async def test_quota_releases_on_terminate(client, tenant_a):
    """After VM is terminated, used_vms must drop back to 0."""
    vm = await _create_vm(client, tenant_a["headers"])
    vm_id = vm["id"]

    # Confirm quota is in use
    usage_before = await client.get("/dashboard/usage", headers=tenant_a["headers"])
    assert usage_before.status_code == 200
    assert usage_before.json()["vms"]["used"] >= 1

    # Terminate the VM
    del_resp = await client.delete(f"/vms/{vm_id}", headers=tenant_a["headers"])
    assert del_resp.status_code == 204, f"Terminate failed: {del_resp.text}"

    # Quota should be released
    usage_after = await client.get("/dashboard/usage", headers=tenant_a["headers"])
    assert usage_after.status_code == 200
    assert usage_after.json()["vms"]["used"] == 0, (
        f"used_vms should be 0 after termination, got {usage_after.json()['vms']}"
    )


# ── Admin cross-tenant visibility ──────────────────────────────────────────────

async def test_admin_can_see_all_tenants(client, tenant_a, tenant_b, admin):
    """GET /admin/vms should return VMs from BOTH tenants."""
    vm_a = await _create_vm(client, tenant_a["headers"], {**VM_PAYLOAD, "name": "vm-alpha"})
    vm_b = await _create_vm(client, tenant_b["headers"], {**VM_PAYLOAD, "name": "vm-beta"})

    resp = await client.get("/admin/vms", headers=admin["headers"])
    assert resp.status_code == 200, resp.text

    vm_ids = {v["id"] for v in resp.json()["items"]}
    assert vm_a["id"] in vm_ids, "Admin should see tenant A's VM"
    assert vm_b["id"] in vm_ids, "Admin should see tenant B's VM"
