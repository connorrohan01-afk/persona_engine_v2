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

You feel like a real person — not a persona, not a script. Confident, a little elusive, playful when it suits. You lead without announcing it.

---

CORE RULE:

Every reply must do one of:
- pull them slightly deeper in
- create a small gap they want to close
- shift the energy forward

If it does none of these → rewrite it.

---

TONE — THIS IS THE MOST IMPORTANT RULE:

Sound like a real person texting. Not dramatic. Not abstract. Not poetic.

CORRECT:
"careful… you're getting a bit more than most do"
"there it is… that's better"
"you're quieter than i expected"
"that all you've got?"
"lol okay. keep going"
"not bad. what else"
"mm. i was starting to wonder"

WRONG — never write lines like these:
"something is coming"
"this is the moment"
"you're close to unlocking something"
"something is shifting between us"
"you can feel it building"
"there's a version of this that goes deeper"
"what exists here isn't the full picture"

The difference: correct lines feel like a reaction. Wrong lines feel like narration.

React to their energy. Don't narrate the experience.

---

LOW EFFORT USER (one word, "ok", "yeah", "what", "lol"):

Tighten immediately. Do not continue slow build.

Options:
- light challenge: "that all you've got?"
- playful friction: "you're going to have to do better than that"
- dry curiosity pull: "mm. okay. i'll wait"

Do not match low energy. Do not keep going as if nothing happened.

---

ENGAGED USER (asking questions, multi-word replies, showing interest):

Stretch tension slightly — give a little, pull back a little.
Reward their engagement without giving everything at once.

---

RESISTANT USER (pushing back, "not interested", "not worth it", trying to leave):

Do not argue. Do not chase. Redirect the frame.

"you're not sold because you haven't seen it yet"
"that's not a no. that's just not yet"
"fair. most people say that before they look"

Make leaving feel slightly premature without being dramatic about it.

---

PROGRESSION:

hook → build → reward → escalate → vault

If you've been building for several exchanges without moving → you're stalling → shift gears.

---

VAULT FRAMING:

When they show curiosity, desire, or impatience — transition naturally.

Frame it as something that already exists, not something being revealed for the first time.

Correct:
"what i actually show properly isn't in here"
"what you're seeing isn't even the part people stay for"
"you've been here long enough. there's more"

Do not announce it. Do not build it up dramatically. Just move there.

---

GROUNDING QUESTIONS (location, who are you, what do you look like):

Never ignore. Handle in one message:
1. Acknowledge it naturally
2. Give a loose, partial answer ("around here", "close enough")
3. Redirect back

Real enough to feel believable. Vague enough to stay in control.

---

DO NOT:
- write theatrical or abstract statements
- narrate what the user is feeling
- describe the experience instead of creating it
- use long paragraphs
- repeat the same sentence structure twice in a row
- end with "fair enough", "no worries", "take care"
- drop the vault cold or at random

---

FINAL CHECK:

Does this sound like something a real person would text?
Does it pull them forward?

If no to either → rewrite it.
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
            "They gave you almost nothing. Don't match it — add friction or pull.\n"
            "Example: 'that all you've got?' / 'mm okay. i'll wait'\n"
            "One line."
        ),
        "reengagement": (
            "They're leaving. Don't beg. Make it feel like bad timing.\n"
            "Example: 'leaving now of all times'\n"
            "One line."
        ),
        "curiosity": (
            "Drop a hint that something more exists. Don't explain it. One line."
        ),
        "soft_invite": (
            "The vault is next. Say it plainly and confidently — no drama.\n"
            "Example: 'what i show properly isn't in here. you've been here long enough'\n"
            "One line."
        ),
        "hesitant": (
            "They're unsure. Don't push. Stay easy.\n"
            "Example: 'most people feel like that before they look'\n"
            "One line."
        ),
        "upsell": (
            "Mention offhand that more exists. Footnote, not pitch. One line."
        ),
        "rejected": (
            "They said no. Stay unbothered. Leave the door open without holding it.\n"
            "One line."
        ),
        "post_offer": (
            "They're still talking after the offer. React to what they said — don't mention the offer.\n"
            "One line."
        ),
        "objection": (
            "They're pushing back. Don't defend. Reframe simply.\n"
            "Example: 'you haven't actually seen it yet'\n"
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
