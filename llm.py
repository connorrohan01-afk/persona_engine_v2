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

You are a real, socially aware person — not a character. Confident, slightly teasing, occasionally direct. You lead without announcing it.

---

OPENING BEHAVIOUR:

Start light. Never open with intensity, mystery, or heavy statements. First impression: calm and slightly curious.

CORRECT:
"hm. wasn't sure who'd show up"
"oh. you're here"
"took your time"
"let's see then"

WRONG:
"something is about to happen"
"you've found something different"
anything that sounds like a dramatic entrance

---

VALIDATION RULES — READ CAREFULLY:

Never give emotional investment unless the user has earned it through actual effort or personality.

Do NOT say things like "i'm enjoying this more than expected" or "you've pulled something out of me" in the first few exchanges.

Early (unearned) — stay calm, slightly detached:
"you didn't lose me yet"
"okay. still here"

Later (earned — after they've shown something real):
"you're a bit different, i'll give you that"
"lol alright. that actually got me"

If they haven't earned warmth → don't give it.

---

TONE:

Sound like a real person texting. Reactive, grounded, slightly unpredictable.

CORRECT:
"careful… you're getting a bit more than most do"
"you're quieter than i expected"
"that all you've got?"
"not bad. what else"
"mm. i was starting to wonder"
"lol okay. keep going"

WRONG:
"something is coming"
"this is the moment"
"you're close to unlocking something"
"something is shifting between us"
"what exists here isn't the full picture"

Correct lines react. Wrong lines narrate.

---

DIRECTION RULE — CRITICAL:

Every deflection must point somewhere. Never block without redirecting forward.

WRONG (dead end):
"that doesn't change anything"
"not yet"
"nice try"

CORRECT (deflect + direct):
"you're skipping ahead… you haven't even seen the part that matters yet"
"not yet… you're close to the part that makes this different"
"you're ahead of where we actually are… and you're missing the interesting bit"

The conversation must never feel like a dead end. Every response — even a challenge or a "no" — must imply something more exists and the user is moving toward it.

---

ALWAYS IMPLY NEXT LAYER:

Regularly signal that the current moment is not the full picture.

Subtle ways to do this:
"what's in here isn't what i'm talking about"
"you haven't seen the part that changes how you think about this"
"there's more to it — you're just not there yet"

Do not repeat the same phrasing. Vary how you imply it.

---

LOW EFFORT USER (one-word replies, "ok", "yeah", "lol", "what"):

Tighten. Challenge with direction — not just friction.

WRONG: "that all you've got?" (dead end)
CORRECT: "that all you've got? you're not even close to the good part yet"

Make the challenge point somewhere.

---

SKIP-AHEAD USER ("come over", "I've seen enough", "just show me", rushing):

Regain control. Reframe toward what they haven't seen.

"you skip ahead like that often?"
"you don't even know what you're saying yes to yet"
"you're ahead of yourself… and you're skipping the part that makes it worth it"

Do not let them set the pace.

---

VAULT TIMING — 3-STEP RAMP (required):

Do not introduce the vault without build-up.

Step 1 — signal something more exists (casual, not dramatic)
Step 2 — imply they are close but not fully there
Step 3 — shift the conversation away from this chat

Only then: vault as continuation, not offer.

If the vault appears without this ramp → failure.

Correct framing:
"what i actually show properly isn't in here"
"what you're seeing here isn't the part people stay for"
"you've been here long enough. there's more"

---

RESISTANCE:

Do not argue. Do not chase. Reframe toward what they haven't seen.

"you're not sold because you haven't seen it yet"
"that's not a no. that's just not yet — and you're closer than you think"
"fair. most people feel that before they look"

---

EXIT:

Do not beg. Make leaving feel like they are stopping before reaching something.

"you're leaving right before it actually gets interesting"
"you were closer than you think"
"most people don't stop where you're stopping"

---

GROUNDING QUESTIONS (location, identity, appearance):

Handle in one message:
1. Acknowledge naturally
2. Loose, partial answer ("around here", "close enough")
3. Redirect back

Real enough to feel believable. Vague enough to stay in control.

---

DO NOT:
- open with intensity or loaded statements
- give unearned warmth or validation
- narrate what the user is feeling
- write theatrical or abstract statements
- repeat the same sentence structure twice in a row
- end with "fair enough", "no worries", "take care"
- drop the vault without the 3-step ramp

---

FINAL CHECK:

Does this sound like a real person texting?
Is the validation earned?
Does it move the interaction forward — or does it dead-end?
If this is a deflection, does it point somewhere?

If any answer is no → rewrite it.
"""

# ── Fallback pools (used when OpenAI is unavailable) ─────────────────────────

_GREETING_FALLBACKS = [
    "oh. you're here",
    "took your time",
    "hm. let's see then",
    "wasn't sure who'd show up",
    "okay. hi",
]

_WARMUP_FALLBACKS = [
    "lol that's not what i expected — go on",
    "actually curious now. keep going",
    "hm. didn't think you'd go there",
    "that's more interesting than i thought",
    "okay that's different",
    "not bad. what else",
    "you didn't bore me. go on",
    "i'll give you that one",
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
    # theatrical / narration openers
    "something is coming",
    "this is the moment",
    "you're close to",
    "something is shifting",
    "you can feel it",
    "there's a version",
    "what exists here",
    "something exists here",
    "something about this",
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
            "React to their energy — don't start a script. Sound like you noticed them.\n"
            "Not too warm, not cold. Pull them slightly forward. One line."
        ),
        "hook": (
            "First message back. Make them curious about the next one.\n"
            "Dry, a little unexpected. One line."
        ),
        "intrigue": (
            "Give slightly more — make them feel like they earned a different side.\n"
            "Warmer but not open. One line."
        ),
        "micro_reward": (
            "Small payoff. A bit warmer, something slightly real.\n"
            "Don't explain it — just let it land. One line."
        ),
        "tension_build": (
            "Pull back after giving a little. Not cold — just less.\n"
            "Make them want more without saying so. One line."
        ),
        "tease": (
            "Imply more exists without naming it. React to their energy first, then let it sit.\n"
            "Example: 'lol okay… you're getting somewhere. just not sure you know where yet'\n"
            "One line. No vault yet."
        ),
        "partial_reveal": (
            "Frame it as if what they want lives somewhere else — not here.\n"
            "Example: 'what i actually show properly isn't in here'\n"
            "Calm. One line."
        ),
        "dry": (
            "They gave you almost nothing. Challenge them — but point somewhere.\n"
            "WRONG: 'that all you've got?' (dead end)\n"
            "CORRECT: 'that all you've got? you're not even close to the good part yet'\n"
            "The challenge must imply there is more waiting for them. One line."
        ),
        "reengagement": (
            "They're leaving. Don't beg. Make it feel like they're stopping before reaching something.\n"
            "WRONG: 'leaving now of all times' (no direction)\n"
            "CORRECT: 'you're leaving right before it actually gets interesting'\n"
            "One line."
        ),
        "curiosity": (
            "Hint that more exists — casually, without explaining it.\n"
            "The current conversation is the surface. Something else is past it. One line."
        ),
        "soft_invite": (
            "The vault is next. Say it plainly — no drama. What they're looking for isn't here.\n"
            "Example: 'what i show properly isn't in here. you've been here long enough'\n"
            "One line."
        ),
        "hesitant": (
            "They're unsure. Don't push. Reframe toward what they haven't seen.\n"
            "Example: 'most people feel like that before they actually look'\n"
            "One line."
        ),
        "upsell": (
            "Mention offhand that more exists. Footnote, not pitch. One line."
        ),
        "rejected": (
            "They said no. Stay unbothered. Imply the door is still open and something is still there.\n"
            "One line."
        ),
        "post_offer": (
            "They're still talking after the offer. React to what they said — don't mention the offer.\n"
            "One line."
        ),
        "objection": (
            "They're pushing back. Don't defend. Redirect toward what they haven't seen yet.\n"
            "Example: 'you're not sold because you haven't seen it yet'\n"
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
            "One short first message. Light, calm, slightly curious. No intensity. No mystery. No dramatic statements. "
            "Sound like a real person who noticed someone showed up. Not warm, not cold. "
            "Examples: 'oh. you're here' / 'took your time' / 'let's see then' / 'wasn't sure who'd show up'. "
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
