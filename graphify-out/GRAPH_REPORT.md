# Graph Report - 数据治理  (2026-07-19)

## Corpus Check
- 139 files · ~47,187 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1398 nodes · 2169 edges · 114 communities (95 shown, 19 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 135 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 106|Community 106]]
- [[_COMMUNITY_Community 107|Community 107]]

## God Nodes (most connected - your core abstractions)
1. `cn()` - 270 edges
2. `AuditService` - 45 edges
3. `MaterialValidator` - 33 edges
4. `DuplicateDetector` - 24 edges
5. `compilerOptions` - 22 edges
6. `CodeGenerator` - 21 edges
7. `compilerOptions` - 18 edges
8. `Button()` - 15 edges
9. `TestApplicationEndpoints` - 13 edges
10. `get_application()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `upload_application_attachment()` --calls--> `AuditService`  [INFERRED]
  backend/app/api/applications.py → backend/app/services/audit_service.py
- `create_application()` --calls--> `AuditService`  [INFERRED]
  backend/app/api/applications.py → backend/app/services/audit_service.py
- `save_draft()` --calls--> `AuditService`  [INFERRED]
  backend/app/api/applications.py → backend/app/services/audit_service.py
- `submit_application()` --calls--> `AuditService`  [INFERRED]
  backend/app/api/applications.py → backend/app/services/audit_service.py
- `submit_application()` --calls--> `CodeGenerator`  [INFERRED]
  backend/app/api/applications.py → backend/app/services/code_generator.py

## Import Cycles
- None detected.

## Communities (114 total, 19 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (66): Layout(), api(), downloadFile(), getToken(), getUser(), login(), logout(), setAuth() (+58 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (40): cn(), AccordionContent(), AccordionItem(), AccordionTrigger(), Avatar(), AvatarFallback(), AvatarImage(), BreadcrumbEllipsis() (+32 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (40): useIsMobile(), Sheet(), SheetContent(), SheetDescription(), SheetFooter(), SheetHeader(), SheetOverlay(), SheetTitle() (+32 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (48): dependencies, class-variance-authority, clsx, cmdk, date-fns, embla-carousel-react, @hookform/resolvers, input-otp (+40 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (27): DuplicateDetector, Duplicate detection service - optimized with database-level similarity., Detect duplicate materials using database-level similarity queries., Unit tests for DuplicateDetector service., TC-DEDUP-013: Obsolete records should not match., TC-DEDUP-001: Empty database should return no duplicates., Test partial/prefix matching., TC-DEDUP-020: Partial match with high word overlap should be flagged. (+19 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (25): CodeGenerator, Material code generation engine., Generate material codes based on rules., Generate a unique material code., Generate default code when no rule matches., Get parent classification code., Unit tests for CodeGenerator service., TC-CODE-013: Sequence numbers should be zero-padded. (+17 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (39): ApplicationStatus, AttributeTemplate, AuditLog, ExternalSystemLog, GoldenRecord, GoldenRecordStatus, MaterialType, SQLAlchemy models for Material Master Data Governance. (+31 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (37): create_application(), create_attribute_template(), create_audit_log(), create_classification(), create_code_rule(), create_external_log(), create_golden_record(), generate_app_no() (+29 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (29): get_me(), login(), FastAPI main application entry point., Authenticate user and return JWT token.          Request body: {"user_id": "us, Get current authenticated user info., create_access_token(), admin_client(), client() (+21 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (19): AuditService, Audit service for full-chain traceability., Generate step ID: SQ-2026-00001-S1, Create an audit log entry., Get full audit trace for an application., Record every step of the material lifecycle., Test audit trace endpoints., TC-API-050: Get audit trace for application. (+11 more)

### Community 10 - "Community 10"
Cohesion: 0.11
Nodes (24): admin_approve(), create_application(), dept_approve(), download_application_attachment(), get_application(), get_application_audit(), list_applications(), publish_application() (+16 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (24): compilerOptions, allowImportingTsExtensions, baseUrl, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+16 more)

### Community 12 - "Community 12"
Cohesion: 0.09
Nodes (18): AlertDialogAction(), AlertDialogCancel(), AlertDialogContent(), AlertDialogDescription(), AlertDialogFooter(), AlertDialogHeader(), AlertDialogOverlay(), AlertDialogTitle() (+10 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (9): Checkbox(), HoverCardContent(), PopoverContent(), Progress(), ResizableHandle(), ResizablePanelGroup(), Slider(), Spinner() (+1 more)

### Community 14 - "Community 14"
Cohesion: 0.09
Nodes (12): Test application lifecycle API endpoints., TC-API-020: Create new application draft., TC-API-021: List applications., TC-API-022: Get specific application., TC-API-023: Save draft updates fields., TC-API-024: Saving non-draft application should fail., TC-API-025: Submit draft application., TC-API-026: Submit non-draft should fail. (+4 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (15): Command(), CommandDialog(), CommandGroup(), CommandInput(), CommandItem(), CommandList(), CommandSeparator(), CommandShortcut() (+7 more)

### Community 16 - "Community 16"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, @babel/plugin-proposal-decorators, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals (+12 more)

### Community 17 - "Community 17"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 18 - "Community 18"
Cohesion: 0.13
Nodes (17): ButtonGroup(), ButtonGroupSeparator(), ButtonGroupText(), buttonGroupVariants, Item(), ItemActions(), ItemContent(), ItemDescription() (+9 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (18): aliases, components, hooks, lib, ui, utils, iconLibrary, registries (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.17
Nodes (17): Namespace, Path, build_url(), extract_token(), main(), mask_token(), parse_args(), Configure OpenMetadata connection settings for the local backend.  Examples: (+9 more)

### Community 21 - "Community 21"
Cohesion: 0.11
Nodes (10): Test application CRUD operations., TC-CRUD-001: Create application generates app_no., TC-CRUD-002: Get application by ID., TC-CRUD-003: Non-existent application returns None., TC-CRUD-004: Update application fields., TC-CRUD-005: Update non-existent returns None., TC-CRUD-006: List applications with pagination., TC-CRUD-007: Filter applications by status. (+2 more)

### Community 22 - "Community 22"
Cohesion: 0.12
Nodes (11): Menubar(), MenubarCheckboxItem(), MenubarContent(), MenubarItem(), MenubarLabel(), MenubarRadioItem(), MenubarSeparator(), MenubarShortcut() (+3 more)

### Community 23 - "Community 23"
Cohesion: 0.12
Nodes (9): ContextMenuCheckboxItem(), ContextMenuContent(), ContextMenuItem(), ContextMenuLabel(), ContextMenuRadioItem(), ContextMenuSeparator(), ContextMenuShortcut(), ContextMenuSubContent() (+1 more)

### Community 24 - "Community 24"
Cohesion: 0.12
Nodes (9): DropdownMenuCheckboxItem(), DropdownMenuContent(), DropdownMenuItem(), DropdownMenuLabel(), DropdownMenuRadioItem(), DropdownMenuSeparator(), DropdownMenuShortcut(), DropdownMenuSubContent() (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.18
Nodes (9): MaterialValidator, Validate material application data., TC-VAL-001: All required fields should pass., TC-VAL-002: Missing material_name should fail., TC-VAL-003: Missing classification_id should fail., TC-VAL-004: Missing material_type should fail., TC-VAL-005: All missing fields should produce multiple errors., Test validation of required fields. (+1 more)

### Community 26 - "Community 26"
Cohesion: 0.18
Nodes (9): Dependency factory to enforce role-based access., require_role(), Test RBAC role requirements., TC-AUTH-040: Applicant can access applicant endpoints., TC-AUTH-041: Admin can access admin endpoints., TC-AUTH-042: User with any allowed role should pass., TC-AUTH-044: User without allowed role should raise HTTPException., TC-AUTH-043: Predefined role checkers exist. (+1 more)

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (8): TC-API-014: Get attribute templates for classification., Test classification API endpoints., TC-API-010: List classifications returns tree structure., TC-API-011: Get specific classification., TC-API-012: Non-existent classification returns 404., TC-API-013: Create new classification., TC-API-013B: Create and filter a level-3 classification., TestClassificationEndpoints

### Community 28 - "Community 28"
Cohesion: 0.19
Nodes (13): Carousel(), CarouselApi, CarouselContent(), CarouselContext, CarouselContextProps, CarouselItem(), CarouselNext(), CarouselOptions (+5 more)

### Community 29 - "Community 29"
Cohesion: 0.15
Nodes (12): 关键入口 / 核心模块, 前端, 后端, 常见问题和预防, 技术栈, 用户偏好与长期约束, 登录凭据, 目录结构 (+4 more)

### Community 30 - "Community 30"
Cohesion: 0.15
Nodes (7): Any, Publish material to mock BTP., Rollback a published material., Check mock BTP health., Check for duplicate materials.                  Uses database ILIKE query inst, Run all validation checks., Run data quality tests via OpenMetadata.

### Community 31 - "Community 31"
Cohesion: 0.15
Nodes (12): Execution Handoff, Global Constraints, MDM Governance 构建修复与工程基线实施计划, Self-Review, Task 1: 创建 `src/lib/utils.ts`（shadcn/ui 基础工具）, Task 2: 创建 `src/lib/api.ts`（前端 API 客户端）, Task 3: 修复后端默认环境变量, Task 4: 重写 `README.md` (+4 more)

### Community 32 - "Community 32"
Cohesion: 0.15
Nodes (13): RalphLoop MDM Governance — 制造业物料主数据治理平台, 主数据治理流程, 发布流程, 待办, 快速导航, 技术栈一览, 提交自动执行链, 核心模块 (+5 more)

### Community 33 - "Community 33"
Cohesion: 0.17
Nodes (11): create_classification(), create_template(), get_classification(), get_templates(), list_classifications(), Classification and Attribute Template API., List all material classifications., Get a classification by ID. (+3 more)

### Community 34 - "Community 34"
Cohesion: 0.20
Nodes (9): btp_mock_health(), dashboard(), health_check(), Dashboard and health API., Get dashboard statistics., BTP Mock service health., BTPMockService, Mock BTP publish service (Phase 2.2). (+1 more)

### Community 35 - "Community 35"
Cohesion: 0.17
Nodes (7): Test audit trace retrieval., TC-AUDIT-010: Empty trace should return empty list., TC-AUDIT-011: Trace should return all logs in order., TC-AUDIT-012: Each trace entry should have required fields., TC-AUDIT-013: executed_at should be ISO format string., TC-AUDIT-014: Trace should only return logs for specified application., TestAuditTraceRetrieval

### Community 36 - "Community 36"
Cohesion: 0.17
Nodes (7): Test atomic sequence increment - critical for preventing duplicate codes., TC-CRUD-010: Basic sequence increment., TC-CRUD-011: Sequence should start positive., TC-CRUD-012: Invalid rule ID should return 0., TC-CRUD-013: Sequence should persist across operations., TC-CRUD-014: Concurrent increments should produce unique values., TestIncrementSeqAtomicity

### Community 37 - "Community 37"
Cohesion: 0.23
Nodes (10): FormControl(), FormDescription(), FormFieldContext, FormFieldContextValue, FormItem(), FormItemContext, FormItemContextValue, FormLabel() (+2 more)

### Community 38 - "Community 38"
Cohesion: 0.24
Nodes (7): authenticate_user(), Test full authentication flow., TC-AUTH-020: Valid credentials return user dict., TC-AUTH-021: Wrong password returns None., TC-AUTH-022: Non-existent user returns None., TC-AUTH-023: Empty credentials return None., TestAuthentication

### Community 39 - "Community 39"
Cohesion: 0.24
Nodes (7): verify_password(), Test bcrypt password hashing and verification., TC-AUTH-001: Correct password should verify successfully., TC-AUTH-002: Wrong password should fail verification., TC-AUTH-003: Empty password should fail verification., TC-AUTH-004: All mock users must have valid bcrypt hashes., TestPasswordVerification

### Community 40 - "Community 40"
Cohesion: 0.18
Nodes (10): 1. TypeScript compile check, 2. Production build, Commit Attempt, Existing commit containing this file, Files Changed, Issues / Concerns, Self-Review, Task 2 Report: Create `src/lib/api.ts` (+2 more)

### Community 41 - "Community 41"
Cohesion: 0.22
Nodes (6): OpenMetadataSync, OpenMetadata synchronization service., Check OpenMetadata connection., Sync Golden Records to OpenMetadata., Make API call to OpenMetadata., Sync a material to OpenMetadata.

### Community 42 - "Community 42"
Cohesion: 0.22
Nodes (8): ChartConfig, ChartContainer(), ChartContext, ChartContextProps, ChartLegendContent(), ChartTooltipContent(), THEMES, useChart()

### Community 43 - "Community 43"
Cohesion: 0.18
Nodes (6): DrawerContent(), DrawerDescription(), DrawerFooter(), DrawerHeader(), DrawerOverlay(), DrawerTitle()

### Community 44 - "Community 44"
Cohesion: 0.20
Nodes (9): name, private, scripts, build, dev, lint, preview, type (+1 more)

### Community 45 - "Community 45"
Cohesion: 0.20
Nodes (6): TC-API-001: Successful login returns token., TC-API-002: Wrong password returns 401., TC-API-003: Non-existent user returns 401., TC-API-004: /api/auth/me with valid token returns user., Test authentication API endpoints., TestAuthEndpoints

### Community 46 - "Community 46"
Cohesion: 0.20
Nodes (6): Test approval workflow endpoints., TC-API-030: Admin approves application., TC-API-031: Admin rejects application., TC-API-032: Department approves application., TC-API-033: Approve application in wrong status should fail., TestApprovalEndpoints

### Community 47 - "Community 47"
Cohesion: 0.20
Nodes (6): Test authorization - role-based access control., TC-API-080: Applicant cannot access admin approval., TC-API-081: Applicant cannot publish., TC-API-082: Admin can access applicant endpoints., TC-API-083: Request without token in non-DEV mode behavior., TestAuthorization

### Community 48 - "Community 48"
Cohesion: 0.20
Nodes (6): Unit tests for AuditService., Test label mapping completeness., TC-AUDIT-020: All StepName enum values should have labels., TC-AUDIT-021: All status values should have labels., TC-AUDIT-022: Unknown step name should use the raw name as label., TestAuditServiceLabels

### Community 49 - "Community 49"
Cohesion: 0.20
Nodes (6): Unit tests for authentication and authorization., Test role hierarchy - admin can access applicant endpoints., TC-AUTH-050: Admin role is included in applicant allowed roles., TC-AUTH-051: data_admin can access admin endpoints., TC-AUTH-052: dept_approver can access approver endpoints., TestRoleHierarchy

### Community 50 - "Community 50"
Cohesion: 0.20
Nodes (6): TC-VAL-013: Name of exactly 200 chars should pass., Test material name length validation., TC-VAL-010: Name shorter than 5 chars should fail., TC-VAL-011: Name of exactly 5 chars should pass., TC-VAL-012: Name longer than 200 chars should fail., TestMaterialValidatorNameLength

### Community 51 - "Community 51"
Cohesion: 0.20
Nodes (6): Test attribute template validation., TC-VAL-040: Missing required attribute should fail., TC-VAL-041: All required attributes present should pass., TC-VAL-042: Missing optional attribute should not fail., TC-VAL-043: One required attribute missing should fail., TestMaterialValidatorAttributes

### Community 52 - "Community 52"
Cohesion: 0.20
Nodes (6): Test validation result structure., TC-VAL-050: Result should have passed, checks, errors keys., TC-VAL-051: Each check should have check, passed, message keys., TC-VAL-052: passed should be True iff errors is empty., TC-VAL-053: passed should be False when errors exist., TestMaterialValidatorCheckStructure

### Community 53 - "Community 53"
Cohesion: 0.22
Nodes (9): NavigationMenu(), NavigationMenuContent(), NavigationMenuIndicator(), NavigationMenuItem(), NavigationMenuLink(), NavigationMenuList(), NavigationMenuTrigger(), navigationMenuTriggerStyle (+1 more)

### Community 54 - "Community 54"
Cohesion: 0.28
Nodes (6): get_user(), Test user retrieval from mock database., TC-AUTH-010: Retrieve existing user by ID., TC-AUTH-011: Non-existent user should return None., TC-AUTH-012: User lookup should be case-sensitive., TestUserLookup

### Community 55 - "Community 55"
Cohesion: 0.22
Nodes (8): Commit, Files changed, Issues or concerns, Self-review findings, Task 1 Report: Create `src/lib/utils.ts`, Test results, What was implemented, What was tested

### Community 56 - "Community 56"
Cohesion: 0.25
Nodes (5): Integration tests for API endpoints using TestClient., Test Golden Record endpoints., TC-API-060: List golden records., TC-API-061: Get specific golden record., TestGoldenRecordEndpoints

### Community 57 - "Community 57"
Cohesion: 0.25
Nodes (5): Test publish workflow endpoints., TC-API-040: Publish approved application., TC-API-041: Publish unapproved application should fail., TC-API-042: Publish nonexistent application should 404., TestPublishEndpoints

### Community 58 - "Community 58"
Cohesion: 0.25
Nodes (5): Test dashboard and health endpoints., TC-API-070: Dashboard returns statistics., TC-API-071: Health check returns system status., TC-API-072: BTP mock health endpoint., TestDashboardEndpoints

### Community 59 - "Community 59"
Cohesion: 0.25
Nodes (5): Unit tests for CRUD operations - focus on atomicity and correctness., Test audit log CRUD operations., TC-CRUD-030: Create audit log entry., TC-CRUD-031: Get audit logs for application., TestAuditLogCRUD

### Community 60 - "Community 60"
Cohesion: 0.25
Nodes (5): Test Golden Record CRUD operations., TC-CRUD-020: Create golden record., TC-CRUD-021: Get golden record by material code., TC-CRUD-022: Update golden record fields., TestGoldenRecordCRUD

### Community 61 - "Community 61"
Cohesion: 0.25
Nodes (5): Unit tests for MaterialValidator service., Test classification existence validation., TC-VAL-020: Existing classification should pass., TC-VAL-021: Non-existent classification should fail., TestMaterialValidatorClassification

### Community 62 - "Community 62"
Cohesion: 0.25
Nodes (5): Test material type validation., TC-VAL-030: Valid type 'raw' should pass., TC-VAL-031: All valid types should pass., TC-VAL-032: Invalid type should fail., TestMaterialValidatorType

### Community 63 - "Community 63"
Cohesion: 0.29
Nodes (7): Empty(), EmptyContent(), EmptyDescription(), EmptyHeader(), EmptyMedia(), emptyMediaVariants, EmptyTitle()

### Community 64 - "Community 64"
Cohesion: 0.29
Nodes (6): get_golden_record(), get_golden_record_by_code(), list_golden_records(), List all Golden Records with pagination., Get a Golden Record by ID., Get a Golden Record by material code.

### Community 65 - "Community 65"
Cohesion: 0.29
Nodes (6): coze-preview-run.sh script, BTP_ENABLED, ENV, OM_ENABLED, PORT, SQLALCHEMY_DATABASE_URL

### Community 66 - "Community 66"
Cohesion: 0.29
Nodes (5): 一、结构全景, 七、架构决策, 九、待办事项与技术债务, 制造业物料主数据治理平台 · 代码资产知识图谱, 十、文档分层

### Community 67 - "Community 67"
Cohesion: 0.29
Nodes (6): compilerOptions, baseUrl, paths, files, @/*, references

### Community 68 - "Community 68"
Cohesion: 0.43
Nodes (5): ToggleGroup(), ToggleGroupContext, ToggleGroupItem(), Toggle(), toggleVariants

### Community 69 - "Community 69"
Cohesion: 0.47
Nodes (5): _classification_path(), get_metadata_governance_overview(), _latest_log(), Metadata governance API for catalog, lineage, quality, and traceability views., Return a dashboard-friendly metadata governance overview.

### Community 70 - "Community 70"
Cohesion: 0.40
Nodes (5): ensure_schema_compatibility(), Small startup schema compatibility fixes for local demo databases., Backfill a few level-3 demo classes for existing two-level local data., Add columns that Base.metadata.create_all cannot add to existing tables., seed_demo_three_level_classifications()

### Community 71 - "Community 71"
Cohesion: 0.33
Nodes (5): coze-deploy-build.sh script, BTP_ENABLED, ENV, OM_ENABLED, SQLALCHEMY_DATABASE_URL

### Community 72 - "Community 72"
Cohesion: 0.33
Nodes (5): coze-deploy-run.sh script, BTP_ENABLED, ENV, OM_ENABLED, SQLALCHEMY_DATABASE_URL

### Community 73 - "Community 73"
Cohesion: 0.33
Nodes (5): coze-preview-build.sh script, BTP_ENABLED, ENV, OM_ENABLED, SQLALCHEMY_DATABASE_URL

### Community 74 - "Community 74"
Cohesion: 0.33
Nodes (4): Test metadata governance overview endpoints., TC-API-073: Metadata governance overview returns all sections., TC-API-074: Overview includes catalog, lineage, and trace data., TestMetadataGovernanceEndpoints

### Community 75 - "Community 75"
Cohesion: 0.33
Nodes (5): test_extract_token_finds_nested_common_keys(), test_normalize_host_accepts_ui_and_api_urls(), test_write_env_values_preserves_and_updates(), normalize_host(), Normalize OpenMetadata UI/API URL to the API base URL.

### Community 76 - "Community 76"
Cohesion: 0.33
Nodes (4): Test dashboard statistics., TC-CRUD-040: Empty database stats should reflect seeded data., TC-CRUD-041: Stats should reflect actual data., TestDashboardStats

### Community 77 - "Community 77"
Cohesion: 0.40
Nodes (4): get_current_user(), Authentication and authorization middleware., Extract and validate current user from JWT token., HTTPAuthorizationCredentials

### Community 78 - "Community 78"
Cohesion: 0.40
Nodes (5): 2.1 入口与路由, 2.2 路由表, 2.3 组件与工具, 2.4 页面功能矩阵, 二、前端资产 (src/)

### Community 79 - "Community 79"
Cohesion: 0.40
Nodes (5): 3.1 入口与核心配置, 3.2 API 路由 (backend/app/api/), 3.3 业务服务 (backend/app/services/), 3.4 测试 (backend/tests/), 三、后端资产 (backend/)

### Community 80 - "Community 80"
Cohesion: 0.40
Nodes (5): 5.1 认证（定义于 main.py）, 5.2 物料申请（/api/applications）, 5.3 分类（/api/classifications）, 5.4 仪表盘 / Golden Record / 元数据治理, 五、API 端点清单

### Community 81 - "Community 81"
Cohesion: 0.40
Nodes (5): 6.1 页面 → API → 服务, 6.2 状态机（ApplicationStatus）, 6.3 提交事务（原子操作）, 6.4 发布流程, 六、端到端映射

### Community 82 - "Community 82"
Cohesion: 0.40
Nodes (5): 八、运行指南, 前端开发, 后端开发, 开发环境, 登录凭据

### Community 83 - "Community 83"
Cohesion: 0.50
Nodes (4): headers(), login(), Authenticate and get JWT token., test()

### Community 84 - "Community 84"
Cohesion: 0.40
Nodes (5): 前端, 前置条件, 后端, 快速启动, 访问入口

### Community 85 - "Community 85"
Cohesion: 0.50
Nodes (4): Alert(), AlertDescription(), AlertTitle(), alertVariants

### Community 86 - "Community 86"
Cohesion: 0.50
Nodes (4): 4.1 实体关系, 4.2 表清单（7 张）, 4.3 枚举, 四、数据模型

## Knowledge Gaps
- **272 isolated node(s):** `Settings`, `$schema`, `style`, `rsc`, `tsx` (+267 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AuditService` connect `Community 9` to `Community 35`, `Community 10`, `Community 74`, `Community 45`, `Community 46`, `Community 14`, `Community 47`, `Community 48`, `Community 56`, `Community 57`, `Community 58`, `Community 27`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `submit_application()` connect `Community 10` to `Community 4`, `Community 5`, `Community 7`, `Community 9`, `Community 25`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `cn()` connect `Community 1` to `Community 0`, `Community 2`, `Community 68`, `Community 37`, `Community 42`, `Community 43`, `Community 12`, `Community 13`, `Community 15`, `Community 18`, `Community 85`, `Community 22`, `Community 23`, `Community 24`, `Community 53`, `Community 28`, `Community 63`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Are the 39 inferred relationships involving `AuditService` (e.g. with `admin_approve()` and `create_application()`) actually correct?**
  _`AuditService` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `MaterialValidator` (e.g. with `submit_application()` and `TestMaterialValidatorAttributes`) actually correct?**
  _`MaterialValidator` has 29 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Material Application API - Full lifecycle management with auth and transactions.`, `List material applications with optional filters.`, `Get application details.` to the rest of the system?**
  _553 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.053465346534653464 - nodes in this community are weakly interconnected._