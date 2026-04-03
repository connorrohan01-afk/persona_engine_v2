"""
State machine definition.

GREETING → WARMUP → CURIOSITY → SOFT_INVITE → OFFER → PREVIEW → PAYMENT_PENDING → DELIVERY → UPSELL → EXIT

All transitions are executed by handler code — never by the LLM.
"""

from enum import Enum


class State(str, Enum):
    GREETING        = "GREETING"
    WARMUP          = "WARMUP"
    CURIOSITY       = "CURIOSITY"
    SOFT_INVITE     = "SOFT_INVITE"
    OFFER           = "OFFER"
    PREVIEW         = "PREVIEW"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    DELIVERY        = "DELIVERY"
    UPSELL          = "UPSELL"
    EXIT            = "EXIT"


# Valid transitions — code controls these, never the LLM
TRANSITIONS: dict[State, list[State]] = {
    State.GREETING:        [State.WARMUP],
    State.WARMUP:          [State.WARMUP, State.CURIOSITY],
    State.CURIOSITY:       [State.SOFT_INVITE],
    State.SOFT_INVITE:     [State.OFFER, State.WARMUP],
    State.OFFER:           [State.PREVIEW],
    State.PREVIEW:         [State.PAYMENT_PENDING],
    State.PAYMENT_PENDING: [State.DELIVERY],
    State.DELIVERY:        [State.UPSELL],
    State.UPSELL:          [State.OFFER, State.EXIT],
    State.EXIT:            [],
}


def can_transition(current: str, target: str) -> bool:
    try:
        c = State(current)
        t = State(target)
    except ValueError:
        return False
    return t in TRANSITIONS.get(c, [])
