"""Stripe billing endpoints.

Flow:
  POST /billing/checkout  → creates Stripe Checkout Session, returns URL
  GET  /billing/success   → Stripe redirect target; bounces to docchat:// deep link
  GET  /billing/cancel    → same for cancellation
  GET  /billing/status    → current plan for the logged-in user
  POST /billing/portal    → creates Customer Portal session for managing subscription
  POST /billing/webhook   → Stripe event sink (no JWT; verified via signature)
"""

from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.routes.auth import current_user_id
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.storage.subscription_store import SubscriptionRecord, get_subscription_store
from app.services.storage.user_store import UserStore

logger = get_logger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

FREE_TIER_LABEL = "1 MB"
PRO_TIER_LABEL = "50 MB"


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _stripe_client(settings: Settings) -> None:
    stripe.api_key = settings.stripe_secret_key


def _get_or_create_customer(user_id: str, email: str, settings: Settings) -> str:
    """Return existing Stripe customer ID or create one."""
    store = get_subscription_store()
    record = store.get(user_id)
    if record and record.stripe_customer_id:
        return record.stripe_customer_id

    customer = stripe.Customer.create(
        email=email,
        metadata={"user_id": user_id},
    )
    return customer.id


# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #

class CheckoutResponse(BaseModel):
    url: str


class BillingStatusResponse(BaseModel):
    plan: str                     # "free" | "pro"
    status: str                   # "active" | "inactive" | "past_due" | "canceled"
    current_period_end: str | None


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #

@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    user_id: str = Depends(current_user_id),
    settings: Settings = Depends(get_settings),
) -> CheckoutResponse:
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Billing is not configured on this server")

    _stripe_client(settings)

    user_store = UserStore(settings)
    user = user_store.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    customer_id = _get_or_create_customer(user_id, user.email, settings)

    # Persist customer mapping immediately so webhook can find the user later.
    sub_store = get_subscription_store()
    existing = sub_store.get(user_id)
    if not existing:
        sub_store.upsert(SubscriptionRecord(
            user_id=user_id,
            stripe_customer_id=customer_id,
        ))
    elif not existing.stripe_customer_id:
        existing.stripe_customer_id = customer_id
        sub_store.upsert(existing)

    base = settings.server_base_url.rstrip("/")
    session = stripe.checkout.Session.create(
        customer=customer_id,
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/billing/cancel",
        metadata={"user_id": user_id},
    )
    logger.info("checkout session created for user %s", user_id)
    return CheckoutResponse(url=session.url)


@router.get("/success")
def billing_success(session_id: str = "") -> RedirectResponse:
    """Stripe bounces here after payment; we redirect to the app's deep link."""
    return RedirectResponse(url=f"docchat://billing/success?session_id={session_id}")


@router.get("/cancel")
def billing_cancel() -> RedirectResponse:
    return RedirectResponse(url="docchat://billing/cancel")


@router.get("/status", response_model=BillingStatusResponse)
def billing_status(
    user_id: str = Depends(current_user_id),
) -> BillingStatusResponse:
    record = get_subscription_store().get(user_id)
    if record and record.is_pro:
        return BillingStatusResponse(
            plan="pro",
            status=record.status,
            current_period_end=record.current_period_end or None,
        )
    return BillingStatusResponse(plan="free", status="inactive", current_period_end=None)


@router.post("/portal", response_model=CheckoutResponse)
def create_portal(
    user_id: str = Depends(current_user_id),
    settings: Settings = Depends(get_settings),
) -> CheckoutResponse:
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Billing is not configured on this server")

    _stripe_client(settings)
    record = get_subscription_store().get(user_id)
    if not record or not record.stripe_customer_id:
        raise HTTPException(404, "No billing account found")

    base = settings.server_base_url.rstrip("/")
    session = stripe.billing_portal.Session.create(
        customer=record.stripe_customer_id,
        return_url=f"{base}/billing/cancel",
    )
    return CheckoutResponse(url=session.url)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
    settings: Settings = Depends(get_settings),
):
    """Raw-body endpoint — Stripe sends events here after payment lifecycle changes."""
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Billing not configured")

    _stripe_client(settings)
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    store = get_subscription_store()
    event_type: str = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        if not user_id or not subscription_id:
            return {"status": "skipped"}

        sub = stripe.Subscription.retrieve(subscription_id)
        period_end = _ts(sub.get("current_period_end"))
        record = store.get(user_id) or SubscriptionRecord(
            user_id=user_id, stripe_customer_id=customer_id or ""
        )
        record.stripe_customer_id = customer_id or record.stripe_customer_id
        record.stripe_subscription_id = subscription_id
        record.status = "active"
        record.current_period_end = period_end
        store.upsert(record)
        logger.info("subscription activated for user %s", user_id)

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_id = data.get("customer")
        record = store.get_by_customer(customer_id)
        if record:
            record.stripe_subscription_id = data.get("id", record.stripe_subscription_id)
            record.status = (
                "canceled" if event_type == "customer.subscription.deleted"
                else _map_status(data.get("status", "inactive"))
            )
            record.current_period_end = _ts(data.get("current_period_end"))
            store.upsert(record)
            logger.info(
                "subscription %s for customer %s → %s",
                event_type, customer_id, record.status,
            )

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        record = store.get_by_customer(customer_id)
        if record:
            record.status = "past_due"
            store.upsert(record)
            logger.info("payment failed for customer %s", customer_id)

    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Utilities                                                                    #
# --------------------------------------------------------------------------- #

def _ts(unix: int | None) -> str:
    if not unix:
        return ""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(unix, tz=timezone.utc).isoformat()


def _map_status(stripe_status: str) -> str:
    return {
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "trialing": "active",
    }.get(stripe_status, "inactive")
