# 📋 FRONTEND PLAN — CloudIaaS Client & Admin Panel

## Project Vision
A TimeWeb Cloud–inspired SaaS dashboard.
Two distinct interfaces: **Client Panel** (tenant user) and **Admin Panel** (superadmin).
Visual resource gauges, VM lifecycle controls, real-time status indicators.

---

## UI Goal
| Aspect | Target |
|---|---|
| Style | Clean SaaS, dark/light sidebar, white content area |
| Client UX | Resource gauge cards, VM table with status badges, one-click actions |
| Admin UX | Tenant list, quota editor, global stats charts, VM monitoring table |
| Responsiveness | Desktop-first, tablet-friendly |
| Feedback | Toast notifications, loading skeletons, optimistic UI |

---

## Tech Stack
| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript 5 |
| Build Tool | Vite 5 |
| Routing | React Router v6 (createBrowserRouter) |
| Server State | TanStack Query v5 (React Query) |
| Client State | Zustand |
| HTTP | Axios (interceptors for JWT + 401 handling) |
| Styling | Tailwind CSS v3 + shadcn/ui (slate theme) |
| Forms | React Hook Form + Zod |
| Charts | Recharts |
| Icons | Lucide React |
| Tests | Vitest + React Testing Library + MSW v2 |

---

## Team
| Role | Responsibility |
|---|---|
| **Dev-1** | Routing, App Layout, Protected Routes, Role-based rendering |
| **Dev-2** | Design System, Base Components, ResourceGauge, VMStatusBadge |
| **Dev-3** | Axios client, TypeScript types, React Query hooks, Zustand stores |
| **Dev-4** | Client Panel: VM pages, Create VM modal, Network pages |
| **Dev-5** | Admin Panel: Charts, Tenant management, Quota editor, Tests |

---

## Pages Overview
```
/login                → LoginPage (public)
/register             → RegisterPage (public)
/register/confirm     → ConfirmEmailPage (public)
/onboarding           → CreateTenantPage (auth, no tenant yet)
/dashboard            → DashboardPage (client)
/vms                  → VMListPage (client)
/vms/:id              → VMDetailPage (client)
/networks             → NetworkListPage (client)
/profile              → ProfilePage (client)
/admin                → AdminDashboard (admin)
/admin/tenants        → TenantListPage (admin)
/admin/tenants/:id    → TenantDetailPage (admin)
/admin/vms            → AdminVMListPage (admin)
/admin/audit          → AuditLogPage (admin)
*                     → NotFoundPage
```

---

## DAY 1 — Foundation, Auth & Layout

### 1.1 [Dev-1] Project Scaffold + Router + Protected Routes
- [ ] **Demonstrates: UI Quality, Role-based Access** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Create a React 18 + TypeScript + Vite project (npm create vite@latest frontend -- --template react-ts).
Set up folder structure:
  src/
  ├── api/            ← axios client, typed endpoint functions
  ├── components/
  │   ├── ui/         ← shadcn + custom base components
  │   ├── features/
  │   │   ├── vms/    ← VM-specific components
  │   │   ├── networks/
  │   │   ├── quotas/
  │   │   └── admin/
  │   └── layout/     ← AppLayout, Sidebar, Topbar
  ├── pages/          ← route-level components (lazy loaded)
  ├── hooks/          ← React Query hooks per domain
  ├── store/          ← Zustand stores
  ├── types/          ← TypeScript interfaces
  ├── lib/            ← zod schemas, utils, constants
  └── tests/          ← Vitest tests

In src/router/index.tsx use createBrowserRouter:
  Public routes: /login, /register, /register/confirm
  Onboarding route: /onboarding (auth required, redirects to /dashboard if tenant exists)
  Client routes (protected + has tenant): wrapped in <AppLayout>, lazy loaded:
    /dashboard, /vms, /vms/:id, /networks, /profile
  Admin routes (protected + role=admin): wrapped in <AdminLayout>, lazy loaded:
    /admin, /admin/tenants, /admin/tenants/:id, /admin/vms, /admin/audit
  Catch-all: * → NotFoundPage

Create src/components/ProtectedRoute.tsx:
  Reads from authStore: isAuthenticated, user
  If not authenticated → <Navigate to="/login" />
  If no tenant_id in user → <Navigate to="/onboarding" />

Create src/components/AdminRoute.tsx:
  Extends ProtectedRoute. If user.role !== "admin" → <Navigate to="/dashboard" />

Each lazy page wrapped in <Suspense fallback={<PageSkeleton />}>.
```
</details>

---

### 1.2 [Dev-2] Design System: Base Components + VMStatusBadge + ResourceGauge
- [ ] **Demonstrates: UI Quality** | ⏱ 3h

<details>
<summary>📎 Copilot Prompt</summary>

```
In the React + TypeScript project:
1. Install Tailwind CSS v3 + configure with slate color palette.
2. Install shadcn/ui: npx shadcn-ui@latest init
3. Add shadcn components: button, input, label, card, badge, dialog, dropdown-menu,
   table, toast, avatar, skeleton, separator, progress, tabs, select, tooltip.
4. Install: lucide-react, recharts, class-variance-authority

Create src/components/ui/ResourceGauge.tsx:
  Props:
    label: string          ← "vCPU" | "RAM" | "Disk" | "VMs"
    used: number
    max: number
    unit?: string          ← "cores" | "GB" | "VMs"
    icon?: ReactNode
  Renders:
    - shadcn Progress bar (colored: green <60%, yellow 60-85%, red >85%)
    - Label row: "{label}" left, "{used}{unit} / {max}{unit}" right
    - Percentage text below bar
    - If pct >= 100: show red warning badge "Quota exceeded"
  Example: <ResourceGauge label="RAM" used={8192} max={16384} unit="MB" />

Create src/components/ui/VMStatusBadge.tsx:
  Props: status: "pending" | "running" | "stopped" | "terminated"
  Renders shadcn Badge with:
    pending    → yellow bg, pulsing dot animation, "Pending"
    running    → green bg, solid dot, "Running"
    stopped    → gray bg, empty dot, "Stopped"
    terminated → red bg, "Terminated"
  Dot implemented as: <span className="w-2 h-2 rounded-full animate-pulse bg-current" />

Create src/components/ui/StatCard.tsx:
  Props: title: string, value: string | number, icon: ReactNode, trend?: {value: number, label: string}, color?: string
  Renders: shadcn Card with icon in colored circle, large value, title, optional trend indicator
  Used in Dashboard for: Total VMs, Running VMs, Networks, Used vCPU

Create src/components/ui/PageSkeleton.tsx:
  Full-page loading skeleton: header bar + 3 card skeletons side by side + table skeleton

Create src/components/ui/EmptyState.tsx:
  Props: title, description, action?: ReactNode, icon?: ReactNode
  Centered layout with icon, heading, subtext, optional call-to-action button

Create src/components/ui/ConfirmDialog.tsx:
  Props: open, title, description, confirmLabel, isLoading, onConfirm, onCancel, variant?: "danger"|"default"
  Uses shadcn Dialog. Confirm button is red variant when "danger". Shows Spinner when isLoading.
```
</details>

---

### 1.3 [Dev-3] Axios Client + TypeScript Types + Auth Store
- [ ] **Demonstrates: Multi-tenancy (tenant_id in token), UI Quality** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read the backend API contracts:
  POST /auth/token → {access_token, refresh_token, token_type}
  GET /auth/me → User object
  All /vms/* endpoints return VMResponse
  GET /dashboard/usage → {vcpu: {used,max,pct}, ram_mb: {...}, disk_gb: {...}, vms: {...}}

Create src/types/index.ts with all TypeScript interfaces:
  User: { id: string; email: string; username: string; role: "user"|"admin"; tenant_id: string|null; is_active: boolean; first_name?: string; last_name?: string; avatar_url?: string }
  Tokens: { access_token: string; refresh_token: string; token_type: string }
  Tenant: { id: string; name: string; slug: string; owner_id: string; is_active: boolean; created_at: string }
  VM: { id: string; tenant_id: string; name: string; status: VMStatus; vcpu: number; ram_mb: number; disk_gb: number; ip_address: string|null; container_id: string|null; created_at: string }
  VMStatus = "pending"|"running"|"stopped"|"terminated"
  VMCreate: { name: string; vcpu: number; ram_mb: number; disk_gb: number }
  Network: { id: string; tenant_id: string; name: string; cidr: string; status: string; is_public: boolean; created_at: string }
  ResourceUsage: { vcpu: UsageMetric; ram_mb: UsageMetric; disk_gb: UsageMetric; vms: UsageMetric }
  UsageMetric: { used: number; max: number; pct: number }
  Quota: { max_vcpu: number; max_ram_mb: number; max_disk_gb: number; max_vms: number }
  AdminStats: { total_tenants: number; active_tenants: number; total_vms: number; running_vms: number; total_vcpu_allocated: number; total_ram_mb_allocated: number; top_tenants_by_vms: Array<{tenant_name: string; vm_count: number}> }
  Paginated<T>: { items: T[]; total: number }
  ApiError: { detail: string; resource?: string; requested?: number; available?: number }

Create src/api/client.ts:
  axios instance baseURL=import.meta.env.VITE_API_URL ?? "http://localhost:8000"
  Request interceptor: attach Authorization: Bearer {accessToken} from authStore
  Response interceptor:
    On 401: try POST /auth/refresh with stored refresh_token → update tokens → retry original request
            If refresh also fails → authStore.logout() → redirect /login
    On 429: show toast "Too many requests. Please wait."
    On 5xx: show toast "Server error. Please try again."

Create src/store/authStore.ts (Zustand + persist to localStorage):
  state: { user: User|null; accessToken: string|null; refreshToken: string|null }
  computed: isAuthenticated = !!accessToken; isAdmin = user?.role === "admin"; hasTenant = !!user?.tenant_id
  actions: login(tokens, user), logout(), setUser(user), setTokens(tokens)

Create src/api/auth.ts, src/api/vms.ts, src/api/networks.ts, src/api/dashboard.ts, src/api/admin.ts
Each file exports typed async functions for each endpoint.
```
</details>

---

### 1.4 [Dev-4] Auth Pages (Login, Register, Confirm, Onboarding)
- [ ] **Demonstrates: Multi-tenancy (tenant creation flow), UI Quality** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/store/authStore.ts and src/api/auth.ts.

Create src/lib/schemas/auth.schema.ts with Zod:
  loginSchema: { username: z.string().min(1, "Required"), password: z.string().min(1, "Required") }
  registerSchema: { email: z.string().email(), username: z.string().min(3).max(50), password: z.string().min(8), confirm_password }.refine(passwords match)
  tenantSchema: { name: z.string().min(3).max(100, "Name must be 3-100 chars") }

Create src/pages/LoginPage.tsx:
  - Centered card layout with CloudIaaS logo/name at top
  - React Hook Form + zodResolver(loginSchema)
  - On submit: POST /auth/token (OAuth2 FormData: username + password)
  - On success: GET /auth/me to get user → authStore.login() → navigate /dashboard
  - Show inline field errors. Show API error as red alert below form.
  - Link "Don't have an account? Register" → /register
  - Show spinner on submit button while loading

Create src/pages/RegisterPage.tsx:
  - Same card layout
  - Fields: Email, Username, Password, Confirm Password
  - On success: show green success alert "Check your email to confirm your account"
  - Link to /login

Create src/pages/ConfirmEmailPage.tsx:
  - Reads token from URL ?token=...
  - Auto-calls GET /auth/register_confirm?token=... on mount
  - Shows: loading spinner → success card "Email confirmed! You can now log in" → /login button
  - OR: error card "Invalid or expired link"

Create src/pages/OnboardingPage.tsx (NEW — Multi-tenancy onboarding):
  - Shown when user is authenticated but has no tenant_id
  - Large centered card: "Welcome to CloudIaaS! Create your workspace."
  - Single input: Workspace name (maps to tenant name)
  - On submit: POST /auth/tenant {name}
  - On success: receive new tokens with tenant_id embedded → authStore.setTokens() → navigate /dashboard
  - Clean, welcoming design with cloud icon
```
</details>

---

### 1.5 [Dev-1] App Layout (Sidebar + Topbar) + Admin Layout
- [ ] **Demonstrates: UI Quality, Role-based rendering** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/store/authStore.ts (isAdmin, hasTenant, user).
Install: lucide-react (already in plan).

Create src/components/layout/Sidebar.tsx:
  Fixed left sidebar (w-64), dark background (slate-900), white text.
  Top: CloudIaaS logo + workspace name (from user.tenant?.name or slug)
  Navigation sections:
    COMPUTE:
      - Dashboard (/dashboard) — LayoutDashboard icon
      - Virtual Machines (/vms) — Server icon
    NETWORKING:
      - Networks (/networks) — Network icon
    ACCOUNT:
      - Profile (/profile) — User icon
  Admin section (visible only if isAdmin):
    ADMINISTRATION:
      - Admin Dashboard (/admin) — Shield icon
      - Tenants (/admin/tenants) — Building icon
      - All VMs (/admin/vms) — Layers icon
      - Audit Log (/admin/audit) — ClipboardList icon
  Bottom: User avatar + name + role badge + Logout button
  Active link: white bg with subtle highlight, left accent bar (border-l-2 border-blue-400)

Create src/components/layout/Topbar.tsx:
  Height 16, white bg, border-bottom.
  Left: page title (dynamic via context or route handle)
  Right: notification bell icon (placeholder) + UserAvatar dropdown (Profile, Logout)

Create src/components/layout/AppLayout.tsx:
  flex-row: Sidebar (fixed) + main content (flex-1 overflow-auto)
  main: Topbar at top + <Outlet /> below with p-6 padding

Create src/components/layout/AdminLayout.tsx:
  Same structure as AppLayout but with AdminRoute wrapper.
  Topbar shows "Admin Panel" badge next to title.

Create src/components/features/users/UserAvatar.tsx:
  Props: user: User, size: "sm"|"md"|"lg"
  Shows avatar_url if present (rounded img), else colored circle with initials.
  Color determined by hashing username → one of 8 Tailwind bg colors.
```
</details>

---

## DAY 2 — Client Panel: Compute, Networking & Usage

### 2.1 [Dev-3] React Query Hooks (all domains)
- [ ] **Demonstrates: Multi-tenancy (all queries tenant-scoped via JWT)** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/api/vms.ts, src/api/networks.ts, src/api/dashboard.ts, src/types/index.ts.

Create src/api/queryKeys.ts:
  export const queryKeys = {
    vms: { all: ["vms"], list: (params) => ["vms", "list", params], detail: (id) => ["vms", id] },
    networks: { all: ["networks"], list: (params) => ["networks", "list", params], detail: (id) => ["networks", id] },
    dashboard: { usage: ["dashboard", "usage"], vmSummary: ["dashboard", "vms-summary"], activity: ["dashboard", "activity"] },
    admin: { stats: ["admin", "stats"], tenants: (params) => ["admin", "tenants", params], allVMs: (params) => ["admin", "vms", params] },
  }

Create src/hooks/useVMs.ts:
  useVMList(params: {limit:number, offset:number, status?:string}) →
    useQuery({ queryKey: queryKeys.vms.list(params), queryFn: () => api.vms.list(params), staleTime: 30_000 })
  useVM(id: string) → useQuery detail
  useCreateVM() → useMutation({
    mutationFn: (data: VMCreate) => api.vms.create(data),
    onSuccess: () => { queryClient.invalidateQueries(queryKeys.vms.all); queryClient.invalidateQueries(queryKeys.dashboard.usage); toast.success("VM created successfully") },
    onError: (err: ApiError) => {
      if (err.status === 429) toast.error(`Quota exceeded for ${err.resource}: ${err.available} available`)
      else toast.error(err.detail)
    }
  })
  useStartVM() → useMutation({mutationFn: (id) => api.vms.start(id), onSuccess: () => invalidate vm detail + list})
  useStopVM()  → useMutation
  useTerminateVM() → useMutation(onSuccess: invalidate + usage)

Create src/hooks/useNetworks.ts: equivalent hooks for Network CRUD + attach/detach VM.

Create src/hooks/useDashboard.ts:
  useResourceUsage() → useQuery(queryKeys.dashboard.usage, staleTime: 30_000)
    → auto-refetches every 30s: refetchInterval: 30_000
  useVMSummary() → useQuery(queryKeys.dashboard.vmSummary)
  useActivityLog() → useQuery(queryKeys.dashboard.activity)

Create src/hooks/useAdmin.ts:
  useAdminStats(), useTenantList(params), useTenantDetail(id), useUpdateQuota(), useAdminVMs(params)
```
</details>

---

### 2.2 [Dev-2] Dashboard Page (Resource Gauges + VM Summary)
- [ ] **Demonstrates: Resource Control (visual), UI Quality** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/hooks/useDashboard.ts, src/components/ui/ResourceGauge.tsx, src/components/ui/StatCard.tsx.

Create src/pages/DashboardPage.tsx:
  Layout sections (top to bottom):

  SECTION 1 — Welcome header:
    "Good morning, {user.username}" + current date
    Subtitle: "Workspace: {tenant_slug}"

  SECTION 2 — Resource Usage Cards (grid 2x2 on desktop, 1 col on mobile):
    Uses useResourceUsage() data. Shows 4 ResourceGauge components:
      <ResourceGauge label="vCPU" used={usage.vcpu.used} max={usage.vcpu.max} unit=" cores" icon={<Cpu />} />
      <ResourceGauge label="RAM"  used={Math.round(usage.ram_mb.used/1024)} max={Math.round(usage.ram_mb.max/1024)} unit=" GB" icon={<MemoryStick />} />
      <ResourceGauge label="Disk" used={usage.disk_gb.used} max={usage.disk_gb.max} unit=" GB" icon={<HardDrive />} />
      <ResourceGauge label="VMs"  used={usage.vms.used} max={usage.vms.max} unit="" icon={<Server />} />
    Wrap each in a shadcn Card. Show skeleton when isLoading.

  SECTION 3 — VM Status Summary (row of StatCards):
    Uses useVMSummary() data:
      StatCard "Total VMs" value={summary.total} icon={<Server />} color="blue"
      StatCard "Running"   value={summary.running} icon={<Play />} color="green"
      StatCard "Stopped"   value={summary.stopped} icon={<Pause />} color="gray"

  SECTION 4 — Recent Activity:
    Uses useActivityLog() data.
    Table: Time | Action | Resource | Details
    Max 5 rows shown, "View all →" link to full audit log.

  Add Create VM floating action button (bottom-right, mobile only): navigates to /vms with modal open.
  Show "Quota Exceeded" alert banner at top if any resource is at 100%:
    <Alert variant="destructive">You have reached your {resource} quota. Contact support to upgrade.</Alert>
```
</details>

---

### 2.3 [Dev-4] VM List Page + Create VM Modal
- [ ] **Demonstrates: Hypervisor (VM lifecycle), Resource Control (quota blocking), UI Quality** | ⏱ 3h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/hooks/useVMs.ts, src/hooks/useDashboard.ts, src/components/ui/VMStatusBadge.tsx.

Create src/lib/schemas/vm.schema.ts:
  vmCreateSchema = z.object({
    name: z.string().min(3, "Min 3 chars").max(100),
    vcpu: z.number().int().min(1).max(32, "Max 32 vCPU"),
    ram_mb: z.number().int().min(512).max(65536),
    disk_gb: z.number().int().min(10).max(500),
  })

Create src/components/features/vms/CreateVMModal.tsx:
  Props: open: boolean, onClose: () => void, currentUsage: ResourceUsage, quota: Quota
  Uses useCreateVM() mutation.
  React Hook Form + zodResolver.
  Fields with shadcn Input:
    - Name (text)
    - vCPU: number stepper (1-32), shows "Available: {quota.max_vcpu - usage.vcpu.used} cores"
    - RAM: Select options: [512MB, 1GB, 2GB, 4GB, 8GB, 16GB, 32GB, 64GB]
    - Disk: number input (GB), shows "Available: {quota.max_disk_gb - usage.disk_gb.used} GB"
  Live quota preview below form:
    "After creation: vCPU {new_used}/{max} | RAM {new_ram}/{max} | Disk {new_disk}/{max}"
    Preview bars update as user changes values.
  Submit button:
    DISABLED + tooltip "vCPU quota exceeded" if requested > available
    Shows spinner + "Creating..." while isLoading
  On success: close modal + navigate to /vms/{newVm.id}

Create src/pages/VMListPage.tsx:
  Header: "Virtual Machines" + "Create VM" button (opens CreateVMModal)
  Filter bar: status dropdown (All/Running/Stopped/Pending/Terminated) + search by name (debounced 300ms)
  
  Data table (VMTable) with columns:
    Name (clickable → /vms/{id})
    Status: <VMStatusBadge status={vm.status} />
    vCPU | RAM (show in GB) | Disk (GB)
    IP Address (or "—" if null)
    Created At (relative time: "2 hours ago")
    Actions: Start (play icon, disabled unless stopped) | Stop (pause, disabled unless running) | Terminate (trash, always available unless terminated) — each triggers ConfirmDialog for destructive actions
  
  Pagination: 10 items/page, shadcn Pagination component.
  Empty state: "No virtual machines yet. Create your first VM →" with Create button.
  Disabled "Create VM" button with tooltip when VMs quota exceeded.
```
</details>

---

### 2.4 [Dev-4] VM Detail Page + Network List/Create
- [ ] **Demonstrates: Hypervisor (status transitions), Multi-tenancy (tenant-isolated networks)** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/hooks/useVMs.ts, src/hooks/useNetworks.ts.

Create src/pages/VMDetailPage.tsx:
  Uses useVM(id) query + useStartVM, useStopVM, useTerminateVM mutations.
  Layout:
    TOP: VM name + VMStatusBadge (large) + action buttons:
      [▶ Start] — enabled only if status=stopped
      [⏸ Stop]  — enabled only if status=running
      [🗑 Terminate] — always visible, opens ConfirmDialog ("This will destroy the VM and all data")
    DETAILS CARD (grid 2-col):
      VM ID | Tenant ID
      vCPU  | RAM
      Disk  | IP Address
      Container ID (truncated) | Created At
    RESOURCE ALLOCATION BARS (3 small ResourceGauge showing this VM's share of total quota):
      "This VM uses: {vcpu} of your {max_vcpu} vCPU quota"
    NETWORKS CARD:
      Lists attached networks (network name + CIDR badge)
      "Attach to network" dropdown (fetches /networks list)
      "Detach" button per attached network

Create src/pages/NetworkListPage.tsx + CreateNetworkModal:
  Schema: { name: z.string().min(3), cidr: z.string().regex(IPv4_CIDR_REGEX, "e.g. 192.168.1.0/24"), is_public: z.boolean().default(false) }
  NetworkTable columns: Name, CIDR, Status badge, Public/Private, VMs attached (count), Created At, Actions (Delete)
  CreateNetworkModal: Name + CIDR input with helper text + Public toggle

Create src/components/features/networks/NetworkStatusBadge.tsx:
  active → green "Active", inactive → gray "Inactive"
```
</details>

---

### 2.5 [Dev-3] Profile Page + Quota Usage Widget
- [ ] **Demonstrates: Resource Control (usage visibility), UI Quality** | ⏱ 1h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/hooks/useAuth.ts and src/hooks/useDashboard.ts.

Create src/pages/ProfilePage.tsx with 3 tabs (shadcn Tabs):

  Tab 1 "Account":
    User avatar (large, UserAvatar component), email, username, member since
    Edit form: first_name, last_name, avatar_url URL input
    Calls PATCH /users/{id}. Shows success toast.

  Tab 2 "Workspace":
    Tenant name + slug (read-only)
    4 ResourceGauge components (same as Dashboard) showing current usage
    "Upgrade quota" section: "Need more resources? Contact your administrator."
    Table: Quota limits (vCPU, RAM, Disk, VMs) — current limits vs current usage

  Tab 3 "Security":
    Change Password form: old_password, new_password, confirm_new_password
    Zod validation: new must be min 8 chars, must match confirm
    Calls PATCH /auth/change_password
    On success: toast "Password changed. You'll be logged out." → logout after 2s

Create src/components/features/quotas/QuotaSummaryCard.tsx:
  Props: usage: ResourceUsage
  Compact card showing all 4 gauges in a 2x2 grid.
  Used in both DashboardPage and ProfilePage.
  Border turns red when any resource > 90%.
```
</details>

---

## DAY 3 — Admin Panel, Charts & Tests

### 3.1 [Dev-5] Admin Dashboard + Global Stats Charts
- [ ] **Demonstrates: Resource Distribution Control (admin view), UI Quality** | ⏱ 3h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/hooks/useAdmin.ts (useAdminStats, useTenantList).
Install: recharts

Create src/pages/AdminDashboardPage.tsx:
  Uses useAdminStats() → AdminStats type.

  SECTION 1 — Global Stats Row (StatCards):
    Total Tenants | Active Tenants | Total VMs | Running VMs
    Total vCPU Allocated | Total RAM Allocated (TB/GB) | Total Disk Allocated (TB)

  SECTION 2 — Charts (grid 2-col):
    Chart A: BarChart (Recharts) — "Top 5 Tenants by VM Count"
      Data: adminStats.top_tenants_by_vms
      X-axis: tenant_name, Y-axis: vm_count
      Colored bars with tooltip

    Chart B: PieChart — "VM Status Distribution"
      Data: {running: N, stopped: N, pending: N, terminated: N}
      Color: green/gray/yellow/red per status
      Legend below chart

    Chart C: BarChart — "Resource Allocation by Tenant" (optional, stacked)
      Shows used_vcpu per tenant (fetched from tenant list with usage)

  SECTION 3 — Recent VMs Table (last 10 across all tenants):
    Tenant Name | VM Name | Status | vCPU | RAM | Created At
    Link to /admin/vms for full list

  All charts responsive (use ResponsiveContainer from recharts).
  Show skeleton charts while loading (gray rounded rect placeholders).
```
</details>

---

### 3.2 [Dev-5] Tenant List + Quota Editor Modal
- [ ] **Demonstrates: Resource Distribution Control (admin assigns quotas), Multi-tenancy** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/hooks/useAdmin.ts (useTenantList, useUpdateQuota).

Create src/lib/schemas/admin.schema.ts:
  quotaUpdateSchema = z.object({
    max_vcpu: z.number().int().min(1).max(512).optional(),
    max_ram_mb: z.number().int().min(1024).max(1048576).optional(),
    max_disk_gb: z.number().int().min(10).max(10000).optional(),
    max_vms: z.number().int().min(1).max(100).optional(),
  })

Create src/pages/TenantListPage.tsx:
  Header: "Tenant Management" + search input (by name/slug)
  Tenant Table columns:
    Name + Slug (monospace badge)
    Owner (email)
    Status badge: Active (green) / Inactive (red)
    VMs (used_vms / max_vms shown as "3/5")
    vCPU usage bar (mini progress bar inline)
    RAM usage bar (mini progress bar inline)
    Actions: [Edit Quota] [Deactivate/Activate] [View →]
  
  Clicking [Edit Quota] opens QuotaEditorModal.

Create src/components/features/admin/QuotaEditorModal.tsx:
  Props: tenant: Tenant, quota: Quota, usage: ResourceUsage, open, onClose
  Title: "Edit Quota — {tenant.name}"
  Shows current usage context: "Currently using {usage.vcpu.used} of {quota.max_vcpu} vCPU"
  Form (React Hook Form + zodResolver(quotaUpdateSchema)):
    max_vcpu:    number input, min={usage.vcpu.used} (cannot reduce below current usage)
    max_ram_mb:  number input with helper "Current usage: {X} MB"
    max_disk_gb: number input with helper
    max_vms:     number input, min={usage.vms.used}
  Warning if reducing quota below current usage: red inline error
  Submit calls PATCH /admin/tenants/{id}/quota
  On success: invalidate tenant list + show toast "Quota updated for {tenant.name}"

Create src/pages/TenantDetailPage.tsx:
  Tenant info card (name, slug, owner, created_at, status)
  Quota card: 4 ResourceGauge components with current limits + usage
  Recent VMs table (tenant's VMs): same columns as VMListPage but read-only for admin
  Admin actions: [Edit Quota] [Deactivate Tenant]
```
</details>

---

### 3.3 [Dev-5] Admin VM Monitor + Audit Log
- [ ] **Demonstrates: Multi-tenancy (cross-tenant visibility for admin), Hypervisor** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/hooks/useAdmin.ts (useAdminVMs) and src/components/ui/VMStatusBadge.tsx.

Create src/pages/AdminVMListPage.tsx:
  Header: "All Virtual Machines" — shows VMs across ALL tenants
  Filter bar:
    - Tenant dropdown (All + list of tenants from useTenantList)
    - Status dropdown (All/Running/Stopped/Pending/Terminated)
    - Search by VM name
  
  Table columns:
    Tenant (colored badge with tenant name)
    VM Name (link to detail)
    VMStatusBadge
    vCPU | RAM (GB) | Disk (GB)
    IP Address
    Container ID (truncated to 12 chars, monospace font, tooltip with full ID)
    Created At
    Actions: Force Stop (admin can stop any VM) | Force Terminate

  Pagination: 20 items/page
  Summary row at top: "Showing {total} VMs across {tenant_count} tenants | {running} running"

Create src/pages/AuditLogPage.tsx:
  Uses GET /dashboard/activity (admin gets all tenants' logs via admin endpoint).
  Filters: Tenant | Action type (vm.create, vm.stop, etc.) | Date range (from/to datepicker)
  
  Table columns:
    Timestamp (formatted: "Mar 04, 2026 09:30:22")
    Tenant
    User (email)
    Action (colored badge: create=blue, delete=red, stop=orange, start=green)
    Resource Type + Resource ID (truncated UUID)
    Details (expandable JSON viewer inline)
  
  Export button: "Export CSV" — downloads filtered results as CSV file.
  Infinite scroll or pagination (20 items/page).
```
</details>

---

### 3.4 [Dev-5] Vitest + MSW Tests
- [ ] **Demonstrates: UI Quality, Test Coverage** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/components/ui/ResourceGauge.tsx, src/components/ui/VMStatusBadge.tsx,
src/lib/schemas/vm.schema.ts, src/pages/LoginPage.tsx.

Set up test infrastructure:
  Install: vitest, @testing-library/react, @testing-library/user-event, msw, @testing-library/jest-dom, jsdom
  Configure vite.config.ts: test: { environment: "jsdom", setupFiles: ["src/tests/setup.ts"] }
  Create src/tests/setup.ts: import '@testing-library/jest-dom'; setup MSW server with beforeAll/afterEach/afterAll

Create src/tests/msw/handlers.ts with MSW v2 http handlers:
  http.post("/auth/token") → returns mock Tokens
  http.get("/auth/me") → returns mock User
  http.get("/vms") → returns mock PaginatedVMs
  http.post("/vms") → on first call returns VMResponse, on second call returns 429 QuotaExceeded
  http.get("/dashboard/usage") → returns mock ResourceUsage (50% utilization)
  http.get("/admin/stats") → returns mock AdminStats

Tests to write:

  src/tests/components/ResourceGauge.test.tsx:
    - renders correct percentage text
    - progress bar is green when pct < 60
    - progress bar is yellow when 60 <= pct < 85
    - progress bar is red when pct >= 85
    - shows "Quota exceeded" badge when pct >= 100

  src/tests/components/VMStatusBadge.test.tsx:
    - renders "Running" with green class for status=running
    - renders "Stopped" for status=stopped
    - renders pulsing dot for status=pending

  src/tests/schemas/vm.schema.test.ts:
    - vmCreateSchema accepts valid: {name:"my-vm", vcpu:2, ram_mb:2048, disk_gb:50}
    - vmCreateSchema rejects vcpu=0, vcpu=33, ram_mb=256, disk_gb=5

  src/tests/pages/LoginPage.test.tsx (with MSW):
    - shows validation errors when submitted empty
    - shows error alert on 401 response
    - redirects to /dashboard on successful login

  src/tests/pages/DashboardPage.test.tsx:
    - renders 4 ResourceGauge components
    - shows StatCards with correct VM counts
    - shows "Quota Exceeded" banner when usage.pct = 100

Run: npm run test
```
</details>

---

### 3.5 [Dev-1] Final Polish, Dark Mode & CI/CD
- [ ] **Demonstrates: UI Quality** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read all page and layout components in src/.

1. Dark mode support:
   Create src/store/themeStore.ts (Zustand + persist):
     state: { theme: "light"|"dark" }
     toggle(): flips theme + applies class "dark" to document.documentElement
   Add sun/moon toggle button to Topbar.
   Ensure all Tailwind classes use dark: prefix variants for dark mode compatibility.
   shadcn/ui supports dark mode via .dark class on <html> automatically.

2. Responsive audit:
   - Mobile (375px): Sidebar hidden (drawer via Sheet from shadcn), hamburger in Topbar
   - Tablet (768px): Sidebar collapsed (icon-only, w-16), tooltips on icons
   - Desktop (1280px): Full sidebar (w-64)
   Create src/hooks/useSidebar.ts: { isOpen, isCollapsed, toggle, collapse }

3. Generate .env.example:
   VITE_API_URL=http://localhost:8000
   VITE_APP_NAME=CloudIaaS

4. Generate vite.config.ts build optimization:
   build.rollupOptions.output.manualChunks:
     "vendor-react": ["react", "react-dom", "react-router-dom"]
     "vendor-query": ["@tanstack/react-query"]
     "vendor-charts": ["recharts"]
     "vendor-ui": ["@radix-ui/...all radix packages"]

5. Generate .github/workflows/frontend-ci.yml:
   trigger: push/PR to main and dev
   jobs:
     ci:
       runs-on: ubuntu-latest
       steps:
         - checkout
         - node 20 setup
         - npm ci
         - npx tsc --noEmit          ← type check
         - npm run lint               ← eslint
         - npm run test -- --run      ← vitest
         - npm run build              ← vite build

6. Generate README_FRONTEND.md with:
   Project overview + tech badges
   Quick start: clone → cp .env.example .env → npm install → npm run dev
   Pages & routes table
   Architecture diagram (text-based)
   Environment variables table
   Available npm scripts
   Component structure explanation
   Deployment to Vercel (vercel.json: rewrites /* → /index.html)
```
</details>

---

## FINAL TASK — Generate Checklist README Files

> **COPILOT PROMPT:**
> ```
> Read README_BACKEND.md and README_FRONTEND.md in the project root.
> Read all source files in src/ to understand the current implementation state.
>
> Generate two files:
>
> 1. README_BACKEND.md — overwrite with full backend plan formatted as:
>    - Grouped by Day (### DAY 1, ### DAY 2, ### DAY 3)
>    - Each task as: - [ ] **[Dev-X] Task Title** | ⏱ Xh
>    - Under each task, a <details><summary>📎 Copilot Prompt</summary> block with the full prompt
>    - Each task must explicitly tag which of these it demonstrates:
>      🏢 Multi-tenancy | 🖥 Hypervisor | 📊 Resource Control | 🎨 UI Quality
>
> 2. README_FRONTEND.md — same format
>    - All tasks as checklists grouped by Day and Developer
>    - Each with estimated time and full Copilot prompt in <details> block
>    - Tag: 🏢 Multi-tenancy | 🖥 Hypervisor | 📊 Resource Control | 🎨 UI Quality
>
> At the top of each file include:
>   - Project description
>   - Tech stack table
>   - Architecture overview
>   - Team assignments
>   - Progress summary: X/Y tasks completed
> ```

---

## Component Architecture

```
src/
├── pages/
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx        ← ResourceGauge + StatCards + Activity
│   ├── VMListPage.tsx           ← VMTable + CreateVMModal (quota-aware)
│   ├── VMDetailPage.tsx         ← Lifecycle controls + Network attachment
│   ├── NetworkListPage.tsx
│   ├── ProfilePage.tsx          ← Quota usage tab
│   ├── AdminDashboardPage.tsx   ← Recharts: BarChart + PieChart
│   ├── TenantListPage.tsx       ← QuotaEditorModal
│   ├── AdminVMListPage.tsx      ← Cross-tenant VM monitor
│   └── AuditLogPage.tsx
├── components/
│   ├── ui/
│   │   ├── ResourceGauge.tsx    ← THE key component (colored progress + pct)
│   │   ├── VMStatusBadge.tsx    ← Pulsing dot + color per status
│   │   ├── StatCard.tsx
│   │   ├── ConfirmDialog.tsx
│   │   └── EmptyState.tsx
│   ├── features/
│   │   ├── vms/
│   │   │   ├── CreateVMModal.tsx  ← Live quota preview + disable on exceeded
│   │   │   └── VMTable.tsx
│   │   ├── networks/
│   │   ├── quotas/
│   │   │   └── QuotaSummaryCard.tsx
│   │   └── admin/
│   │       └── QuotaEditorModal.tsx
│   └── layout/
│       ├── Sidebar.tsx          ← Role-aware nav (admin section conditional)
│       ├── Topbar.tsx
│       └── AppLayout.tsx
├── hooks/
│   ├── useVMs.ts               ← quota-aware mutations with 429 handling
│   ├── useNetworks.ts
│   ├── useDashboard.ts         ← polling every 30s
│   └── useAdmin.ts
└── store/
    ├── authStore.ts            ← JWT + tenant_id + role
    └── themeStore.ts
```
