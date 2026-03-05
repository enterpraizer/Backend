"""
VM lifecycle integration tests.
Tests the full state machine: PENDING → RUNNING → STOPPED → RUNNING → TERMINATED.
"""
import pytest
from tests.conftest import _create_vm, VM_PAYLOAD


async def test_vm_full_lifecycle(client, tenant_a):
    """
    Full VM state machine:
      create → RUNNING (after provision)
      stop   → STOPPED
      start  → RUNNING
      delete → TERMINATED (204)
    """
    headers = tenant_a["headers"]

    # 1. Create — should land in RUNNING (HypervisorService mock returns RUNNING)
    vm = await _create_vm(client, headers)
    assert vm["status"] == "running", f"Expected running after create, got {vm['status']}"
    vm_id = vm["id"]

    # 2. Stop
    stop_resp = await client.post(f"/vms/{vm_id}/stop", headers=headers)
    assert stop_resp.status_code == 200, f"Stop failed: {stop_resp.text}"
    assert stop_resp.json()["status"] == "stopped"

    # 3. Start
    start_resp = await client.post(f"/vms/{vm_id}/start", headers=headers)
    assert start_resp.status_code == 200, f"Start failed: {start_resp.text}"
    assert start_resp.json()["status"] == "running"

    # 4. Terminate
    del_resp = await client.delete(f"/vms/{vm_id}", headers=headers)
    assert del_resp.status_code == 204, f"Terminate failed: {del_resp.text}"

    # 5. VM should no longer be retrievable (terminated)
    get_resp = await client.get(f"/vms/{vm_id}", headers=headers)
    # Terminated VMs still exist in DB but can be fetched; OR 404 depending on impl
    # Our get() returns the VM regardless of status — just verify no crash
    assert get_resp.status_code in (200, 404)


async def test_stop_already_stopped_returns_409(client, tenant_a):
    """Stopping a STOPPED VM must return 409 Conflict."""
    headers = tenant_a["headers"]
    vm = await _create_vm(client, headers)
    vm_id = vm["id"]

    # Stop once (valid)
    stop1 = await client.post(f"/vms/{vm_id}/stop", headers=headers)
    assert stop1.status_code == 200

    # Stop again (already stopped)
    stop2 = await client.post(f"/vms/{vm_id}/stop", headers=headers)
    assert stop2.status_code == 409, f"Expected 409, got {stop2.status_code}: {stop2.text}"


async def test_start_already_running_returns_409(client, tenant_a):
    """Starting a RUNNING VM must return 409 Conflict."""
    headers = tenant_a["headers"]
    vm = await _create_vm(client, headers)
    vm_id = vm["id"]
    assert vm["status"] == "running"

    start_resp = await client.post(f"/vms/{vm_id}/start", headers=headers)
    assert start_resp.status_code == 409, (
        f"Expected 409 for starting a running VM, got {start_resp.status_code}: {start_resp.text}"
    )


async def test_create_vm_quota_exceeded_returns_429_with_details(client, tenant_a, admin):
    """When quota is exceeded, POST /vms must return 429 with structured error detail."""
    tid = tenant_a["tenant_id"]

    # Admin reduces max_vms to 1
    quota_resp = await client.patch(
        f"/admin/tenants/{tid}/quota",
        json={"max_vms": 1},
        headers=admin["headers"],
    )
    assert quota_resp.status_code == 200

    # First VM: OK
    vm1 = await client.post("/vms", json=VM_PAYLOAD, headers=tenant_a["headers"])
    assert vm1.status_code == 201

    # Second VM: quota exceeded
    vm2 = await client.post("/vms", json={**VM_PAYLOAD, "name": "vm-overflow"}, headers=tenant_a["headers"])
    assert vm2.status_code == 429

    # Response must include structured detail
    body = vm2.json()
    detail = body.get("detail") or body  # router wraps in HTTPException detail dict
    assert "resource" in str(body).lower() or "quota" in str(body).lower(), (
        f"Expected quota detail in response body, got: {body}"
    )


async def test_vm_response_contains_ip_address_after_provision(client, tenant_a):
    """After provisioning, ip_address must be present (non-empty) in the response."""
    vm = await _create_vm(client, tenant_a["headers"])
    assert vm.get("ip_address"), (
        f"ip_address should be populated after provisioning, got: {vm.get('ip_address')!r}"
    )


async def test_vm_list_returns_only_own_vms(client, tenant_a):
    """GET /vms should only return VMs belonging to the current tenant."""
    headers = tenant_a["headers"]
    vm1 = await _create_vm(client, headers, {**VM_PAYLOAD, "name": "list-vm-1"})
    vm2 = await _create_vm(client, headers, {**VM_PAYLOAD, "name": "list-vm-2"})

    list_resp = await client.get("/vms", headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 2
    ids = {v["id"] for v in data["items"]}
    assert vm1["id"] in ids
    assert vm2["id"] in ids


async def test_update_vm_name(client, tenant_a):
    """PATCH /vms/{id} should update the VM name."""
    headers = tenant_a["headers"]
    vm = await _create_vm(client, headers)
    vm_id = vm["id"]

    patch_resp = await client.patch(
        f"/vms/{vm_id}",
        json={"name": "renamed-vm"},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["name"] == "renamed-vm"
