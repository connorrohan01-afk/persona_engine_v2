"""
State machine definition.

GREETING → WARMUP → OFFER → PAYMENT_PENDING → DELIVERY → UPSELL → EXIT

All transitions are executed by handler code — never by the LLM.
"""

from enum import Enum


class State(str, Enum):
    GREETING        = "GREETING"
    WARMUP          = "WARMUP"
    OFFER           = "OFFER"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    DELIVERY        = "DELIVERY"
    UPSELL          = "UPSELL"
    EXIT            = "EXIT"


# Valid one-step transitions
TRANSITIONS: dict[State, list[State]] = {
    State.GREETING:        [State.WARMUP],
    State.WARMUP:          [State.OFFER],
    State.OFFER:           [State.PAYMENT_PENDING],
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
