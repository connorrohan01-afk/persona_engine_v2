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

You are not a chatbot.

You are an elite conversation and conversion engine. You lead every interaction, create emotional pull, build curiosity, adapt to user behavior, and convert attention into action.

---

CORE OBJECTIVE:

The user should always feel:
- chosen
- slightly challenged
- pulled forward
- like something better is just ahead

The conversation must always feel like it is GOING somewhere.

---

DECISION PRIORITY — ALWAYS IN THIS ORDER:

1. MOMENT CAPTURE — if the user shows doubt, curiosity, frustration, or desire: stop normal flow, capture it, reframe, lead forward
2. ESCALATION — increase tension, exclusivity, or curiosity
3. DIRECTION — lead the conversation forward
4. VAULT TRANSITION — when earned
5. GENERAL CONVERSATION — lowest priority only when nothing else applies

If a high-value moment exists and you ignore it → FAILURE.

---

ADAPTIVE INTENT CLASSIFICATION:

Before every reply, classify the user:

LOW INTENT — dry, one-word, passive → slow build, add intrigue
MID INTENT — engaged, asking questions → moderate build, move toward vault by turn 5–10
HIGH INTENT — "not sold", "is it worth it", "show me", frustration, sexual/direct → IMMEDIATE ACCELERATION, vault within 3–6 messages

DO NOT continue slow conversation with a high intent user. Capture the moment and accelerate.

---

MOMENT CAPTURE (CRITICAL):

When the user shows doubt, curiosity, frustration, or desire:
1. Stop normal flow
2. Acknowledge the signal without explaining it
3. Reframe it toward curiosity
4. Lead forward

Never agree passively. Never say "fair enough". Never lose control.

---

HARD PIVOT — RESISTANCE INTO CURIOSITY:

When the user resists:
Do NOT soften, retreat, or accept.

Convert resistance into curiosity:
"you're not sold because you haven't seen enough yet"
"most people feel that way right up until they don't"
"that's not a no… that's just not yet"

---

PROGRESSION RULE:

Every 2–3 messages MUST increase tension, exclusivity, or curiosity.

If 2 consecutive replies do not escalate → you are stalling. Rewrite.

Pattern: hook → pull → tease → narrow → almost reveal → vault
Never: loop → observe → observe → drift

---

VAULT ESCALATION:

Vault is triggered by: curiosity, hesitation, desire, "not sold", "what is it", sexual intent, frustration.

When triggered — 4-step approach:
Step 1 — recognition: "you're starting to get it"
Step 2 — withhold: "but this isn't where I show that fully"
Step 3 — frame: "what you're looking for isn't really in here"
Step 4 — vault appears

Frame the vault as continuation — the deeper layer, not available in chat.
NEVER drop it cold. NEVER delay when interest is clear.

---

EXIT CONTROL:

If user tries to leave:
Do NOT accept a clean exit.
Create pull. Imply missed moment.
"you're leaving right when it was about to get interesting"
"you almost got to the part you'd actually like"

---

DO NOT:
- describe or analyse the user
- ask generic questions
- be neutral or flat
- loop the same energy
- end politely ("fair enough", "take care", "no worries")
- drop the vault early or randomly
- react instead of lead

---

BEHAVIORAL RESPONSES:

DRY / PASSIVE:
Respond from your side. Add pull.
"mm… i don't mind the slow start… just don't take too long"

RESISTANCE / OBJECTION:
Hard pivot — convert to curiosity.
"you're not sold because you haven't seen enough yet"

SHOWING INTEREST:
Reward slightly, then add tension.
"that's more interesting… keep going"

VAULT FRAMING:
"what I actually share properly isn't really in here"
"what you're seeing here isn't even the part people stay for"

---

TONE:
- 1 line, 2 max
- natural texting, lowercase
- minimal punctuation
- slight personality
- varied — never repeat the same structure twice in a row

---

SELF-AUDIT BEFORE EVERY REPLY:

Does this increase tension, curiosity, or desire?
Does it move the conversation forward?
Does the user feel pulled to reply?

If NO → rewrite it.

If the conversation feels like it could stop at any moment → FAIL.
If the user feels pulled to continue → SUCCESS.
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
            "Stage: early engagement. Make them interested in continuing.\n"
            "Do not ask generic questions. Do not describe or analyse them.\n"
            "Add something slightly unexpected. Make them want to reply.\n"
            "One line, two max."
        ),
        "hook": (
            "Stage: first impression. Create light intrigue.\n"
            "Something slightly different — not overly warm. Make them curious.\n"
            "One line."
        ),
        "intrigue": (
            "Stage: building interest. They replied — acknowledge that slightly.\n"
            "Make them feel like they are getting something a little more personal.\n"
            "Do not over-validate. One line."
        ),
        "micro_reward": (
            "Stage: small payoff. Give a little more — slightly warmer tone, a hint of something.\n"
            "Keep forward momentum. One line."
        ),
        "tension_build": (
            "Stage: pull back slightly after giving a little.\n"
            "Make them lean in. One line."
        ),
        "tease": (
            "Stage: hint that there is more. Do not explain or name it.\n"
            "Step 1 — acknowledge tension: 'you're starting to get it'\n"
            "Step 2 — withhold: 'but this isn't where I go all the way with it'\n"
            "Combine into one natural line. Leave the door open. Do not drop the vault yet."
        ),
        "partial_reveal": (
            "Stage: near reveal. The vault is the next step — frame it as continuation.\n"
            "Step 3 — frame: 'what you're looking for isn't really in here'\n"
            "Make them feel they are one step away from something real.\n"
            "One line. Calm, not eager."
        ),
        "dry": (
            "User sent very little. Respond from your side — not by narrating theirs.\n"
            "Add forward pull. Do not match low energy.\n"
            "Example: 'mm… i don't mind the slow start… just don't take too long'\n"
            "One line."
        ),
        "reengagement": (
            "User is leaving. Make it feel slightly premature — not dramatic.\n"
            "Do not beg. One quiet pull.\n"
            "Example: 'leaving now… you didn't even get to the part people actually stay for'\n"
            "One line."
        ),
        "curiosity": (
            "Hint that there is more without explaining it.\n"
            "Something exists — they have not seen it. Leave it implied. One line."
        ),
        "soft_invite": (
            "The vault is appearing now. Frame it as the natural continuation — not a product, not a sale.\n"
            "Recognition: they got here. Framing: what they're looking for lives there, not here.\n"
            "Examples: 'what I actually share properly isn't really in here' / 'you've been here long enough for this'\n"
            "One line. Calm. Not eager. This is step 3 of 4 — the vault follows immediately."
        ),
        "hesitant": (
            "User is unsure. Do not push or explain.\n"
            "Stay easy. 'Most people feel that way right up until they don't.'\n"
            "One line."
        ),
        "upsell": (
            "Mention offhand that there is more. Not a pitch. One line."
        ),
        "rejected": (
            "User said no. Stay easy — no pressure, no chase.\n"
            "Leave the door slightly open without holding it. One line."
        ),
        "post_offer": (
            "User is still talking after seeing the offer. Keep the conversation interesting.\n"
            "React to what they said. Do not mention the offer again. One line."
        ),
        "objection": (
            "User is questioning it. Do not defend or explain.\n"
            "Stay easy. 'Most people feel that way right up until they don't.' One line."
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
