"""
test_call_graph_enterprise.py - 100 Enterprise Product-Oriented Test Cases for CallGraphTracer.
Mimics complex, production-grade microservice codebases across 10 industry domains:
1. Fintech & Core Payment Processing (Tests 101 to 110)
2. E-Commerce & Fulfillment Pipeline (Tests 111 to 120)
3. Multi-Tenant SaaS & RBAC Security (Tests 121 to 130)
4. Ride-Sharing & Geospatial Dispatch (Tests 131 to 140)
5. Healthcare & Telehealth Portal (HIPAA) (Tests 141 to 150)
6. Content Streaming & Social Feed Architecture (Tests 151 to 160)
7. Cloud Infrastructure & DevOps Orchestration (Tests 161 to 170)
8. Customer Support & CRM Ticketing (Tests 171 to 180)
9. Data Engineering & Analytics Pipeline (Tests 181 to 190)
10. IoT Fleet & Device Telemetry (Tests 191 to 200)
"""
from app.slicing.call_graph import CallGraphTracer
from app.schemas.slice import CodeSymbol, ImportStatement, SymbolKind


def _make_symbol(
    file_path: str,
    name: str,
    qualified_name: str | None = None,
    kind: SymbolKind = SymbolKind.FUNCTION,
    outgoing_calls: list[str] | None = None,
    line_start: int = 1,
    line_end: int = 10,
) -> CodeSymbol:
    q_name = qualified_name or name
    return CodeSymbol(
        symbol_id=f"{file_path}:{q_name}",
        name=name,
        qualified_name=q_name,
        kind=kind,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        source_code=f"def {name}(): pass",
        outgoing_calls=outgoing_calls or [],
    )


# ============================================================================
# DOMAIN 1: Fintech & Core Payment Processing (Tests 101 to 110)
# ============================================================================

def test_101_idempotent_payment_intent_creation():
    route = _make_symbol("payments/api.py", "create_intent", kind=SymbolKind.ROUTE, outgoing_calls=["self.service.create_intent"])
    svc_cls = _make_symbol("payments/service.py", "PaymentIntentService", kind=SymbolKind.CLASS)
    svc_m = _make_symbol("payments/service.py", "create_intent", "PaymentIntentService.create_intent", SymbolKind.METHOD, outgoing_calls=["self.idempotency.check", "self.vault.tokenize", "self.repo.save"])
    idem_m = _make_symbol("payments/idempotency.py", "check", "IdempotencyService.check", SymbolKind.METHOD)
    vault_m = _make_symbol("payments/vault.py", "tokenize", "CardVault.tokenize", SymbolKind.METHOD)
    repo_m = _make_symbol("payments/repo.py", "save", "PaymentIntentRepo.save", SymbolKind.METHOD)

    imports = {
        "payments/api.py": [ImportStatement(source_module="payments.service", imported_names=["PaymentIntentService"], is_from=True)],
        "payments/service.py": [
            ImportStatement(source_module="payments.idempotency", imported_names=["IdempotencyService"], is_from=True),
            ImportStatement(source_module="payments.vault", imported_names=["CardVault"], is_from=True),
            ImportStatement(source_module="payments.repo", imported_names=["PaymentIntentRepo"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([route, svc_cls, svc_m, idem_m, vault_m, repo_m], imports)
    assert svc_m.symbol_id in graph[route.symbol_id]
    assert idem_m.symbol_id in graph[svc_m.symbol_id]
    assert vault_m.symbol_id in graph[svc_m.symbol_id]
    assert repo_m.symbol_id in graph[svc_m.symbol_id]


def test_102_two_phase_commit_capture():
    caller = _make_symbol("payments/capture.py", "capture_authorized", outgoing_calls=["self.gateway.capture", "self.ledger.record_entry"])
    gw_m = _make_symbol("payments/gateway.py", "capture", "PaymentGateway.capture", SymbolKind.METHOD)
    led_m = _make_symbol("payments/ledger.py", "record_entry", "LedgerService.record_entry", SymbolKind.METHOD)
    imports = {
        "payments/capture.py": [
            ImportStatement(source_module="payments.gateway", imported_names=["PaymentGateway"], is_from=True),
            ImportStatement(source_module="payments.ledger", imported_names=["LedgerService"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, gw_m, led_m], imports)
    assert gw_m.symbol_id in graph[caller.symbol_id]
    assert led_m.symbol_id in graph[caller.symbol_id]


def test_103_double_entry_bookkeeping_balancing():
    caller = _make_symbol("ledger/engine.py", "post_transaction", outgoing_calls=["self.validator.verify_balance", "self.journal.append_batch"])
    val_m = _make_symbol("ledger/validator.py", "verify_balance", "BalanceValidator.verify_balance", SymbolKind.METHOD)
    jrnl_m = _make_symbol("ledger/journal.py", "append_batch", "JournalRepo.append_batch", SymbolKind.METHOD)
    imports = {
        "ledger/engine.py": [
            ImportStatement(source_module="ledger.validator", imported_names=["BalanceValidator"], is_from=True),
            ImportStatement(source_module="ledger.journal", imported_names=["JournalRepo"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, val_m, jrnl_m], imports)
    assert val_m.symbol_id in graph[caller.symbol_id]
    assert jrnl_m.symbol_id in graph[caller.symbol_id]


def test_104_three_d_secure_webhook_signature():
    webhook = _make_symbol("webhooks/stripe.py", "handle_3ds_callback", kind=SymbolKind.ROUTE, outgoing_calls=["verify_signature", "self.orders.fulfill"])
    sig_fn = _make_symbol("webhooks/crypto.py", "verify_signature")
    fulfill_m = _make_symbol("orders/service.py", "fulfill", "OrderFulfillmentService.fulfill", SymbolKind.METHOD)
    imports = {
        "webhooks/stripe.py": [
            ImportStatement(source_module="webhooks.crypto", imported_names=["verify_signature"], is_from=True),
            ImportStatement(source_module="orders.service", imported_names=["OrderFulfillmentService"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([webhook, sig_fn, fulfill_m], imports)
    assert sig_fn.symbol_id in graph[webhook.symbol_id]
    assert fulfill_m.symbol_id in graph[webhook.symbol_id]


def test_105_refund_cascade_with_fee_reversal():
    caller = _make_symbol("refunds/processor.py", "process_refund", outgoing_calls=["self.acquirer.refund", "self.platform_fee.reverse"])
    acq_m = _make_symbol("acquirer/client.py", "refund", "AcquirerClient.refund", SymbolKind.METHOD)
    fee_m = _make_symbol("billing/fee.py", "reverse", "PlatformFeeManager.reverse", SymbolKind.METHOD)
    imports = {
        "refunds/processor.py": [
            ImportStatement(source_module="acquirer.client", imported_names=["AcquirerClient"], is_from=True),
            ImportStatement(source_module="billing.fee", imported_names=["PlatformFeeManager"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, acq_m, fee_m], imports)
    assert acq_m.symbol_id in graph[caller.symbol_id]
    assert fee_m.symbol_id in graph[caller.symbol_id]


def test_106_card_vault_tokenization_and_pci_sanitization():
    caller = _make_symbol("vault/tokenizer.py", "tokenize_card", outgoing_calls=["sanitize_pan", "self.kms.encrypt_data"])
    san_fn = _make_symbol("vault/sanitizer.py", "sanitize_pan")
    kms_m = _make_symbol("security/kms.py", "encrypt_data", "KmsClient.encrypt_data", SymbolKind.METHOD)
    imports = {
        "vault/tokenizer.py": [
            ImportStatement(source_module="vault.sanitizer", imported_names=["sanitize_pan"], is_from=True),
            ImportStatement(source_module="security.kms", imported_names=["KmsClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, san_fn, kms_m], imports)
    assert san_fn.symbol_id in graph[caller.symbol_id]
    assert kms_m.symbol_id in graph[caller.symbol_id]


def test_107_fx_currency_conversion_spread():
    caller = _make_symbol("fx/converter.py", "convert_currency", outgoing_calls=["self.rates.get_spot_rate", "self.spread.apply_markup"])
    rate_m = _make_symbol("fx/rates.py", "get_spot_rate", "RateProvider.get_spot_rate", SymbolKind.METHOD)
    spread_m = _make_symbol("fx/spread.py", "apply_markup", "SpreadCalculator.apply_markup", SymbolKind.METHOD)
    imports = {
        "fx/converter.py": [
            ImportStatement(source_module="fx.rates", imported_names=["RateProvider"], is_from=True),
            ImportStatement(source_module="fx.spread", imported_names=["SpreadCalculator"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, rate_m, spread_m], imports)
    assert rate_m.symbol_id in graph[caller.symbol_id]
    assert spread_m.symbol_id in graph[caller.symbol_id]


def test_108_fraud_risk_scoring_pipeline():
    caller = _make_symbol("fraud/engine.py", "evaluate_risk", outgoing_calls=["self.velocity.check_frequency", "self.geo.check_impossible_travel"])
    velo_m = _make_symbol("fraud/velocity.py", "check_frequency", "VelocityRule.check_frequency", SymbolKind.METHOD)
    geo_m = _make_symbol("fraud/geo.py", "check_impossible_travel", "GeoIpRule.check_impossible_travel", SymbolKind.METHOD)
    imports = {
        "fraud/engine.py": [
            ImportStatement(source_module="fraud.velocity", imported_names=["VelocityRule"], is_from=True),
            ImportStatement(source_module="fraud.geo", imported_names=["GeoIpRule"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, velo_m, geo_m], imports)
    assert velo_m.symbol_id in graph[caller.symbol_id]
    assert geo_m.symbol_id in graph[caller.symbol_id]


def test_109_dispute_evidence_submission():
    caller = _make_symbol("disputes/manager.py", "submit_evidence", outgoing_calls=["self.s3.upload_pdf", "self.gateway.send_dispute_packet"])
    s3_m = _make_symbol("storage/s3.py", "upload_pdf", "S3Storage.upload_pdf", SymbolKind.METHOD)
    gw_m = _make_symbol("disputes/gateway.py", "send_dispute_packet", "DisputeGateway.send_dispute_packet", SymbolKind.METHOD)
    imports = {
        "disputes/manager.py": [
            ImportStatement(source_module="storage.s3", imported_names=["S3Storage"], is_from=True),
            ImportStatement(source_module="disputes.gateway", imported_names=["DisputeGateway"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, s3_m, gw_m], imports)
    assert s3_m.symbol_id in graph[caller.symbol_id]
    assert gw_m.symbol_id in graph[caller.symbol_id]


def test_110_merchant_settlement_batch():
    caller = _make_symbol("settlement/cron.py", "run_daily_settlement", outgoing_calls=["self.ledger.calculate_net", "self.ach.initiate_transfer"])
    led_m = _make_symbol("ledger/calculator.py", "calculate_net", "LedgerCalculator.calculate_net", SymbolKind.METHOD)
    ach_m = _make_symbol("banking/ach.py", "initiate_transfer", "AchService.initiate_transfer", SymbolKind.METHOD)
    imports = {
        "settlement/cron.py": [
            ImportStatement(source_module="ledger.calculator", imported_names=["LedgerCalculator"], is_from=True),
            ImportStatement(source_module="banking.ach", imported_names=["AchService"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, led_m, ach_m], imports)
    assert led_m.symbol_id in graph[caller.symbol_id]
    assert ach_m.symbol_id in graph[caller.symbol_id]


# ============================================================================
# DOMAIN 2: E-Commerce & Fulfillment Pipeline (Tests 111 to 120)
# ============================================================================

def test_111_order_checkout_cart_validation():
    caller = _make_symbol("checkout/service.py", "validate_cart", outgoing_calls=["self.catalog.verify_items_exist", "self.pricing.recalculate_totals"])
    cat_m = _make_symbol("catalog/service.py", "verify_items_exist", "CatalogService.verify_items_exist", SymbolKind.METHOD)
    price_m = _make_symbol("pricing/engine.py", "recalculate_totals", "PricingEngine.recalculate_totals", SymbolKind.METHOD)
    imports = {
        "checkout/service.py": [
            ImportStatement(source_module="catalog.service", imported_names=["CatalogService"], is_from=True),
            ImportStatement(source_module="pricing.engine", imported_names=["PricingEngine"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, cat_m, price_m], imports)
    assert cat_m.symbol_id in graph[caller.symbol_id]
    assert price_m.symbol_id in graph[caller.symbol_id]


def test_112_tiered_coupon_evaluator():
    caller = _make_symbol("promos/evaluator.py", "apply_coupon", outgoing_calls=["self.coupons.find_by_code", "self.rules.evaluate_eligibility"])
    coup_m = _make_symbol("promos/repo.py", "find_by_code", "CouponRepo.find_by_code", SymbolKind.METHOD)
    rule_m = _make_symbol("promos/rules.py", "evaluate_eligibility", "CouponRuleEngine.evaluate_eligibility", SymbolKind.METHOD)
    imports = {
        "promos/evaluator.py": [
            ImportStatement(source_module="promos.repo", imported_names=["CouponRepo"], is_from=True),
            ImportStatement(source_module="promos.rules", imported_names=["CouponRuleEngine"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, coup_m, rule_m], imports)
    assert coup_m.symbol_id in graph[caller.symbol_id]
    assert rule_m.symbol_id in graph[caller.symbol_id]


def test_113_distributed_inventory_reservation():
    caller = _make_symbol("inventory/service.py", "reserve_stock", outgoing_calls=["self.redis.acquire_lock", "self.repo.decrement_quantity"])
    redis_m = _make_symbol("infra/redis.py", "acquire_lock", "RedisLockManager.acquire_lock", SymbolKind.METHOD)
    repo_m = _make_symbol("inventory/repo.py", "decrement_quantity", "StockRepo.decrement_quantity", SymbolKind.METHOD)
    imports = {
        "inventory/service.py": [
            ImportStatement(source_module="infra.redis", imported_names=["RedisLockManager"], is_from=True),
            ImportStatement(source_module="inventory.repo", imported_names=["StockRepo"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, redis_m, repo_m], imports)
    assert redis_m.symbol_id in graph[caller.symbol_id]
    assert repo_m.symbol_id in graph[caller.symbol_id]


def test_114_multi_carrier_shipping_quoter():
    caller = _make_symbol("shipping/quoter.py", "quote_all", outgoing_calls=["self.fedex.get_rate", "self.ups.get_rate", "self.dhl.get_rate"])
    fedex_m = _make_symbol("shipping/fedex.py", "get_rate", "FedExClient.get_rate", SymbolKind.METHOD)
    ups_m = _make_symbol("shipping/ups.py", "get_rate", "UpsClient.get_rate", SymbolKind.METHOD)
    dhl_m = _make_symbol("shipping/dhl.py", "get_rate", "DhlClient.get_rate", SymbolKind.METHOD)
    imports = {
        "shipping/quoter.py": [
            ImportStatement(source_module="shipping.fedex", imported_names=["FedExClient"], is_from=True),
            ImportStatement(source_module="shipping.ups", imported_names=["UpsClient"], is_from=True),
            ImportStatement(source_module="shipping.dhl", imported_names=["DhlClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, fedex_m, ups_m, dhl_m], imports)
    assert fedex_m.symbol_id in graph[caller.symbol_id]
    assert ups_m.symbol_id in graph[caller.symbol_id]
    assert dhl_m.symbol_id in graph[caller.symbol_id]


def test_115_tax_calculation_engine_regional():
    caller = _make_symbol("tax/calculator.py", "calculate_tax", outgoing_calls=["self.nexus.check_nexus", "self.rates.lookup_jurisdiction_rate"])
    nex_m = _make_symbol("tax/nexus.py", "check_nexus", "NexusVerifier.check_nexus", SymbolKind.METHOD)
    rate_m = _make_symbol("tax/rates.py", "lookup_jurisdiction_rate", "JurisdictionRateTable.lookup_jurisdiction_rate", SymbolKind.METHOD)
    imports = {
        "tax/calculator.py": [
            ImportStatement(source_module="tax.nexus", imported_names=["NexusVerifier"], is_from=True),
            ImportStatement(source_module="tax.rates", imported_names=["JurisdictionRateTable"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, nex_m, rate_m], imports)
    assert nex_m.symbol_id in graph[caller.symbol_id]
    assert rate_m.symbol_id in graph[caller.symbol_id]


def test_116_warehouse_pick_pack_dispatch():
    caller = _make_symbol("warehouse/dispatch.py", "dispatch_order", outgoing_calls=["self.wms.generate_pick_list", "self.labels.print_shipping_label"])
    wms_m = _make_symbol("warehouse/wms.py", "generate_pick_list", "WmsGateway.generate_pick_list", SymbolKind.METHOD)
    lbl_m = _make_symbol("shipping/labels.py", "print_shipping_label", "LabelPrinter.print_shipping_label", SymbolKind.METHOD)
    imports = {
        "warehouse/dispatch.py": [
            ImportStatement(source_module="warehouse.wms", imported_names=["WmsGateway"], is_from=True),
            ImportStatement(source_module="shipping.labels", imported_names=["LabelPrinter"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, wms_m, lbl_m], imports)
    assert wms_m.symbol_id in graph[caller.symbol_id]
    assert lbl_m.symbol_id in graph[caller.symbol_id]


def test_117_out_of_stock_backorder_trigger():
    caller = _make_symbol("inventory/backorder.py", "handle_shortage", outgoing_calls=["self.supplier.create_purchase_order", "self.notifications.notify_customer"])
    po_m = _make_symbol("suppliers/service.py", "create_purchase_order", "SupplierService.create_purchase_order", SymbolKind.METHOD)
    notif_m = _make_symbol("notify/service.py", "notify_customer", "NotificationService.notify_customer", SymbolKind.METHOD)
    imports = {
        "inventory/backorder.py": [
            ImportStatement(source_module="suppliers.service", imported_names=["SupplierService"], is_from=True),
            ImportStatement(source_module="notify.service", imported_names=["NotificationService"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, po_m, notif_m], imports)
    assert po_m.symbol_id in graph[caller.symbol_id]
    assert notif_m.symbol_id in graph[caller.symbol_id]


def test_118_rma_return_inspection_workflow():
    caller = _make_symbol("returns/rma.py", "inspect_return", outgoing_calls=["self.grading.grade_item", "self.refunds.trigger_refund"])
    grade_m = _make_symbol("returns/grading.py", "grade_item", "ItemGradingService.grade_item", SymbolKind.METHOD)
    ref_m = _make_symbol("payments/refunds.py", "trigger_refund", "RefundService.trigger_refund", SymbolKind.METHOD)
    imports = {
        "returns/rma.py": [
            ImportStatement(source_module="returns.grading", imported_names=["ItemGradingService"], is_from=True),
            ImportStatement(source_module="payments.refunds", imported_names=["RefundService"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, grade_m, ref_m], imports)
    assert grade_m.symbol_id in graph[caller.symbol_id]
    assert ref_m.symbol_id in graph[caller.symbol_id]


def test_119_customer_loyalty_points_accrual():
    caller = _make_symbol("loyalty/service.py", "accrue_points", outgoing_calls=["self.points.calculate_points", "self.ledger.credit_account"])
    pts_m = _make_symbol("loyalty/calc.py", "calculate_points", "PointsCalculator.calculate_points", SymbolKind.METHOD)
    led_m = _make_symbol("loyalty/ledger.py", "credit_account", "PointsLedger.credit_account", SymbolKind.METHOD)
    imports = {
        "loyalty/service.py": [
            ImportStatement(source_module="loyalty.calc", imported_names=["PointsCalculator"], is_from=True),
            ImportStatement(source_module="loyalty.ledger", imported_names=["PointsLedger"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, pts_m, led_m], imports)
    assert pts_m.symbol_id in graph[caller.symbol_id]
    assert led_m.symbol_id in graph[caller.symbol_id]


def test_120_abandoned_cart_recovery():
    caller = _make_symbol("marketing/abandoned_cart.py", "process_stale_carts", outgoing_calls=["self.carts.find_unconverted", "self.email.send_discount_nudge"])
    cart_m = _make_symbol("cart/repo.py", "find_unconverted", "CartRepo.find_unconverted", SymbolKind.METHOD)
    mail_m = _make_symbol("marketing/email.py", "send_discount_nudge", "MarketingEmailer.send_discount_nudge", SymbolKind.METHOD)
    imports = {
        "marketing/abandoned_cart.py": [
            ImportStatement(source_module="cart.repo", imported_names=["CartRepo"], is_from=True),
            ImportStatement(source_module="marketing.email", imported_names=["MarketingEmailer"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, cart_m, mail_m], imports)
    assert cart_m.symbol_id in graph[caller.symbol_id]
    assert mail_m.symbol_id in graph[caller.symbol_id]


# ============================================================================
# DOMAIN 3: Multi-Tenant SaaS & RBAC Security (Tests 121 to 130)
# ============================================================================

def test_121_tenant_context_middleware():
    caller = _make_symbol("tenant/middleware.py", "resolve_tenant", outgoing_calls=["extract_subdomain", "self.repo.find_by_slug"])
    ext_fn = _make_symbol("tenant/extractor.py", "extract_subdomain")
    repo_m = _make_symbol("tenant/repo.py", "find_by_slug", "TenantRepo.find_by_slug", SymbolKind.METHOD)
    imports = {
        "tenant/middleware.py": [
            ImportStatement(source_module="tenant.extractor", imported_names=["extract_subdomain"], is_from=True),
            ImportStatement(source_module="tenant.repo", imported_names=["TenantRepo"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, ext_fn, repo_m], imports)
    assert ext_fn.symbol_id in graph[caller.symbol_id]
    assert repo_m.symbol_id in graph[caller.symbol_id]


def test_122_abac_policy_evaluator():
    caller = _make_symbol("security/abac.py", "evaluate_policy", outgoing_calls=["self.context.get_attributes", "self.rules.matches_condition"])
    ctx_m = _make_symbol("security/context.py", "get_attributes", "AttributeContext.get_attributes", SymbolKind.METHOD)
    rule_m = _make_symbol("security/rules.py", "matches_condition", "PolicyRule.matches_condition", SymbolKind.METHOD)
    imports = {
        "security/abac.py": [
            ImportStatement(source_module="security.context", imported_names=["AttributeContext"], is_from=True),
            ImportStatement(source_module="security.rules", imported_names=["PolicyRule"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, ctx_m, rule_m], imports)
    assert ctx_m.symbol_id in graph[caller.symbol_id]
    assert rule_m.symbol_id in graph[caller.symbol_id]


def test_123_org_hierarchy_role_inheritance():
    caller = _make_symbol("rbac/hierarchy.py", "get_effective_permissions", outgoing_calls=["self.orgs.get_ancestors", "self.roles.aggregate_permissions"])
    org_m = _make_symbol("orgs/service.py", "get_ancestors", "OrganizationService.get_ancestors", SymbolKind.METHOD)
    role_m = _make_symbol("rbac/roles.py", "aggregate_permissions", "RoleService.aggregate_permissions", SymbolKind.METHOD)
    imports = {
        "rbac/hierarchy.py": [
            ImportStatement(source_module="orgs.service", imported_names=["OrganizationService"], is_from=True),
            ImportStatement(source_module="rbac.roles", imported_names=["RoleService"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, org_m, role_m], imports)
    assert org_m.symbol_id in graph[caller.symbol_id]
    assert role_m.symbol_id in graph[caller.symbol_id]


def test_124_oauth2_authorization_code_exchange():
    caller = _make_symbol("oauth/token_endpoint.py", "exchange_code", outgoing_calls=["self.validator.validate_pkce", "self.jwt.sign_access_token"])
    pkce_m = _make_symbol("oauth/pkce.py", "validate_pkce", "PkceValidator.validate_pkce", SymbolKind.METHOD)
    jwt_m = _make_symbol("security/jwt.py", "sign_access_token", "JwtSigner.sign_access_token", SymbolKind.METHOD)
    imports = {
        "oauth/token_endpoint.py": [
            ImportStatement(source_module="oauth.pkce", imported_names=["PkceValidator"], is_from=True),
            ImportStatement(source_module="security.jwt", imported_names=["JwtSigner"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, pkce_m, jwt_m], imports)
    assert pkce_m.symbol_id in graph[caller.symbol_id]
    assert jwt_m.symbol_id in graph[caller.symbol_id]


def test_125_api_key_permission_mask():
    caller = _make_symbol("auth/api_key.py", "validate_key", outgoing_calls=["hash_api_key", "self.keys.find_by_hash"])
    hash_fn = _make_symbol("auth/hasher.py", "hash_api_key")
    key_m = _make_symbol("auth/repo.py", "find_by_hash", "ApiKeyRepo.find_by_hash", SymbolKind.METHOD)
    imports = {
        "auth/api_key.py": [
            ImportStatement(source_module="auth.hasher", imported_names=["hash_api_key"], is_from=True),
            ImportStatement(source_module="auth.repo", imported_names=["ApiKeyRepo"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, hash_fn, key_m], imports)
    assert hash_fn.symbol_id in graph[caller.symbol_id]
    assert key_m.symbol_id in graph[caller.symbol_id]


def test_126_usage_based_metering():
    caller = _make_symbol("metering/collector.py", "record_api_call", outgoing_calls=["self.redis.incr_quota", "self.stripe.report_usage"])
    redis_m = _make_symbol("infra/redis.py", "incr_quota", "RedisCounter.incr_quota", SymbolKind.METHOD)
    stripe_m = _make_symbol("billing/stripe.py", "report_usage", "StripeMeterClient.report_usage", SymbolKind.METHOD)
    imports = {
        "metering/collector.py": [
            ImportStatement(source_module="infra.redis", imported_names=["RedisCounter"], is_from=True),
            ImportStatement(source_module="billing.stripe", imported_names=["StripeMeterClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, redis_m, stripe_m], imports)
    assert redis_m.symbol_id in graph[caller.symbol_id]
    assert stripe_m.symbol_id in graph[caller.symbol_id]


def test_127_dynamic_feature_flag_evaluator():
    caller = _make_symbol("features/flags.py", "is_enabled", outgoing_calls=["self.flags.get_flag_definition", "hash_user_bucket"])
    flag_m = _make_symbol("features/repo.py", "get_flag_definition", "FlagRepo.get_flag_definition", SymbolKind.METHOD)
    hash_fn = _make_symbol("features/bucketer.py", "hash_user_bucket")
    imports = {
        "features/flags.py": [
            ImportStatement(source_module="features.repo", imported_names=["FlagRepo"], is_from=True),
            ImportStatement(source_module="features.bucketer", imported_names=["hash_user_bucket"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, flag_m, hash_fn], imports)
    assert flag_m.symbol_id in graph[caller.symbol_id]
    assert hash_fn.symbol_id in graph[caller.symbol_id]


def test_128_webhook_dispatcher_dlq():
    caller = _make_symbol("webhooks/dispatcher.py", "dispatch_webhook", outgoing_calls=["self.http.post", "self.dlq.enqueue_dead_letter"])
    http_m = _make_symbol("infra/http.py", "post", "HttpClient.post", SymbolKind.METHOD)
    dlq_m = _make_symbol("queues/dlq.py", "enqueue_dead_letter", "DeadLetterQueue.enqueue_dead_letter", SymbolKind.METHOD)
    imports = {
        "webhooks/dispatcher.py": [
            ImportStatement(source_module="infra.http", imported_names=["HttpClient"], is_from=True),
            ImportStatement(source_module="queues.dlq", imported_names=["DeadLetterQueue"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, http_m, dlq_m], imports)
    assert http_m.symbol_id in graph[caller.symbol_id]
    assert dlq_m.symbol_id in graph[caller.symbol_id]


def test_129_audit_log_producer():
    caller = _make_symbol("audit/producer.py", "record_audit_event", outgoing_calls=["self.hasher.hash_event", "self.stream.publish"])
    hash_m = _make_symbol("audit/hasher.py", "hash_event", "EventHasher.hash_event", SymbolKind.METHOD)
    stream_m = _make_symbol("infra/kafka.py", "publish", "KafkaProducer.publish", SymbolKind.METHOD)
    imports = {
        "audit/producer.py": [
            ImportStatement(source_module="audit.hasher", imported_names=["EventHasher"], is_from=True),
            ImportStatement(source_module="infra.kafka", imported_names=["KafkaProducer"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, hash_m, stream_m], imports)
    assert hash_m.symbol_id in graph[caller.symbol_id]
    assert stream_m.symbol_id in graph[caller.symbol_id]


def test_130_session_invalidation_cascade():
    caller = _make_symbol("auth/session.py", "logout_all_devices", outgoing_calls=["self.redis.delete_pattern", "self.tokens.blacklist_jwt"])
    redis_m = _make_symbol("infra/redis.py", "delete_pattern", "RedisStore.delete_pattern", SymbolKind.METHOD)
    jwt_m = _make_symbol("auth/tokens.py", "blacklist_jwt", "TokenBlacklist.blacklist_jwt", SymbolKind.METHOD)
    imports = {
        "auth/session.py": [
            ImportStatement(source_module="infra.redis", imported_names=["RedisStore"], is_from=True),
            ImportStatement(source_module="auth.tokens", imported_names=["TokenBlacklist"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, redis_m, jwt_m], imports)
    assert redis_m.symbol_id in graph[caller.symbol_id]
    assert jwt_m.symbol_id in graph[caller.symbol_id]


# ============================================================================
# DOMAIN 4: Ride-Sharing & Geospatial Dispatch (Tests 131 to 140)
# ============================================================================

def test_131_ride_request_geohash_lookup():
    caller = _make_symbol("rides/request.py", "request_ride", outgoing_calls=["encode_geohash", "self.geo_index.query_nearby"])
    geo_fn = _make_symbol("geo/hasher.py", "encode_geohash")
    idx_m = _make_symbol("geo/index.py", "query_nearby", "GeoSpatialIndex.query_nearby", SymbolKind.METHOD)
    imports = {
        "rides/request.py": [
            ImportStatement(source_module="geo.hasher", imported_names=["encode_geohash"], is_from=True),
            ImportStatement(source_module="geo.index", imported_names=["GeoSpatialIndex"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, geo_fn, idx_m], imports)
    assert geo_fn.symbol_id in graph[caller.symbol_id]
    assert idx_m.symbol_id in graph[caller.symbol_id]


def test_132_nearest_driver_distance_matrix():
    caller = _make_symbol("dispatch/matcher.py", "find_best_driver", outgoing_calls=["self.routing.calculate_eta", "self.drivers.filter_active"])
    route_m = _make_symbol("routing/engine.py", "calculate_eta", "RoutingEngine.calculate_eta", SymbolKind.METHOD)
    drv_m = _make_symbol("drivers/service.py", "filter_active", "DriverService.filter_active", SymbolKind.METHOD)
    imports = {
        "dispatch/matcher.py": [
            ImportStatement(source_module="routing.engine", imported_names=["RoutingEngine"], is_from=True),
            ImportStatement(source_module="drivers.service", imported_names=["DriverService"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, route_m, drv_m], imports)
    assert route_m.symbol_id in graph[caller.symbol_id]
    assert drv_m.symbol_id in graph[caller.symbol_id]


def test_133_dynamic_surge_pricing():
    caller = _make_symbol("pricing/surge.py", "calculate_surge_multiplier", outgoing_calls=["self.demand.get_open_requests", "self.supply.get_available_drivers"])
    dem_m = _make_symbol("pricing/demand.py", "get_open_requests", "DemandTracker.get_open_requests", SymbolKind.METHOD)
    sup_m = _make_symbol("pricing/supply.py", "get_available_drivers", "SupplyTracker.get_available_drivers", SymbolKind.METHOD)
    imports = {
        "pricing/surge.py": [
            ImportStatement(source_module="pricing.demand", imported_names=["DemandTracker"], is_from=True),
            ImportStatement(source_module="pricing.supply", imported_names=["SupplyTracker"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, dem_m, sup_m], imports)
    assert dem_m.symbol_id in graph[caller.symbol_id]
    assert sup_m.symbol_id in graph[caller.symbol_id]


def test_134_trip_lifecycle_state_machine():
    caller = _make_symbol("trips/lifecycle.py", "transition_state", outgoing_calls=["self.validator.validate_transition", "self.events.emit_trip_update"])
    trans_m = _make_symbol("trips/validator.py", "validate_transition", "TransitionValidator.validate_transition", SymbolKind.METHOD)
    evt_m = _make_symbol("trips/events.py", "emit_trip_update", "TripEventEmitter.emit_trip_update", SymbolKind.METHOD)
    imports = {
        "trips/lifecycle.py": [
            ImportStatement(source_module="trips.validator", imported_names=["TransitionValidator"], is_from=True),
            ImportStatement(source_module="trips.events", imported_names=["TripEventEmitter"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, trans_m, evt_m], imports)
    assert trans_m.symbol_id in graph[caller.symbol_id]
    assert evt_m.symbol_id in graph[caller.symbol_id]


def test_135_gps_telemetry_streaming():
    caller = _make_symbol("telemetry/streamer.py", "ingest_coordinate", outgoing_calls=["filter_outlier_gps", "self.ws.broadcast_to_passenger"])
    flt_fn = _make_symbol("telemetry/filter.py", "filter_outlier_gps")
    ws_m = _make_symbol("infra/websocket.py", "broadcast_to_passenger", "WebSocketHub.broadcast_to_passenger", SymbolKind.METHOD)
    imports = {
        "telemetry/streamer.py": [
            ImportStatement(source_module="telemetry.filter", imported_names=["filter_outlier_gps"], is_from=True),
            ImportStatement(source_module="infra.websocket", imported_names=["WebSocketHub"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, flt_fn, ws_m], imports)
    assert flt_fn.symbol_id in graph[caller.symbol_id]
    assert ws_m.symbol_id in graph[caller.symbol_id]


def test_136_fare_calculation_tolls():
    caller = _make_symbol("pricing/fare.py", "compute_total_fare", outgoing_calls=["self.toll_service.get_tolls", "self.distance.calculate_haversine"])
    toll_m = _make_symbol("pricing/tolls.py", "get_tolls", "TollService.get_tolls", SymbolKind.METHOD)
    dist_m = _make_symbol("geo/distance.py", "calculate_haversine", "DistanceMatrix.calculate_haversine", SymbolKind.METHOD)
    imports = {
        "pricing/fare.py": [
            ImportStatement(source_module="pricing.tolls", imported_names=["TollService"], is_from=True),
            ImportStatement(source_module="geo.distance", imported_names=["DistanceMatrix"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, toll_m, dist_m], imports)
    assert toll_m.symbol_id in graph[caller.symbol_id]
    assert dist_m.symbol_id in graph[caller.symbol_id]


def test_137_split_fare_acceptance():
    caller = _make_symbol("rides/split_fare.py", "accept_split", outgoing_calls=["self.wallet.pre_authorize", "self.trips.add_passenger"])
    wall_m = _make_symbol("payments/wallet.py", "pre_authorize", "WalletService.pre_authorize", SymbolKind.METHOD)
    trip_m = _make_symbol("trips/manager.py", "add_passenger", "TripManager.add_passenger", SymbolKind.METHOD)
    imports = {
        "rides/split_fare.py": [
            ImportStatement(source_module="payments.wallet", imported_names=["WalletService"], is_from=True),
            ImportStatement(source_module="trips.manager", imported_names=["TripManager"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, wall_m, trip_m], imports)
    assert wall_m.symbol_id in graph[caller.symbol_id]
    assert trip_m.symbol_id in graph[caller.symbol_id]


def test_138_driver_cancellation_penalty():
    caller = _make_symbol("rides/cancellation.py", "handle_driver_cancel", outgoing_calls=["self.penalties.assess_fee", "self.dispatch.reassign_ride"])
    pen_m = _make_symbol("drivers/penalties.py", "assess_fee", "PenaltyEngine.assess_fee", SymbolKind.METHOD)
    disp_m = _make_symbol("dispatch/engine.py", "reassign_ride", "DispatchEngine.reassign_ride", SymbolKind.METHOD)
    imports = {
        "rides/cancellation.py": [
            ImportStatement(source_module="drivers.penalties", imported_names=["PenaltyEngine"], is_from=True),
            ImportStatement(source_module="dispatch.engine", imported_names=["DispatchEngine"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, pen_m, disp_m], imports)
    assert pen_m.symbol_id in graph[caller.symbol_id]
    assert disp_m.symbol_id in graph[caller.symbol_id]


def test_139_weekly_driver_payout_surcharge():
    caller = _make_symbol("payouts/weekly.py", "aggregate_driver_earnings", outgoing_calls=["self.trips.get_completed_fares", "self.bank.initiate_direct_deposit"])
    trip_m = _make_symbol("trips/repo.py", "get_completed_fares", "TripRepo.get_completed_fares", SymbolKind.METHOD)
    bank_m = _make_symbol("banking/ach.py", "initiate_direct_deposit", "BankClient.initiate_direct_deposit", SymbolKind.METHOD)
    imports = {
        "payouts/weekly.py": [
            ImportStatement(source_module="trips.repo", imported_names=["TripRepo"], is_from=True),
            ImportStatement(source_module="banking.ach", imported_names=["BankClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, trip_m, bank_m], imports)
    assert trip_m.symbol_id in graph[caller.symbol_id]
    assert bank_m.symbol_id in graph[caller.symbol_id]


def test_140_lost_and_found_incident_matching():
    caller = _make_symbol("support/lost_found.py", "report_lost_item", outgoing_calls=["self.trips.get_trip_details", "self.sms.alert_driver"])
    trip_m = _make_symbol("trips/repo.py", "get_trip_details", "TripRepo.get_trip_details", SymbolKind.METHOD)
    sms_m = _make_symbol("notify/sms.py", "alert_driver", "SmsGateway.alert_driver", SymbolKind.METHOD)
    imports = {
        "support/lost_found.py": [
            ImportStatement(source_module="trips.repo", imported_names=["TripRepo"], is_from=True),
            ImportStatement(source_module="notify.sms", imported_names=["SmsGateway"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, trip_m, sms_m], imports)
    assert trip_m.symbol_id in graph[caller.symbol_id]
    assert sms_m.symbol_id in graph[caller.symbol_id]


# ============================================================================
# DOMAIN 5: Healthcare & Telehealth Portal (HIPAA) (Tests 141 to 150)
# ============================================================================

def test_141_appointment_slot_booking():
    caller = _make_symbol("telehealth/booking.py", "book_slot", outgoing_calls=["self.schedule.is_doctor_available", "self.calendar.reserve_time_block"])
    sched_m = _make_symbol("telehealth/schedule.py", "is_doctor_available", "DoctorSchedule.is_doctor_available", SymbolKind.METHOD)
    cal_m = _make_symbol("telehealth/calendar.py", "reserve_time_block", "CalendarService.reserve_time_block", SymbolKind.METHOD)
    imports = {
        "telehealth/booking.py": [
            ImportStatement(source_module="telehealth.schedule", imported_names=["DoctorSchedule"], is_from=True),
            ImportStatement(source_module="telehealth.calendar", imported_names=["CalendarService"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, sched_m, cal_m], imports)
    assert sched_m.symbol_id in graph[caller.symbol_id]
    assert cal_m.symbol_id in graph[caller.symbol_id]


def test_142_ehr_encryption_decryption():
    caller = _make_symbol("ehr/record.py", "read_patient_record", outgoing_calls=["self.crypto.decrypt_phi", "self.audit.log_phi_access"])
    cryp_m = _make_symbol("security/phi.py", "decrypt_phi", "PhiCrypto.decrypt_phi", SymbolKind.METHOD)
    aud_m = _make_symbol("security/audit.py", "log_phi_access", "HipaaAuditLogger.log_phi_access", SymbolKind.METHOD)
    imports = {
        "ehr/record.py": [
            ImportStatement(source_module="security.phi", imported_names=["PhiCrypto"], is_from=True),
            ImportStatement(source_module="security.audit", imported_names=["HipaaAuditLogger"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, cryp_m, aud_m], imports)
    assert cryp_m.symbol_id in graph[caller.symbol_id]
    assert aud_m.symbol_id in graph[caller.symbol_id]


def test_143_prescription_pki_signing():
    caller = _make_symbol("pharmacy/prescription.py", "sign_prescription", outgoing_calls=["self.pki.verify_physician_cert", "self.surescripts.transmit_order"])
    pki_m = _make_symbol("security/pki.py", "verify_physician_cert", "PkiValidator.verify_physician_cert", SymbolKind.METHOD)
    sure_m = _make_symbol("pharmacy/surescripts.py", "transmit_order", "SurescriptsClient.transmit_order", SymbolKind.METHOD)
    imports = {
        "pharmacy/prescription.py": [
            ImportStatement(source_module="security.pki", imported_names=["PkiValidator"], is_from=True),
            ImportStatement(source_module="pharmacy.surescripts", imported_names=["SurescriptsClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, pki_m, sure_m], imports)
    assert pki_m.symbol_id in graph[caller.symbol_id]
    assert sure_m.symbol_id in graph[caller.symbol_id]


def test_144_insurance_preauth_adjudication():
    caller = _make_symbol("insurance/claims.py", "check_eligibility", outgoing_calls=["self.clearinghouse.query_270", "self.rules.evaluate_copay"])
    clear_m = _make_symbol("insurance/edi.py", "query_270", "EdiClearinghouse.query_270", SymbolKind.METHOD)
    copay_m = _make_symbol("insurance/rules.py", "evaluate_copay", "BenefitRules.evaluate_copay", SymbolKind.METHOD)
    imports = {
        "insurance/claims.py": [
            ImportStatement(source_module="insurance.edi", imported_names=["EdiClearinghouse"], is_from=True),
            ImportStatement(source_module="insurance.rules", imported_names=["BenefitRules"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, clear_m, copay_m], imports)
    assert clear_m.symbol_id in graph[caller.symbol_id]
    assert copay_m.symbol_id in graph[caller.symbol_id]


def test_145_webrtc_video_consultation_token():
    caller = _make_symbol("video/session.py", "start_consultation", outgoing_calls=["self.webrtc.generate_room_token", "self.notify.alert_patient"])
    rtc_m = _make_symbol("infra/webrtc.py", "generate_room_token", "WebRtcGateway.generate_room_token", SymbolKind.METHOD)
    notif_m = _make_symbol("notify/push.py", "alert_patient", "PushNotifier.alert_patient", SymbolKind.METHOD)
    imports = {
        "video/session.py": [
            ImportStatement(source_module="infra.webrtc", imported_names=["WebRtcGateway"], is_from=True),
            ImportStatement(source_module="notify.push", imported_names=["PushNotifier"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, rtc_m, notif_m], imports)
    assert rtc_m.symbol_id in graph[caller.symbol_id]
    assert notif_m.symbol_id in graph[caller.symbol_id]


def test_146_lab_results_abnormal_alert():
    caller = _make_symbol("labs/ingestion.py", "ingest_hl7_result", outgoing_calls=["parse_hl7_message", "self.alerts.escalate_critical_value"])
    hl7_fn = _make_symbol("labs/parser.py", "parse_hl7_message")
    alert_m = _make_symbol("labs/alerts.py", "escalate_critical_value", "CriticalAlertManager.escalate_critical_value", SymbolKind.METHOD)
    imports = {
        "labs/ingestion.py": [
            ImportStatement(source_module="labs.parser", imported_names=["parse_hl7_message"], is_from=True),
            ImportStatement(source_module="labs.alerts", imported_names=["CriticalAlertManager"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, hl7_fn, alert_m], imports)
    assert hl7_fn.symbol_id in graph[caller.symbol_id]
    assert alert_m.symbol_id in graph[caller.symbol_id]


def test_147_patient_consent_verification():
    caller = _make_symbol("consent/verifier.py", "verify_sharing_consent", outgoing_calls=["self.consent_repo.has_active_waiver", "self.audit.log_waiver_check"])
    waiver_m = _make_symbol("consent/repo.py", "has_active_waiver", "ConsentRepo.has_active_waiver", SymbolKind.METHOD)
    aud_m = _make_symbol("security/audit.py", "log_waiver_check", "HipaaAuditLogger.log_waiver_check", SymbolKind.METHOD)
    imports = {
        "consent/verifier.py": [
            ImportStatement(source_module="consent.repo", imported_names=["ConsentRepo"], is_from=True),
            ImportStatement(source_module="security.audit", imported_names=["HipaaAuditLogger"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, waiver_m, aud_m], imports)
    assert waiver_m.symbol_id in graph[caller.symbol_id]
    assert aud_m.symbol_id in graph[caller.symbol_id]


def test_148_icd10_coding_validator():
    caller = _make_symbol("billing/coding.py", "validate_icd10_codes", outgoing_calls=["self.validator.check_code_format", "self.crosswalk.map_to_cpt"])
    fmt_m = _make_symbol("billing/validator.py", "check_code_format", "IcdValidator.check_code_format", SymbolKind.METHOD)
    cross_m = _make_symbol("billing/crosswalk.py", "map_to_cpt", "CodeCrosswalk.map_to_cpt", SymbolKind.METHOD)
    imports = {
        "billing/coding.py": [
            ImportStatement(source_module="billing.validator", imported_names=["IcdValidator"], is_from=True),
            ImportStatement(source_module="billing.crosswalk", imported_names=["CodeCrosswalk"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, fmt_m, cross_m], imports)
    assert fmt_m.symbol_id in graph[caller.symbol_id]
    assert cross_m.symbol_id in graph[caller.symbol_id]


def test_149_emergency_physician_pager():
    caller = _make_symbol("emergency/dispatch.py", "trigger_stat_escalation", outgoing_calls=["self.schedule.find_on_call_physician", "self.pager.send_critical_page"])
    doc_m = _make_symbol("telehealth/schedule.py", "find_on_call_physician", "DoctorSchedule.find_on_call_physician", SymbolKind.METHOD)
    page_m = _make_symbol("infra/pagerduty.py", "send_critical_page", "PagerClient.send_critical_page", SymbolKind.METHOD)
    imports = {
        "emergency/dispatch.py": [
            ImportStatement(source_module="telehealth.schedule", imported_names=["DoctorSchedule"], is_from=True),
            ImportStatement(source_module="infra.pagerduty", imported_names=["PagerClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, doc_m, page_m], imports)
    assert doc_m.symbol_id in graph[caller.symbol_id]
    assert page_m.symbol_id in graph[caller.symbol_id]


def test_150_hipaa_compliance_export():
    caller = _make_symbol("compliance/export.py", "generate_hipaa_report", outgoing_calls=["self.audit.fetch_range", "self.archive.bundle_encrypted_zip"])
    fetch_m = _make_symbol("security/audit.py", "fetch_range", "HipaaAuditLogger.fetch_range", SymbolKind.METHOD)
    zip_m = _make_symbol("infra/archive.py", "bundle_encrypted_zip", "ZipArchiver.bundle_encrypted_zip", SymbolKind.METHOD)
    imports = {
        "compliance/export.py": [
            ImportStatement(source_module="security.audit", imported_names=["HipaaAuditLogger"], is_from=True),
            ImportStatement(source_module="infra.archive", imported_names=["ZipArchiver"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, fetch_m, zip_m], imports)
    assert fetch_m.symbol_id in graph[caller.symbol_id]
    assert zip_m.symbol_id in graph[caller.symbol_id]


# ============================================================================
# DOMAIN 6: Content Streaming & Social Feed Architecture (Tests 151 to 160)
# ============================================================================

def test_151_video_chunk_transcoding_job():
    caller = _make_symbol("media/transcoder.py", "queue_transcode", outgoing_calls=["self.s3.assemble_chunks", "self.sqs.send_job"])
    s3_m = _make_symbol("storage/s3.py", "assemble_chunks", "S3Client.assemble_chunks", SymbolKind.METHOD)
    sqs_m = _make_symbol("infra/sqs.py", "send_job", "SqsClient.send_job", SymbolKind.METHOD)
    imports = {
        "media/transcoder.py": [
            ImportStatement(source_module="storage.s3", imported_names=["S3Client"], is_from=True),
            ImportStatement(source_module="infra.sqs", imported_names=["SqsClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, s3_m, sqs_m], imports)
    assert s3_m.symbol_id in graph[caller.symbol_id]
    assert sqs_m.symbol_id in graph[caller.symbol_id]


def test_152_content_moderation_pipeline():
    caller = _make_symbol("moderation/scanner.py", "scan_post", outgoing_calls=["self.nlp.detect_toxicity", "self.vision.detect_nsfw"])
    nlp_m = _make_symbol("ai/nlp.py", "detect_toxicity", "NlpScanner.detect_toxicity", SymbolKind.METHOD)
    vis_m = _make_symbol("ai/vision.py", "detect_nsfw", "VisionScanner.detect_nsfw", SymbolKind.METHOD)
    imports = {
        "moderation/scanner.py": [
            ImportStatement(source_module="ai.nlp", imported_names=["NlpScanner"], is_from=True),
            ImportStatement(source_module="ai.vision", imported_names=["VisionScanner"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, nlp_m, vis_m], imports)
    assert nlp_m.symbol_id in graph[caller.symbol_id]
    assert vis_m.symbol_id in graph[caller.symbol_id]


def test_153_social_graph_follow_edge():
    caller = _make_symbol("social/graph.py", "follow_user", outgoing_calls=["self.neo4j.create_follow_edge", "self.cache.invalidate_follower_list"])
    neo_m = _make_symbol("db/neo4j.py", "create_follow_edge", "Neo4jClient.create_follow_edge", SymbolKind.METHOD)
    cache_m = _make_symbol("cache/social.py", "invalidate_follower_list", "SocialCache.invalidate_follower_list", SymbolKind.METHOD)
    imports = {
        "social/graph.py": [
            ImportStatement(source_module="db.neo4j", imported_names=["Neo4jClient"], is_from=True),
            ImportStatement(source_module="cache.social", imported_names=["SocialCache"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, neo_m, cache_m], imports)
    assert neo_m.symbol_id in graph[caller.symbol_id]
    assert cache_m.symbol_id in graph[caller.symbol_id]


def test_154_fan_out_on_write_inboxes():
    caller = _make_symbol("feed/fanout.py", "fanout_post", outgoing_calls=["self.graph.get_followers", "self.inbox.push_to_timelines"])
    grp_m = _make_symbol("social/graph.py", "get_followers", "SocialGraph.get_followers", SymbolKind.METHOD)
    inb_m = _make_symbol("feed/inbox.py", "push_to_timelines", "TimelinePusher.push_to_timelines", SymbolKind.METHOD)
    imports = {
        "feed/fanout.py": [
            ImportStatement(source_module="social.graph", imported_names=["SocialGraph"], is_from=True),
            ImportStatement(source_module="feed.inbox", imported_names=["TimelinePusher"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, grp_m, inb_m], imports)
    assert grp_m.symbol_id in graph[caller.symbol_id]
    assert inb_m.symbol_id in graph[caller.symbol_id]


def test_155_celebrity_fan_out_on_read():
    caller = _make_symbol("feed/aggregator.py", "get_home_timeline", outgoing_calls=["self.cache.get_inbox_posts", "self.celebrity.pull_recent_posts"])
    cch_m = _make_symbol("cache/feed.py", "get_inbox_posts", "FeedCache.get_inbox_posts", SymbolKind.METHOD)
    cel_m = _make_symbol("feed/celebrity.py", "pull_recent_posts", "CelebrityPool.pull_recent_posts", SymbolKind.METHOD)
    imports = {
        "feed/aggregator.py": [
            ImportStatement(source_module="cache.feed", imported_names=["FeedCache"], is_from=True),
            ImportStatement(source_module="feed.celebrity", imported_names=["CelebrityPool"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, cch_m, cel_m], imports)
    assert cch_m.symbol_id in graph[caller.symbol_id]
    assert cel_m.symbol_id in graph[caller.symbol_id]


def test_156_cdn_presigned_url_hmac():
    caller = _make_symbol("media/cdn.py", "generate_download_url", outgoing_calls=["generate_hmac_token", "self.cf.build_signed_cookie"])
    hmac_fn = _make_symbol("security/hmac.py", "generate_hmac_token")
    cf_m = _make_symbol("infra/cloudfront.py", "build_signed_cookie", "CloudFrontSigner.build_signed_cookie", SymbolKind.METHOD)
    imports = {
        "media/cdn.py": [
            ImportStatement(source_module="security.hmac", imported_names=["generate_hmac_token"], is_from=True),
            ImportStatement(source_module="infra.cloudfront", imported_names=["CloudFrontSigner"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, hmac_fn, cf_m], imports)
    assert hmac_fn.symbol_id in graph[caller.symbol_id]
    assert cf_m.symbol_id in graph[caller.symbol_id]


def test_157_live_stream_comment_broadcast():
    caller = _make_symbol("livestream/chat.py", "post_comment", outgoing_calls=["self.moderation.filter_profanity", "self.pubsub.publish_room_message"])
    mod_m = _make_symbol("moderation/filter.py", "filter_profanity", "ChatFilter.filter_profanity", SymbolKind.METHOD)
    pub_m = _make_symbol("infra/redis_pubsub.py", "publish_room_message", "RedisChatPublisher.publish_room_message", SymbolKind.METHOD)
    imports = {
        "livestream/chat.py": [
            ImportStatement(source_module="moderation.filter", imported_names=["ChatFilter"], is_from=True),
            ImportStatement(source_module="infra.redis_pubsub", imported_names=["RedisChatPublisher"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, mod_m, pub_m], imports)
    assert mod_m.symbol_id in graph[caller.symbol_id]
    assert pub_m.symbol_id in graph[caller.symbol_id]


def test_158_trending_hashtag_counter():
    caller = _make_symbol("analytics/trends.py", "increment_hashtag", outgoing_calls=["self.hll.add_cardinality", "self.leaderboard.update_zset"])
    hll_m = _make_symbol("analytics/hll.py", "add_cardinality", "HyperLogLogCounter.add_cardinality", SymbolKind.METHOD)
    lead_m = _make_symbol("analytics/leaderboard.py", "update_zset", "TrendLeaderboard.update_zset", SymbolKind.METHOD)
    imports = {
        "analytics/trends.py": [
            ImportStatement(source_module="analytics.hll", imported_names=["HyperLogLogCounter"], is_from=True),
            ImportStatement(source_module="analytics.leaderboard", imported_names=["TrendLeaderboard"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, hll_m, lead_m], imports)
    assert hll_m.symbol_id in graph[caller.symbol_id]
    assert lead_m.symbol_id in graph[caller.symbol_id]


def test_159_e2e_encryption_key_exchange():
    caller = _make_symbol("chat/e2e.py", "exchange_keys", outgoing_calls=["self.keys.store_prekey_bundle", "self.notify.send_session_init"])
    key_m = _make_symbol("chat/keys.py", "store_prekey_bundle", "PreKeyStore.store_prekey_bundle", SymbolKind.METHOD)
    notif_m = _make_symbol("notify/push.py", "send_session_init", "PushClient.send_session_init", SymbolKind.METHOD)
    imports = {
        "chat/e2e.py": [
            ImportStatement(source_module="chat.keys", imported_names=["PreKeyStore"], is_from=True),
            ImportStatement(source_module="notify.push", imported_names=["PushClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, key_m, notif_m], imports)
    assert key_m.symbol_id in graph[caller.symbol_id]
    assert notif_m.symbol_id in graph[caller.symbol_id]


def test_160_audio_fingerprint_matching():
    caller = _make_symbol("audio/fingerprint.py", "match_audio_track", outgoing_calls=["extract_chromaprint", "self.catalog.search_chroma_hash"])
    ext_fn = _make_symbol("audio/extractor.py", "extract_chromaprint")
    cat_m = _make_symbol("audio/catalog.py", "search_chroma_hash", "AudioCatalog.search_chroma_hash", SymbolKind.METHOD)
    imports = {
        "audio/fingerprint.py": [
            ImportStatement(source_module="audio.extractor", imported_names=["extract_chromaprint"], is_from=True),
            ImportStatement(source_module="audio.catalog", imported_names=["AudioCatalog"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, ext_fn, cat_m], imports)
    assert ext_fn.symbol_id in graph[caller.symbol_id]
    assert cat_m.symbol_id in graph[caller.symbol_id]


# ============================================================================
# DOMAIN 7: Cloud Infrastructure & DevOps Orchestration (Tests 161 to 170)
# ============================================================================

def test_161_k8s_hpa_scaler():
    caller = _make_symbol("k8s/scaler.py", "evaluate_scale", outgoing_calls=["self.metrics.get_cpu_utilization", "self.client.scale_deployment"])
    met_m = _make_symbol("infra/prometheus.py", "get_cpu_utilization", "PrometheusClient.get_cpu_utilization", SymbolKind.METHOD)
    k8s_m = _make_symbol("k8s/client.py", "scale_deployment", "K8sClient.scale_deployment", SymbolKind.METHOD)
    imports = {
        "k8s/scaler.py": [
            ImportStatement(source_module="infra.prometheus", imported_names=["PrometheusClient"], is_from=True),
            ImportStatement(source_module="k8s.client", imported_names=["K8sClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, met_m, k8s_m], imports)
    assert met_m.symbol_id in graph[caller.symbol_id]
    assert k8s_m.symbol_id in graph[caller.symbol_id]


def test_162_canary_release_traffic_splitter():
    caller = _make_symbol("deploy/canary.py", "shift_traffic", outgoing_calls=["self.istio.update_virtual_service", "self.monitor.check_error_rate"])
    ist_m = _make_symbol("mesh/istio.py", "update_virtual_service", "IstioClient.update_virtual_service", SymbolKind.METHOD)
    mon_m = _make_symbol("infra/datadog.py", "check_error_rate", "DatadogClient.check_error_rate", SymbolKind.METHOD)
    imports = {
        "deploy/canary.py": [
            ImportStatement(source_module="mesh.istio", imported_names=["IstioClient"], is_from=True),
            ImportStatement(source_module="infra.datadog", imported_names=["DatadogClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, ist_m, mon_m], imports)
    assert ist_m.symbol_id in graph[caller.symbol_id]
    assert mon_m.symbol_id in graph[caller.symbol_id]


def test_163_vault_secret_rotation():
    caller = _make_symbol("security/vault.py", "rotate_db_credentials", outgoing_calls=["self.vault.lease_secret", "self.pool.update_credentials"])
    vlt_m = _make_symbol("infra/vault.py", "lease_secret", "HashiVaultClient.lease_secret", SymbolKind.METHOD)
    pool_m = _make_symbol("db/pool.py", "update_credentials", "DbConnectionPool.update_credentials", SymbolKind.METHOD)
    imports = {
        "security/vault.py": [
            ImportStatement(source_module="infra.vault", imported_names=["HashiVaultClient"], is_from=True),
            ImportStatement(source_module="db.pool", imported_names=["DbConnectionPool"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, vlt_m, pool_m], imports)
    assert vlt_m.symbol_id in graph[caller.symbol_id]
    assert pool_m.symbol_id in graph[caller.symbol_id]


def test_164_cloud_storage_lifecycle_worker():
    caller = _make_symbol("storage/lifecycle.py", "purge_expired_blobs", outgoing_calls=["self.gcs.list_blobs_older_than", "self.gcs.delete_blob_batch"])
    list_m = _make_symbol("infra/gcs.py", "list_blobs_older_than", "GcsStorageClient.list_blobs_older_than", SymbolKind.METHOD)
    del_m = _make_symbol("infra/gcs.py", "delete_blob_batch", "GcsStorageClient.delete_blob_batch", SymbolKind.METHOD)
    imports = {
        "storage/lifecycle.py": [
            ImportStatement(source_module="infra.gcs", imported_names=["GcsStorageClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, list_m, del_m], imports)
    assert list_m.symbol_id in graph[caller.symbol_id]
    assert del_m.symbol_id in graph[caller.symbol_id]


def test_165_acme_tls_cert_renewal():
    caller = _make_symbol("certs/acme.py", "renew_certificate", outgoing_calls=["self.acme.request_challenge", "self.dns.create_txt_record"])
    acme_m = _make_symbol("infra/acme.py", "request_challenge", "AcmeClient.request_challenge", SymbolKind.METHOD)
    dns_m = _make_symbol("dns/route53.py", "create_txt_record", "Route53Client.create_txt_record", SymbolKind.METHOD)
    imports = {
        "certs/acme.py": [
            ImportStatement(source_module="infra.acme", imported_names=["AcmeClient"], is_from=True),
            ImportStatement(source_module="dns.route53", imported_names=["Route53Client"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, acme_m, dns_m], imports)
    assert acme_m.symbol_id in graph[caller.symbol_id]
    assert dns_m.symbol_id in graph[caller.symbol_id]


def test_166_redlock_distributed_lock():
    caller = _make_symbol("sync/redlock.py", "acquire_cluster_lock", outgoing_calls=["self.quorum.lock_node", "self.clock.calculate_drift"])
    qrm_m = _make_symbol("infra/redis.py", "lock_node", "RedisQuorum.lock_node", SymbolKind.METHOD)
    clk_m = _make_symbol("sync/clock.py", "calculate_drift", "ClockDriftEstimator.calculate_drift", SymbolKind.METHOD)
    imports = {
        "sync/redlock.py": [
            ImportStatement(source_module="infra.redis", imported_names=["RedisQuorum"], is_from=True),
            ImportStatement(source_module="sync.clock", imported_names=["ClockDriftEstimator"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, qrm_m, clk_m], imports)
    assert qrm_m.symbol_id in graph[caller.symbol_id]
    assert clk_m.symbol_id in graph[caller.symbol_id]


def test_167_fluentd_log_buffer_flush():
    caller = _make_symbol("logging/shipper.py", "flush_buffer", outgoing_calls=["compress_gzip", "self.es.bulk_index"])
    gzip_fn = _make_symbol("utils/compress.py", "compress_gzip")
    es_m = _make_symbol("infra/elasticsearch.py", "bulk_index", "ElasticSearchClient.bulk_index", SymbolKind.METHOD)
    imports = {
        "logging/shipper.py": [
            ImportStatement(source_module="utils.compress", imported_names=["compress_gzip"], is_from=True),
            ImportStatement(source_module="infra.elasticsearch", imported_names=["ElasticSearchClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, gzip_fn, es_m], imports)
    assert gzip_fn.symbol_id in graph[caller.symbol_id]
    assert es_m.symbol_id in graph[caller.symbol_id]


def test_168_finops_cloud_cost_alert():
    caller = _make_symbol("finops/monitor.py", "check_budget_burn", outgoing_calls=["self.billing.get_mtd_spend", "self.slack.send_cost_alert"])
    spend_m = _make_symbol("infra/aws_billing.py", "get_mtd_spend", "AwsBillingClient.get_mtd_spend", SymbolKind.METHOD)
    slack_m = _make_symbol("notify/slack.py", "send_cost_alert", "SlackNotifier.send_cost_alert", SymbolKind.METHOD)
    imports = {
        "finops/monitor.py": [
            ImportStatement(source_module="infra.aws_billing", imported_names=["AwsBillingClient"], is_from=True),
            ImportStatement(source_module="notify.slack", imported_names=["SlackNotifier"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, spend_m, slack_m], imports)
    assert spend_m.symbol_id in graph[caller.symbol_id]
    assert slack_m.symbol_id in graph[caller.symbol_id]


def test_169_disaster_recovery_dns_probe():
    caller = _make_symbol("dr/probe.py", "probe_datacenter", outgoing_calls=["self.http.health_check", "self.dns.failover_traffic"])
    hc_m = _make_symbol("infra/http.py", "health_check", "HttpClient.health_check", SymbolKind.METHOD)
    dns_m = _make_symbol("dns/route53.py", "failover_traffic", "Route53Client.failover_traffic", SymbolKind.METHOD)
    imports = {
        "dr/probe.py": [
            ImportStatement(source_module="infra.http", imported_names=["HttpClient"], is_from=True),
            ImportStatement(source_module="dns.route53", imported_names=["Route53Client"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, hc_m, dns_m], imports)
    assert hc_m.symbol_id in graph[caller.symbol_id]
    assert dns_m.symbol_id in graph[caller.symbol_id]


def test_170_sbom_cve_vulnerability_scanner():
    caller = _make_symbol("security/scanner.py", "scan_sbom", outgoing_calls=["parse_cyclonedx_sbom", "self.nvd.match_cve"])
    sbom_fn = _make_symbol("security/sbom.py", "parse_cyclonedx_sbom")
    cve_m = _make_symbol("security/nvd.py", "match_cve", "NvdClient.match_cve", SymbolKind.METHOD)
    imports = {
        "security/scanner.py": [
            ImportStatement(source_module="security.sbom", imported_names=["parse_cyclonedx_sbom"], is_from=True),
            ImportStatement(source_module="security.nvd", imported_names=["NvdClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, sbom_fn, cve_m], imports)
    assert sbom_fn.symbol_id in graph[caller.symbol_id]
    assert cve_m.symbol_id in graph[caller.symbol_id]


# ============================================================================
# DOMAIN 8: Customer Support & CRM Ticketing (Tests 171 to 180)
# ============================================================================

def test_171_support_email_ticket_ingestion():
    caller = _make_symbol("crm/inbound.py", "ingest_email", outgoing_calls=["parse_mime_body", "self.tickets.create_ticket"])
    mime_fn = _make_symbol("mail/parser.py", "parse_mime_body")
    tick_m = _make_symbol("crm/tickets.py", "create_ticket", "TicketManager.create_ticket", SymbolKind.METHOD)
    imports = {
        "crm/inbound.py": [
            ImportStatement(source_module="mail.parser", imported_names=["parse_mime_body"], is_from=True),
            ImportStatement(source_module="crm.tickets", imported_names=["TicketManager"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, mime_fn, tick_m], imports)
    assert mime_fn.symbol_id in graph[caller.symbol_id]
    assert tick_m.symbol_id in graph[caller.symbol_id]


def test_172_sla_breach_escalation():
    caller = _make_symbol("crm/sla.py", "check_sla_deadlines", outgoing_calls=["self.tickets.find_unanswered", "self.escalate.reassign_tier"])
    unans_m = _make_symbol("crm/tickets.py", "find_unanswered", "TicketManager.find_unanswered", SymbolKind.METHOD)
    tier_m = _make_symbol("crm/escalation.py", "reassign_tier", "EscalationEngine.reassign_tier", SymbolKind.METHOD)
    imports = {
        "crm/sla.py": [
            ImportStatement(source_module="crm.tickets", imported_names=["TicketManager"], is_from=True),
            ImportStatement(source_module="crm.escalation", imported_names=["EscalationEngine"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, unans_m, tier_m], imports)
    assert unans_m.symbol_id in graph[caller.symbol_id]
    assert tier_m.symbol_id in graph[caller.symbol_id]


def test_173_skills_based_agent_routing():
    caller = _make_symbol("crm/router.py", "route_to_agent", outgoing_calls=["self.agents.find_by_skill", "self.load.get_least_busy"])
    skill_m = _make_symbol("crm/agents.py", "find_by_skill", "AgentPool.find_by_skill", SymbolKind.METHOD)
    busy_m = _make_symbol("crm/workload.py", "get_least_busy", "WorkloadBalancer.get_least_busy", SymbolKind.METHOD)
    imports = {
        "crm/router.py": [
            ImportStatement(source_module="crm.agents", imported_names=["AgentPool"], is_from=True),
            ImportStatement(source_module="crm.workload", imported_names=["WorkloadBalancer"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, skill_m, busy_m], imports)
    assert skill_m.symbol_id in graph[caller.symbol_id]
    assert busy_m.symbol_id in graph[caller.symbol_id]


def test_174_macro_variable_interpolator():
    caller = _make_symbol("crm/macro.py", "render_template", outgoing_calls=["extract_placeholders", "self.context.resolve_attribute"])
    plc_fn = _make_symbol("crm/template.py", "extract_placeholders")
    ctx_m = _make_symbol("crm/context.py", "resolve_attribute", "MacroContext.resolve_attribute", SymbolKind.METHOD)
    imports = {
        "crm/macro.py": [
            ImportStatement(source_module="crm.template", imported_names=["extract_placeholders"], is_from=True),
            ImportStatement(source_module="crm.context", imported_names=["MacroContext"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, plc_fn, ctx_m], imports)
    assert plc_fn.symbol_id in graph[caller.symbol_id]
    assert ctx_m.symbol_id in graph[caller.symbol_id]


def test_175_sentiment_analysis_on_chat():
    caller = _make_symbol("crm/sentiment.py", "analyze_transcript", outgoing_calls=["self.nlp.score_polarity", "self.tagger.apply_sentiment_tag"])
    nlp_m = _make_symbol("ai/nlp.py", "score_polarity", "NlpClient.score_polarity", SymbolKind.METHOD)
    tag_m = _make_symbol("crm/tags.py", "apply_sentiment_tag", "TicketTagger.apply_sentiment_tag", SymbolKind.METHOD)
    imports = {
        "crm/sentiment.py": [
            ImportStatement(source_module="ai.nlp", imported_names=["NlpClient"], is_from=True),
            ImportStatement(source_module="crm.tags", imported_names=["TicketTagger"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, nlp_m, tag_m], imports)
    assert nlp_m.symbol_id in graph[caller.symbol_id]
    assert tag_m.symbol_id in graph[caller.symbol_id]


def test_176_omnichannel_thread_consolidation():
    caller = _make_symbol("crm/omnichannel.py", "consolidate_message", outgoing_calls=["self.threads.find_or_create_thread", "self.timeline.append_entry"])
    thr_m = _make_symbol("crm/threads.py", "find_or_create_thread", "ThreadManager.find_or_create_thread", SymbolKind.METHOD)
    time_m = _make_symbol("crm/timeline.py", "append_entry", "TimelineManager.append_entry", SymbolKind.METHOD)
    imports = {
        "crm/omnichannel.py": [
            ImportStatement(source_module="crm.threads", imported_names=["ThreadManager"], is_from=True),
            ImportStatement(source_module="crm.timeline", imported_names=["TimelineManager"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, thr_m, time_m], imports)
    assert thr_m.symbol_id in graph[caller.symbol_id]
    assert time_m.symbol_id in graph[caller.symbol_id]


def test_177_csat_survey_dispatch():
    caller = _make_symbol("crm/csat.py", "on_ticket_resolved", outgoing_calls=["self.surveys.generate_one_click_url", "self.email.send_csat_email"])
    surv_m = _make_symbol("crm/surveys.py", "generate_one_click_url", "SurveyGenerator.generate_one_click_url", SymbolKind.METHOD)
    mail_m = _make_symbol("notify/email.py", "send_csat_email", "EmailService.send_csat_email", SymbolKind.METHOD)
    imports = {
        "crm/csat.py": [
            ImportStatement(source_module="crm.surveys", imported_names=["SurveyGenerator"], is_from=True),
            ImportStatement(source_module="notify.email", imported_names=["EmailService"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, surv_m, mail_m], imports)
    assert surv_m.symbol_id in graph[caller.symbol_id]
    assert mail_m.symbol_id in graph[caller.symbol_id]


def test_178_semantic_knowledge_base_search():
    caller = _make_symbol("crm/kb.py", "suggest_articles", outgoing_calls=["self.embed.embed_query", "self.vector_db.search_articles"])
    emb_m = _make_symbol("ai/embed.py", "embed_query", "EmbeddingClient.embed_query", SymbolKind.METHOD)
    vdb_m = _make_symbol("db/vector.py", "search_articles", "VectorDbClient.search_articles", SymbolKind.METHOD)
    imports = {
        "crm/kb.py": [
            ImportStatement(source_module="ai.embed", imported_names=["EmbeddingClient"], is_from=True),
            ImportStatement(source_module="db.vector", imported_names=["VectorDbClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, emb_m, vdb_m], imports)
    assert emb_m.symbol_id in graph[caller.symbol_id]
    assert vdb_m.symbol_id in graph[caller.symbol_id]


def test_179_levenshtein_duplicate_ticket_check():
    caller = _make_symbol("crm/dedup.py", "check_duplicate", outgoing_calls=["compute_levenshtein", "self.tickets.mark_merged"])
    lev_fn = _make_symbol("utils/strings.py", "compute_levenshtein")
    merge_m = _make_symbol("crm/tickets.py", "mark_merged", "TicketManager.mark_merged", SymbolKind.METHOD)
    imports = {
        "crm/dedup.py": [
            ImportStatement(source_module="utils.strings", imported_names=["compute_levenshtein"], is_from=True),
            ImportStatement(source_module="crm.tickets", imported_names=["TicketManager"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, lev_fn, merge_m], imports)
    assert lev_fn.symbol_id in graph[caller.symbol_id]
    assert merge_m.symbol_id in graph[caller.symbol_id]


def test_180_vip_customer_priority_bypass():
    caller = _make_symbol("crm/vip.py", "prioritize_customer", outgoing_calls=["self.crm.is_vip_tier", "self.queue.jump_to_front"])
    vip_m = _make_symbol("crm/client.py", "is_vip_tier", "CrmClient.is_vip_tier", SymbolKind.METHOD)
    q_m = _make_symbol("queues/priority.py", "jump_to_front", "PriorityQueue.jump_to_front", SymbolKind.METHOD)
    imports = {
        "crm/vip.py": [
            ImportStatement(source_module="crm.client", imported_names=["CrmClient"], is_from=True),
            ImportStatement(source_module="queues.priority", imported_names=["PriorityQueue"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, vip_m, q_m], imports)
    assert vip_m.symbol_id in graph[caller.symbol_id]
    assert q_m.symbol_id in graph[caller.symbol_id]


# ============================================================================
# DOMAIN 9: Data Engineering & Analytics Pipeline (Tests 181 to 190)
# ============================================================================

def test_181_etl_batch_windowing():
    caller = _make_symbol("etl/stream.py", "process_window", outgoing_calls=["self.window.accumulate_events", "self.sink.flush_to_lake"])
    win_m = _make_symbol("etl/window.py", "accumulate_events", "EventWindow.accumulate_events", SymbolKind.METHOD)
    sink_m = _make_symbol("etl/sink.py", "flush_to_lake", "DataLakeSink.flush_to_lake", SymbolKind.METHOD)
    imports = {
        "etl/stream.py": [
            ImportStatement(source_module="etl.window", imported_names=["EventWindow"], is_from=True),
            ImportStatement(source_module="etl.sink", imported_names=["DataLakeSink"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, win_m, sink_m], imports)
    assert win_m.symbol_id in graph[caller.symbol_id]
    assert sink_m.symbol_id in graph[caller.symbol_id]


def test_182_avro_schema_compatibility_check():
    caller = _make_symbol("schema/registry.py", "register_new_schema", outgoing_calls=["self.avro.check_backward_compatibility", "self.repo.save_version"])
    avro_m = _make_symbol("schema/avro.py", "check_backward_compatibility", "AvroCompatibilityChecker.check_backward_compatibility", SymbolKind.METHOD)
    ver_m = _make_symbol("schema/repo.py", "save_version", "SchemaVersionRepo.save_version", SymbolKind.METHOD)
    imports = {
        "schema/registry.py": [
            ImportStatement(source_module="schema.avro", imported_names=["AvroCompatibilityChecker"], is_from=True),
            ImportStatement(source_module="schema.repo", imported_names=["SchemaVersionRepo"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, avro_m, ver_m], imports)
    assert avro_m.symbol_id in graph[caller.symbol_id]
    assert ver_m.symbol_id in graph[caller.symbol_id]


def test_183_parquet_partition_pruning():
    caller = _make_symbol("datalake/reader.py", "query_partition", outgoing_calls=["self.pruner.filter_paths_by_date", "self.parquet.read_row_groups"])
    prun_m = _make_symbol("datalake/pruner.py", "filter_paths_by_date", "PartitionPruner.filter_paths_by_date", SymbolKind.METHOD)
    parq_m = _make_symbol("datalake/parquet.py", "read_row_groups", "ParquetReader.read_row_groups", SymbolKind.METHOD)
    imports = {
        "datalake/reader.py": [
            ImportStatement(source_module="datalake.pruner", imported_names=["PartitionPruner"], is_from=True),
            ImportStatement(source_module="datalake.parquet", imported_names=["ParquetReader"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, prun_m, parq_m], imports)
    assert prun_m.symbol_id in graph[caller.symbol_id]
    assert parq_m.symbol_id in graph[caller.symbol_id]


def test_184_clickstream_sessionization():
    caller = _make_symbol("analytics/sessionizer.py", "process_click", outgoing_calls=["self.state.get_last_click_time", "self.sessions.emit_session_end"])
    state_m = _make_symbol("analytics/state.py", "get_last_click_time", "SessionStateManager.get_last_click_time", SymbolKind.METHOD)
    emit_m = _make_symbol("analytics/events.py", "emit_session_end", "SessionEmitter.emit_session_end", SymbolKind.METHOD)
    imports = {
        "analytics/sessionizer.py": [
            ImportStatement(source_module="analytics.state", imported_names=["SessionStateManager"], is_from=True),
            ImportStatement(source_module="analytics.events", imported_names=["SessionEmitter"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, state_m, emit_m], imports)
    assert state_m.symbol_id in graph[caller.symbol_id]
    assert emit_m.symbol_id in graph[caller.symbol_id]


def test_185_bloom_filter_crawler_dedup():
    caller = _make_symbol("crawler/dedup.py", "is_url_crawled", outgoing_calls=["hash_murmur3", "self.bloom.check_bitset"])
    hash_fn = _make_symbol("utils/hash.py", "hash_murmur3")
    bloom_m = _make_symbol("crawler/bloom.py", "check_bitset", "BloomFilter.check_bitset", SymbolKind.METHOD)
    imports = {
        "crawler/dedup.py": [
            ImportStatement(source_module="utils.hash", imported_names=["hash_murmur3"], is_from=True),
            ImportStatement(source_module="crawler.bloom", imported_names=["BloomFilter"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, hash_fn, bloom_m], imports)
    assert hash_fn.symbol_id in graph[caller.symbol_id]
    assert bloom_m.symbol_id in graph[caller.symbol_id]


def test_186_scd2_dimension_historical_update():
    caller = _make_symbol("dw/scd.py", "update_dimension", outgoing_calls=["self.repo.close_current_row", "self.repo.insert_new_row"])
    close_m = _make_symbol("dw/repo.py", "close_current_row", "DimensionRepo.close_current_row", SymbolKind.METHOD)
    ins_m = _make_symbol("dw/repo.py", "insert_new_row", "DimensionRepo.insert_new_row", SymbolKind.METHOD)
    imports = {
        "dw/scd.py": [
            ImportStatement(source_module="dw.repo", imported_names=["DimensionRepo"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, close_m, ins_m], imports)
    assert close_m.symbol_id in graph[caller.symbol_id]
    assert ins_m.symbol_id in graph[caller.symbol_id]


def test_187_data_quality_null_outlier_pipeline():
    caller = _make_symbol("dq/pipeline.py", "validate_dataframe", outgoing_calls=["self.rules.check_null_ratios", "self.rules.check_zscore_outliers"])
    null_m = _make_symbol("dq/rules.py", "check_null_ratios", "QualityRules.check_null_ratios", SymbolKind.METHOD)
    out_m = _make_symbol("dq/rules.py", "check_zscore_outliers", "QualityRules.check_zscore_outliers", SymbolKind.METHOD)
    imports = {
        "dq/pipeline.py": [
            ImportStatement(source_module="dq.rules", imported_names=["QualityRules"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, null_m, out_m], imports)
    assert null_m.symbol_id in graph[caller.symbol_id]
    assert out_m.symbol_id in graph[caller.symbol_id]


def test_188_cube_metric_aggregator():
    caller = _make_symbol("olap/cube.py", "build_aggregates", outgoing_calls=["self.sql.rollup_by_day", "self.sql.rollup_by_week"])
    day_m = _make_symbol("olap/sql.py", "rollup_by_day", "OlapQueryEngine.rollup_by_day", SymbolKind.METHOD)
    wk_m = _make_symbol("olap/sql.py", "rollup_by_week", "OlapQueryEngine.rollup_by_week", SymbolKind.METHOD)
    imports = {
        "olap/cube.py": [
            ImportStatement(source_module="olap.sql", imported_names=["OlapQueryEngine"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, day_m, wk_m], imports)
    assert day_m.symbol_id in graph[caller.symbol_id]
    assert wk_m.symbol_id in graph[caller.symbol_id]


def test_189_backfill_dag_scheduler():
    caller = _make_symbol("airflow/scheduler.py", "trigger_backfill", outgoing_calls=["self.dag.resolve_upstream_dependencies", "self.executor.launch_task_pod"])
    dag_m = _make_symbol("airflow/dag.py", "resolve_upstream_dependencies", "DagParser.resolve_upstream_dependencies", SymbolKind.METHOD)
    exec_m = _make_symbol("airflow/executor.py", "launch_task_pod", "TaskPodExecutor.launch_task_pod", SymbolKind.METHOD)
    imports = {
        "airflow/scheduler.py": [
            ImportStatement(source_module="airflow.dag", imported_names=["DagParser"], is_from=True),
            ImportStatement(source_module="airflow.executor", imported_names=["TaskPodExecutor"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, dag_m, exec_m], imports)
    assert dag_m.symbol_id in graph[caller.symbol_id]
    assert exec_m.symbol_id in graph[caller.symbol_id]


def test_190_data_provenance_lineage():
    caller = _make_symbol("lineage/tracker.py", "record_transformation", outgoing_calls=["self.lineage.record_input_dataset", "self.lineage.record_output_dataset"])
    in_m = _make_symbol("lineage/graph.py", "record_input_dataset", "LineageGraph.record_input_dataset", SymbolKind.METHOD)
    out_m = _make_symbol("lineage/graph.py", "record_output_dataset", "LineageGraph.record_output_dataset", SymbolKind.METHOD)
    imports = {
        "lineage/tracker.py": [
            ImportStatement(source_module="lineage.graph", imported_names=["LineageGraph"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, in_m, out_m], imports)
    assert in_m.symbol_id in graph[caller.symbol_id]
    assert out_m.symbol_id in graph[caller.symbol_id]


# ============================================================================
# DOMAIN 10: IoT Fleet & Device Telemetry (Tests 191 to 200)
# ============================================================================

def test_191_mqtt_broker_packet_decoding():
    caller = _make_symbol("iot/mqtt.py", "on_packet_received", outgoing_calls=["decode_cbor_payload", "self.devices.update_last_seen"])
    cbor_fn = _make_symbol("codecs/cbor.py", "decode_cbor_payload")
    dev_m = _make_symbol("iot/devices.py", "update_last_seen", "DeviceRegistry.update_last_seen", SymbolKind.METHOD)
    imports = {
        "iot/mqtt.py": [
            ImportStatement(source_module="codecs.cbor", imported_names=["decode_cbor_payload"], is_from=True),
            ImportStatement(source_module="iot.devices", imported_names=["DeviceRegistry"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, cbor_fn, dev_m], imports)
    assert cbor_fn.symbol_id in graph[caller.symbol_id]
    assert dev_m.symbol_id in graph[caller.symbol_id]


def test_192_geofencing_violation_detector():
    caller = _make_symbol("iot/geofence.py", "check_bounds", outgoing_calls=["point_in_polygon", "self.alerts.trigger_tamper_alarm"])
    poly_fn = _make_symbol("geo/polygon.py", "point_in_polygon")
    alert_m = _make_symbol("iot/alerts.py", "trigger_tamper_alarm", "DeviceAlertSystem.trigger_tamper_alarm", SymbolKind.METHOD)
    imports = {
        "iot/geofence.py": [
            ImportStatement(source_module="geo.polygon", imported_names=["point_in_polygon"], is_from=True),
            ImportStatement(source_module="iot.alerts", imported_names=["DeviceAlertSystem"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, poly_fn, alert_m], imports)
    assert poly_fn.symbol_id in graph[caller.symbol_id]
    assert alert_m.symbol_id in graph[caller.symbol_id]


def test_193_ota_firmware_delta_verification():
    caller = _make_symbol("ota/firmware.py", "verify_package", outgoing_calls=["verify_ed25519_signature", "self.storage.fetch_firmware_blob"])
    sig_fn = _make_symbol("security/ed25519.py", "verify_ed25519_signature")
    blob_m = _make_symbol("storage/firmware.py", "fetch_firmware_blob", "FirmwareStorage.fetch_firmware_blob", SymbolKind.METHOD)
    imports = {
        "ota/firmware.py": [
            ImportStatement(source_module="security.ed25519", imported_names=["verify_ed25519_signature"], is_from=True),
            ImportStatement(source_module="storage.firmware", imported_names=["FirmwareStorage"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, sig_fn, blob_m], imports)
    assert sig_fn.symbol_id in graph[caller.symbol_id]
    assert blob_m.symbol_id in graph[caller.symbol_id]


def test_194_device_heartbeat_offline_timeout():
    caller = _make_symbol("iot/heartbeat.py", "check_stale_devices", outgoing_calls=["self.devices.find_silent_devices", "self.events.emit_device_offline"])
    dev_m = _make_symbol("iot/devices.py", "find_silent_devices", "DeviceRegistry.find_silent_devices", SymbolKind.METHOD)
    evt_m = _make_symbol("iot/events.py", "emit_device_offline", "DeviceEventEmitter.emit_device_offline", SymbolKind.METHOD)
    imports = {
        "iot/heartbeat.py": [
            ImportStatement(source_module="iot.devices", imported_names=["DeviceRegistry"], is_from=True),
            ImportStatement(source_module="iot.events", imported_names=["DeviceEventEmitter"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, dev_m, evt_m], imports)
    assert dev_m.symbol_id in graph[caller.symbol_id]
    assert evt_m.symbol_id in graph[caller.symbol_id]


def test_195_battery_drain_anomaly_predictor():
    caller = _make_symbol("iot/battery.py", "predict_drain", outgoing_calls=["compute_exponential_moving_average", "self.alerts.flag_abnormal_consumption"])
    ema_fn = _make_symbol("math/moving_average.py", "compute_exponential_moving_average")
    flg_m = _make_symbol("iot/alerts.py", "flag_abnormal_consumption", "DeviceAlertSystem.flag_abnormal_consumption", SymbolKind.METHOD)
    imports = {
        "iot/battery.py": [
            ImportStatement(source_module="math.moving_average", imported_names=["compute_exponential_moving_average"], is_from=True),
            ImportStatement(source_module="iot.alerts", imported_names=["DeviceAlertSystem"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, ema_fn, flg_m], imports)
    assert ema_fn.symbol_id in graph[caller.symbol_id]
    assert flg_m.symbol_id in graph[caller.symbol_id]


def test_196_c2_command_confirmation_queue():
    caller = _make_symbol("iot/c2.py", "send_actuator_command", outgoing_calls=["self.queue.enqueue_with_ttl", "self.mesh.transmit_packet"])
    q_m = _make_symbol("queues/ttl.py", "enqueue_with_ttl", "TtlQueue.enqueue_with_ttl", SymbolKind.METHOD)
    mesh_m = _make_symbol("mesh/zigbee.py", "transmit_packet", "ZigbeeMeshGateway.transmit_packet", SymbolKind.METHOD)
    imports = {
        "iot/c2.py": [
            ImportStatement(source_module="queues.ttl", imported_names=["TtlQueue"], is_from=True),
            ImportStatement(source_module="mesh.zigbee", imported_names=["ZigbeeMeshGateway"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, q_m, mesh_m], imports)
    assert q_m.symbol_id in graph[caller.symbol_id]
    assert mesh_m.symbol_id in graph[caller.symbol_id]


def test_197_sensor_drift_kalman_filter():
    caller = _make_symbol("iot/kalman.py", "apply_calibration", outgoing_calls=["update_kalman_gain", "self.calibration.store_offset"])
    kal_fn = _make_symbol("math/kalman.py", "update_kalman_gain")
    cal_m = _make_symbol("iot/calibration.py", "store_offset", "SensorCalibrationStore.store_offset", SymbolKind.METHOD)
    imports = {
        "iot/kalman.py": [
            ImportStatement(source_module="math.kalman", imported_names=["update_kalman_gain"], is_from=True),
            ImportStatement(source_module="iot.calibration", imported_names=["SensorCalibrationStore"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, kal_fn, cal_m], imports)
    assert kal_fn.symbol_id in graph[caller.symbol_id]
    assert cal_m.symbol_id in graph[caller.symbol_id]


def test_198_telemetry_downsampling_archival():
    caller = _make_symbol("iot/downsample.py", "aggregate_hourly_sensors", outgoing_calls=["self.tsdb.query_bucket", "self.s3.upload_parquet"])
    tsdb_m = _make_symbol("infra/timescale.py", "query_bucket", "TimescaleClient.query_bucket", SymbolKind.METHOD)
    s3_m = _make_symbol("storage/s3.py", "upload_parquet", "S3StorageClient.upload_parquet", SymbolKind.METHOD)
    imports = {
        "iot/downsample.py": [
            ImportStatement(source_module="infra.timescale", imported_names=["TimescaleClient"], is_from=True),
            ImportStatement(source_module="storage.s3", imported_names=["S3StorageClient"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, tsdb_m, s3_m], imports)
    assert tsdb_m.symbol_id in graph[caller.symbol_id]
    assert s3_m.symbol_id in graph[caller.symbol_id]


def test_199_device_crl_revocation_check():
    caller = _make_symbol("security/crl.py", "validate_device_certificate", outgoing_calls=["self.pki.check_crl_distribution_point", "self.revoked.is_serial_revoked"])
    pki_m = _make_symbol("security/pki.py", "check_crl_distribution_point", "PkiValidator.check_crl_distribution_point", SymbolKind.METHOD)
    rev_m = _make_symbol("security/revoked.py", "is_serial_revoked", "RevocationList.is_serial_revoked", SymbolKind.METHOD)
    imports = {
        "security/crl.py": [
            ImportStatement(source_module="security.pki", imported_names=["PkiValidator"], is_from=True),
            ImportStatement(source_module="security.revoked", imported_names=["RevocationList"], is_from=True),
        ]
    }
    tracer = CallGraphTracer()
    _, graph = tracer.build_call_graph([caller, pki_m, rev_m], imports)
    assert pki_m.symbol_id in graph[caller.symbol_id]
    assert rev_m.symbol_id in graph[caller.symbol_id]


def test_200_smart_city_enterprise_megagraph():
    """Simulates a complex smart city infrastructure with 50 nodes and 10 modules."""
    nodes = []
    imports = {}
    
    # 10 subsystem coordinators
    for m in range(10):
        mod_name = f"subsystem_{m}"
        coord = _make_symbol(f"city/{mod_name}/coord.py", f"run_{mod_name}", kind=SymbolKind.ROUTE, outgoing_calls=[f"handler_{m}_a", f"handler_{m}_b"])
        h_a = _make_symbol(f"city/{mod_name}/handlers.py", f"handler_{m}_a", outgoing_calls=["shared_emergency_alert" if m == 0 else f"worker_{m}"])
        h_b = _make_symbol(f"city/{mod_name}/handlers.py", f"handler_{m}_b", outgoing_calls=[f"worker_{m}"])
        w_m = _make_symbol(f"city/{mod_name}/workers.py", f"worker_{m}", outgoing_calls=["global_logger"])
        nodes.extend([coord, h_a, h_b, w_m])

        imports[f"city/{mod_name}/coord.py"] = [
            ImportStatement(source_module=f"city.{mod_name}.handlers", imported_names=[f"handler_{m}_a", f"handler_{m}_b"], is_from=True)
        ]
        imports[f"city/{mod_name}/handlers.py"] = [
            ImportStatement(source_module=f"city.{mod_name}.workers", imported_names=[f"worker_{m}"], is_from=True),
            ImportStatement(source_module="city.common.alerts", imported_names=["shared_emergency_alert"], is_from=True),
        ]
        imports[f"city/{mod_name}/workers.py"] = [
            ImportStatement(source_module="city.common.logging", imported_names=["global_logger"], is_from=True)
        ]

    shared_alert = _make_symbol("city/common/alerts.py", "shared_emergency_alert", outgoing_calls=["global_logger"])
    shared_log = _make_symbol("city/common/logging.py", "global_logger")
    nodes.extend([shared_alert, shared_log])
    imports["city/common/alerts.py"] = [
        ImportStatement(source_module="city.common.logging", imported_names=["global_logger"], is_from=True)
    ]

    tracer = CallGraphTracer()
    calls, graph = tracer.build_call_graph(nodes, imports)

    assert len(calls) >= 50
    assert len(graph) >= 30
    # Verify subsystem 0 connects to emergency alert and global logger
    sub0_coord = "city/subsystem_0/coord.py:run_subsystem_0"
    sub0_ha = "city/subsystem_0/handlers.py:handler_0_a"
    assert sub0_ha in graph[sub0_coord]
    assert shared_alert.symbol_id in graph[sub0_ha]
    assert shared_log.symbol_id in graph[shared_alert.symbol_id]


def run_all_enterprise_tests():
    print("Running 100 Enterprise Product-Oriented Call Graph Tests (Tests 101 to 200)...")

    # Domain 1: Fintech (101-110)
    test_101_idempotent_payment_intent_creation()
    test_102_two_phase_commit_capture()
    test_103_double_entry_bookkeeping_balancing()
    test_104_three_d_secure_webhook_signature()
    test_105_refund_cascade_with_fee_reversal()
    test_106_card_vault_tokenization_and_pci_sanitization()
    test_107_fx_currency_conversion_spread()
    test_108_fraud_risk_scoring_pipeline()
    test_109_dispute_evidence_submission()
    test_110_merchant_settlement_batch()

    # Domain 2: E-Commerce (111-120)
    test_111_order_checkout_cart_validation()
    test_112_tiered_coupon_evaluator()
    test_113_distributed_inventory_reservation()
    test_114_multi_carrier_shipping_quoter()
    test_115_tax_calculation_engine_regional()
    test_116_warehouse_pick_pack_dispatch()
    test_117_out_of_stock_backorder_trigger()
    test_118_rma_return_inspection_workflow()
    test_119_customer_loyalty_points_accrual()
    test_120_abandoned_cart_recovery()

    # Domain 3: SaaS & RBAC (121-130)
    test_121_tenant_context_middleware()
    test_122_abac_policy_evaluator()
    test_123_org_hierarchy_role_inheritance()
    test_124_oauth2_authorization_code_exchange()
    test_125_api_key_permission_mask()
    test_126_usage_based_metering()
    test_127_dynamic_feature_flag_evaluator()
    test_128_webhook_dispatcher_dlq()
    test_129_audit_log_producer()
    test_130_session_invalidation_cascade()

    # Domain 4: Ride-Sharing (131-140)
    test_131_ride_request_geohash_lookup()
    test_132_nearest_driver_distance_matrix()
    test_133_dynamic_surge_pricing()
    test_134_trip_lifecycle_state_machine()
    test_135_gps_telemetry_streaming()
    test_136_fare_calculation_tolls()
    test_137_split_fare_acceptance()
    test_138_driver_cancellation_penalty()
    test_139_weekly_driver_payout_surcharge()
    test_140_lost_and_found_incident_matching()

    # Domain 5: Healthcare (141-150)
    test_141_appointment_slot_booking()
    test_142_ehr_encryption_decryption()
    test_143_prescription_pki_signing()
    test_144_insurance_preauth_adjudication()
    test_145_webrtc_video_consultation_token()
    test_146_lab_results_abnormal_alert()
    test_147_patient_consent_verification()
    test_148_icd10_coding_validator()
    test_149_emergency_physician_pager()
    test_150_hipaa_compliance_export()

    # Domain 6: Content & Social (151-160)
    test_151_video_chunk_transcoding_job()
    test_152_content_moderation_pipeline()
    test_153_social_graph_follow_edge()
    test_154_fan_out_on_write_inboxes()
    test_155_celebrity_fan_out_on_read()
    test_156_cdn_presigned_url_hmac()
    test_157_live_stream_comment_broadcast()
    test_158_trending_hashtag_counter()
    test_159_e2e_encryption_key_exchange()
    test_160_audio_fingerprint_matching()

    # Domain 7: Cloud & DevOps (161-170)
    test_161_k8s_hpa_scaler()
    test_162_canary_release_traffic_splitter()
    test_163_vault_secret_rotation()
    test_164_cloud_storage_lifecycle_worker()
    test_165_acme_tls_cert_renewal()
    test_166_redlock_distributed_lock()
    test_167_fluentd_log_buffer_flush()
    test_168_finops_cloud_cost_alert()
    test_169_disaster_recovery_dns_probe()
    test_170_sbom_cve_vulnerability_scanner()

    # Domain 8: CRM & Support (171-180)
    test_171_support_email_ticket_ingestion()
    test_172_sla_breach_escalation()
    test_173_skills_based_agent_routing()
    test_174_macro_variable_interpolator()
    test_175_sentiment_analysis_on_chat()
    test_176_omnichannel_thread_consolidation()
    test_177_csat_survey_dispatch()
    test_178_semantic_knowledge_base_search()
    test_179_levenshtein_duplicate_ticket_check()
    test_180_vip_customer_priority_bypass()

    # Domain 9: Data Engineering (181-190)
    test_181_etl_batch_windowing()
    test_182_avro_schema_compatibility_check()
    test_183_parquet_partition_pruning()
    test_184_clickstream_sessionization()
    test_185_bloom_filter_crawler_dedup()
    test_186_scd2_dimension_historical_update()
    test_187_data_quality_null_outlier_pipeline()
    test_188_cube_metric_aggregator()
    test_189_backfill_dag_scheduler()
    test_190_data_provenance_lineage()

    # Domain 10: IoT Fleet (191-200)
    test_191_mqtt_broker_packet_decoding()
    test_192_geofencing_violation_detector()
    test_193_ota_firmware_delta_verification()
    test_194_device_heartbeat_offline_timeout()
    test_195_battery_drain_anomaly_predictor()
    test_196_c2_command_confirmation_queue()
    test_197_sensor_drift_kalman_filter()
    test_198_telemetry_downsampling_archival()
    test_199_device_crl_revocation_check()
    test_200_smart_city_enterprise_megagraph()

    print("🎉 ALL 100 Enterprise Product-Oriented test cases passed successfully!")


if __name__ == "__main__":
    run_all_enterprise_tests()
