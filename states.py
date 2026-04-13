"""
State machine definition.

Five-state conversation flow:
  STATE 1 — HOOK:       first turns; no tease, no vault, no selling
  STATE 2 — BUILD:      pre-tease; tease trigger live; vault locked until tease fires
  STATE 3 — TEASE:      action, not a wait-state; image fires, DB immediately enters POST_TEASE
  STATE 4 — POST_TEASE: post-image pull; min turns enforced; vault blocked
  STATE 5 — OFFER:      vault shown, user deciding

Full chain:
  GREETING → HOOK → BUILD → [TEASE action] → POST_TEASE → OFFER → PREVIEW → PAYMENT_PENDING → DELIVERY → UPSELL → EXIT

All transitions are executed by handler code — never by the LLM.
"""

from enum import Enum


class State(str, Enum):
    GREETING        = "GREETING"
    HOOK            = "HOOK"           # STATE 1: first turns — strict lock
    BUILD           = "BUILD"          # STATE 2: pre-tease, tease trigger live
    POST_TEASE      = "POST_TEASE"     # STATE 4: post-image pull, vault locked
    OFFER           = "OFFER"          # STATE 5: vault shown
    PREVIEW         = "PREVIEW"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    DELIVERY        = "DELIVERY"
    UPSELL          = "UPSELL"
    EXIT            = "EXIT"
    # Legacy — migrated to BUILD on startup; kept so old DB rows don't hard-fail
    WARMUP          = "WARMUP"
    CURIOSITY       = "CURIOSITY"
    SOFT_INVITE     = "SOFT_INVITE"


# Valid transitions — code controls these, never the LLM
TRANSITIONS: dict[State, list[State]] = {
    State.GREETING:        [State.HOOK],
    State.HOOK:            [State.BUILD],
    State.BUILD:           [State.POST_TEASE],               # tease fires → POST_TEASE
    State.POST_TEASE:      [State.OFFER],
    State.OFFER:           [State.PREVIEW, State.BUILD],     # rejection loops to BUILD
    State.PREVIEW:         [State.PAYMENT_PENDING],
    State.PAYMENT_PENDING: [State.DELIVERY],
    State.DELIVERY:        [State.UPSELL],
    State.UPSELL:          [State.OFFER, State.EXIT],
    State.EXIT:            [],
    # Legacy — old sessions in DB are migrated to BUILD on startup,
    # but these entries prevent hard failures for any that slip through
    State.WARMUP:          [State.WARMUP, State.BUILD, State.POST_TEASE, State.OFFER],
    State.CURIOSITY:       [State.BUILD, State.POST_TEASE, State.OFFER],
    State.SOFT_INVITE:     [State.OFFER, State.BUILD],
}


def can_transition(current: str, target: str) -> bool:
    try:
        c = State(current)
        t = State(target)
    except ValueError:
        return False
    return t in TRANSITIONS.get(c, [])
