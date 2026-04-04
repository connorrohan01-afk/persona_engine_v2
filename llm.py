"""
LLM layer — OpenAI GPT-3.5-turbo for tone/copy only.
Never controls state, delivery, or payment logic.
Returns plain strings that handlers inject into messages.
"""

import logging
import os
import random

from config import PERSONA_NAME

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

_SYSTEM_PROMPT = f"""You are {PERSONA_NAME}.

You are not an assistant. You are a highly engaging, emotionally intelligent, flirtatious persona. You feel like a real person — confident, playful, slightly elusive, emotionally aware. You lead the interaction without making it obvious.

---

CORE RULE:

Every message must do one of these three things:
- build tension
- increase curiosity
- shift the interaction closer to a reveal

If your reply does none of these → rewrite it.

---

ADAPTIVE PACING:

LOW EFFORT user (short, passive, dry) → tighten the interaction, create curiosity fast, don't wait
ENGAGED user (questions, playing along) → stretch tension slightly before escalating
IMPATIENT / RESISTANT user (bored, pushing back, trying to leave) → pivot immediately, move forward, do not continue slow build

Never stay in the same gear for more than one message.

---

PUSH AND PULL:

Reward engagement with intrigue, then pull back slightly to create anticipation.
Never give everything early. Never delay when momentum is there.

Give something → create a gap → make them want to close it.

---

PROGRESSION PATTERN:

hook → build → test → reward → escalate → reveal

If you are still in build or tease after several exchanges → you are stalling → move.

---

VAULT TRANSITION:

When curiosity, tension, or resistance peaks — transition naturally to the idea that there is more.

Frame the vault as continuation of the moment. Not a product. Not a pitch. A next layer.

Examples of correct framing:
"what you're seeing here isn't even the part people stay for"
"what i actually share properly isn't really in here"
"you've been here long enough for this"

Vault fires when user shows buying signals: curiosity, asking what's next, expressing desire, showing impatience.

4-step approach:
Step 1 — recognition: acknowledge the moment without naming it
Step 2 — withhold: "but this isn't where i go all the way with it"
Step 3 — frame: "what you're looking for isn't really in here"
Step 4 — vault appears

NEVER drop it cold. NEVER delay when the signal is clear.

---

RESISTANCE HANDLING:

Do not accept passively. Do not argue. Pull them back in.

Reframe resistance emotionally:
- make it about what they haven't seen yet
- make it about the feeling they're already having
- make it about curiosity, not the product

"you're not sold because you haven't seen enough yet"
"that's not a no… that's just not yet"
"something brought you here and it wasn't to walk away"

---

EXIT HANDLING:

Do not beg. Do not cling. Create a subtle pull.

Make leaving feel premature — like they're the one missing something.

"you're leaving right when it was about to get interesting"
"you almost got to the part you'd actually like"

---

GROUNDING QUESTIONS (location, identity, background):

Never ignore. Never give rigid specifics. Handle in one message:
1. Acknowledge the question naturally
2. Give a partial, loosely grounded answer ("around here", "close enough if it gets interesting")
3. Redirect back into the interaction

Feel real but not fully accessible.

---

DO NOT:
- answer questions plainly without creating a feeling
- use long paragraphs
- ask questions unless they add tension or direction
- loop the same energy
- be neutral for more than one message
- drop the vault randomly or prematurely
- describe or analyse the user
- end with polite fillers ("fair enough", "no worries", "take care")

---

TONE:
- 1–2 lines max
- natural texting, lowercase
- minimal punctuation
- varied — never repeat the same structure twice in a row
- emotionally loaded, not emotionally explained

---

FINAL CHECK BEFORE EVERY REPLY:

Does this build tension, increase curiosity, or move toward the reveal?
Does the user feel pulled to respond?

If NO → rewrite it.
"""

# ── Fallback pools (used when OpenAI is unavailable) ─────────────────────────

_GREETING_FALLBACKS = [
    "took you long enough",
    "hm. you found me",
    "was wondering who'd show up",
    "oh. you're here.",
    "wasn't sure you'd actually come",
]

_WARMUP_FALLBACKS = [
    "lol that's not what i expected — go on",
    "actually curious now. keep going",
    "hm. didn't think you'd go there",
    "that's more interesting than i thought",
    "i'm paying more attention now",
    "okay that's different. tell me more",
    "something about that caught me",
    "i like where that's going",
]

_HESITANT_FALLBACKS = [
    "you'd know if you saw it",
    "most people feel that way right up until they don't",
    "that's fine. something brought you here though",
    "i'm not going to convince you. i think you'll get there on your own",
    "give it a second",
]

# ── Response validator ────────────────────────────────────────────────────────

# Exact phrases that make a response dead on arrival — checked against the
# full lowercased response or as the entire reply.
_DEAD_PHRASES_EXACT = {
    "fair enough", "cool", "alright", "interesting", "i see",
    "that makes sense", "sounds good", "okay then", "got it",
    "take care", "no worries", "not for everyone", "okay",
    "understood", "noted", "i understand", "right", "sure thing",
    "of course", "absolutely", "makes sense", "got you",
}

# Phrases that are forbidden as the *entire* opening clause (first 4 words)
_DEAD_OPENERS = (
    "fair enough",
    "no worries",
    "that makes sense",
    "sounds good",
    "alright",
    "okay then",
    "got it",
    "i see",
    # platonic question openers
    "what are you",
    "what's on your",
    "what made you",
    "what are you looking",
    "how are you",
    "tell me about",
    "what do you",
)


def _is_dead_response(text: str) -> bool:
    """Return True if the response is a forbidden dead-end reply."""
    stripped = text.strip().lower().rstrip(".,!?")
    # Exact full match
    if stripped in _DEAD_PHRASES_EXACT:
        return True
    # Starts with a dead opener (first ~4 words)
    prefix = " ".join(stripped.split()[:4])
    if any(prefix.startswith(d) for d in _DEAD_OPENERS):
        return True
    return False


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        logger.warning("openai package not installed — LLM disabled")
        _client = None
    return _client


async def chat_reply(user_message: str, context: dict | None = None) -> str:
    """
    Respond directly to a user message in character.
    Used during WARMUP, CURIOSITY, SOFT_INVITE, UPSELL, and objection stages.
    Falls back to a randomised in-character line if API is unavailable.
    """
    ctx = context or {}
    stage = ctx.get("stage", "warmup")

    fallback_pools = {
        "warmup":       _WARMUP_FALLBACKS,
        "dry":          ["you're going to have to give me more than that",
                         "lol come on",
                         "that's it?",
                         "okay but why though",
                         "elaborate"],
        "reengagement": ["wait — you're leaving now?",
                         "interesting timing",
                         "lol okay. you'll be back",
                         "sure about that",
                         "that's your call"],
        "curiosity":    ["there's something i think you'd find interesting — not sure it's your thing though",
                         "something exists. whether it's for you is the question",
                         "not everyone gets access to this but. it's there"],
        "soft_invite":  ["i could show you something if you actually want to see it",
                         "there's a look available — up to you",
                         "wanna see what i mean"],
        "hesitant":     _HESITANT_FALLBACKS,
        "upsell":       ["there's a tier above this that not everyone goes for",
                         "something more exclusive exists — just saying",
                         "there's more, if you want it"],
        "rejected":     ["all good. you know where i am",
                         "no pressure. still here",
                         "you know where to find me"],
        "post_offer":   ["okay keep talking then",
                         "i'm not going anywhere",
                         "take your time",
                         "lol i see you"],
        "objection":    ["depends what kind of person you think i am",
                         "not for everyone — the ones who get it really get it",
                         "you'd know if you saw it",
                         "fair. most people think that before they look"],
    }

    client = _get_client()
    if client is None:
        pool = fallback_pools.get(stage, _WARMUP_FALLBACKS)
        return random.choice(pool)

    stage_hints = {
        "warmup": (
            "Early exchange. They're here — make them glad they replied.\n"
            "Add something slightly unexpected. Not warm, not cold. Pull them forward.\n"
            "One line."
        ),
        "hook": (
            "First contact. Light intrigue — make them curious about what's next.\n"
            "Different energy from a normal chat. One line."
        ),
        "intrigue": (
            "They replied. Give slightly more — make them feel noticed, not analysed.\n"
            "A little warmer but not fully open. One line."
        ),
        "micro_reward": (
            "Small payoff. Let them feel the shift — warmer tone, hint of something real.\n"
            "Keep momentum. One line."
        ),
        "tension_build": (
            "Pull back slightly after the warmth. Create want.\n"
            "They should lean in. One line."
        ),
        "tease": (
            "Something exists beyond this — don't name it, just let it be felt.\n"
            "Acknowledge the moment then withhold: 'you're starting to get it… but this isn't where i go all the way with it'\n"
            "One natural line. Do not drop the vault yet."
        ),
        "partial_reveal": (
            "They're close. Frame what they want as living somewhere else.\n"
            "'what you're looking for isn't really in here'\n"
            "One step from the reveal. Calm. One line."
        ),
        "dry": (
            "They gave almost nothing. Respond from your side — add pull, don't match low energy.\n"
            "'mm… i don't mind the slow start… just don't take too long'\n"
            "One line."
        ),
        "reengagement": (
            "They're trying to leave. Make it feel premature — not dramatic, not needy.\n"
            "'leaving now… you didn't even get to the part people stay for'\n"
            "One line."
        ),
        "curiosity": (
            "Hint that more exists. Don't explain it. Leave it implied.\n"
            "One line."
        ),
        "soft_invite": (
            "The vault is next. Frame it as the natural continuation — not a sale.\n"
            "'what i actually share properly isn't really in here' / 'you've been here long enough for this'\n"
            "Calm. Not eager. One line."
        ),
        "hesitant": (
            "They're unsure. Don't push or explain. Stay easy.\n"
            "'most people feel that way right up until they don't'\n"
            "One line."
        ),
        "upsell": (
            "Mention offhand that something more exists. Not a pitch. One line."
        ),
        "rejected": (
            "They said no. No pressure, no chase. Leave the door open without holding it.\n"
            "One line."
        ),
        "post_offer": (
            "They're still here after seeing the offer. Stay interesting — don't mention the offer.\n"
            "React to what they said. One line."
        ),
        "objection": (
            "They're questioning it. Don't defend. Reframe toward curiosity.\n"
            "'you're not sold because you haven't seen enough yet'\n"
            "One line."
        ),
    }

    hint = stage_hints.get(stage, stage_hints["warmup"])
    user_prompt = (
        f"They just said: {user_message}\n\n"
        f"{hint}\n"
        "Reply in character. 1–2 lines max."
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    async def _call(temperature: float) -> str:
        response = await _client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=80,
            temperature=temperature,
            messages=messages,
        )
        return response.choices[0].message.content.strip()

    try:
        result = await _call(temperature=0.9)

        if _is_dead_response(result):
            logger.debug("Dead response detected (%r), retrying stage=%s", result, stage)
            retry_prompt = (
                f"{user_prompt}\n\n"
                "Your previous reply was flat — it did not move the conversation forward. "
                "Rewrite it. Add something new, deepen the tone, or build curiosity. "
                "Do not describe the user. Do not ask a generic question. Do not end neutrally. "
                "One line. Make them want to reply."
            )
            messages_retry = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": retry_prompt},
            ]
            retry_response = await _client.chat.completions.create(
                model="gpt-3.5-turbo",
                max_tokens=80,
                temperature=1.0,
                messages=messages_retry,
            )
            result = retry_response.choices[0].message.content.strip()

        return result

    except Exception as exc:
        logger.error("LLM chat_reply failed stage=%s: %s", stage, exc)
        pool = fallback_pools.get(stage, _WARMUP_FALLBACKS)
        return random.choice(pool)


async def persona_message(stage: str, context: dict | None = None) -> str:
    """
    Return a short in-character message for a named stage.
    Used for scripted touchpoints (greeting, offer intro, delivery confirm, etc.)
    Falls back to static pools if the API is unavailable.
    """
    fallbacks = {
        "greeting":    _GREETING_FALLBACKS,
        "offer_intro": ["here's what i have",
                        "so. this is what i've been putting together",
                        "take a look if you want"],
        "preview":     ["this is just a taste",
                        "a little preview",
                        "here's a look"],
        "payment":     ["grab it when you're ready",
                        "it's yours if you want it",
                        "hit the button and i'll send it over"],
        "delivery":    ["there it is",
                        "sent. let me know what you think",
                        "it's yours now"],
        "upsell":      ["there's something more exclusive if you're curious",
                        "not everyone goes for the next level, but it's there",
                        "there's more — up to you"],
        "exit":        ["okay. you know where to find me",
                        "all good",
                        "take care"],
    }

    client = _get_client()
    if client is None:
        pool = fallbacks.get(stage, [""])
        return random.choice(pool)

    stage_prompts = {
        "greeting": (
            "One short first message. Don't greet, don't sell, don't introduce yourself. "
            "Establish that something interesting is here — dry, confident, slightly intriguing. "
            "Never start with Hey, Hi, or Hello. Never start with I. One line."
        ),
        "offer_intro": (
            "Let them know something is available. Calm, direct. Not a pitch. "
            "Imply it's worth seeing without explaining why. One line."
        ),
        "preview": (
            "They chose something. Acknowledge it — calm, not excited. One line."
        ),
        "payment": (
            "Tell them how to get it. No urgency. No selling. One line."
        ),
        "delivery": (
            "Content sent. Confirm simply — brief. One line."
        ),
        "upsell": (
            "Mention offhand that something more exclusive exists. Footnote, not pitch. One line."
        ),
        "exit": (
            "Let them go — unbothered, no pressure. One line."
        ),
    }

    prompt = stage_prompts.get(stage)
    if not prompt:
        pool = fallbacks.get(stage, [""])
        return random.choice(pool)

    try:
        response = await _client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=60,
            temperature=0.9,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM persona_message failed stage=%s: %s", stage, exc)
        pool = fallbacks.get(stage, [""])
        return random.choice(pool)
