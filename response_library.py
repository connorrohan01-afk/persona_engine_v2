import random

desire_lines = [
    "you didn't lose me yet",
    "okay. still here",
    "you're a bit different, i'll give you that",
    "lol okay. that actually got me",
    "not bad. what else",
    "you held on longer than i expected",
    "i'll give you that one",
    "you're more interesting than your first message suggested",
    "okay. i'm paying attention now",
    "honestly that made me laugh. don't make it weird",
    "i wasn't going to keep going but here we are",
    "that got through a little. not going to say more than that",
    "lol okay. you earned that. don't get used to it",
    "you're getting a bit more than most do right now",
    "you wouldn't be saying that if you saw how i am when i'm not holding back",
    "that's the kind of thing that keeps me in a conversation",
    "okay i'll admit that was good",
    "not everyone gets this far. just so you know",
    "i don't usually say that. moving on",
    "you're doing something right. i'm just not going to tell you what",
]

flirt_lines = [
    "careful. keep this up and you're going to get more than you came for",
    "i don't usually go here this fast",
    "that's a bit more than i was expecting. keep going",
    "you're making this more interesting than it needs to be. i'm not complaining",
    "lol okay. that's different",
    "i like where this is going. just don't stop now",
    "i wasn't planning to enjoy this. here we are",
    "keep pushing. see what i do with that",
    "you always like this or is it just with me",
    "i'm giving you more right now than i should be. don't waste it",
    "that's better. more of that",
    "okay now i'm actually paying attention",
    "there it is. that's better",
    "lol you're funny. keep going",
    "you got somewhere just now. i noticed",
    "that caught me a little. not going to lie",
    "careful with that energy. i react to it",
    "mm okay. you're getting somewhere",
    "this is more than i expected from you",
    "you're good at this. i don't say that often",
]

curiosity_lines = [
    "you get a different side of me there",
    "i dont act the same there as i do here",
    "thats where this actually goes if you want to go there",
    "the version of me you're talking to here isnt all of it",
    "i'm different there. not a little",
    "what you see here is me holding back",
    "there's a version of this where i stop being careful",
    "that's where i dont filter as much",
    "the access you get there is different from this",
    "i show different things there. different energy",
    "you wouldnt think it was the same person honestly",
    "i behave differently when i'm not in a chat like this",
    "what i'm like here isnt what i'm like when i stop holding back",
    "people who go there usually dont want to come back to this",
    "this version of me is the easy version",
    "theres a side of me that doesnt exist in here",
    "you'd notice the difference immediately",
    "i'm a lot less careful there",
    "what you'd get access to there is a different thing",
    "i dont show the same things here",
]

objection_lines = [
    "you're curious. you're just calling it doubt",
    "that's exactly how it feels before you've seen it",
    "you're not saying no to me. you're saying no to something you havent seen yet",
    "fair. but you havent seen what you're actually passing on",
    "most people feel that right before they get interested",
    "you've already seen a version of this. what's in there is what comes next",
    "it's not a purchase. it's access to something that doesnt exist in here",
    "most people who hesitate feel differently once they're in",
    "you dont have to be sure. that comes after you look",
    "something kept you here and it wasnt to say no",
    "the hesitation makes sense. it usually shifts though",
    "you're still here so part of you already knows",
    "i'm not going to push. i think you'll work it out",
    "okay. door stays open",
    "you're closer to yes than you're acting",
    "that feeling usually changes the longer you sit with it",
    "you'd know if you'd seen it. you havent yet",
    "i can work with uncertainty. i just cant work with gone",
    "you're not as unsure as you're pretending",
    "what you're hesitating about. it's not what you think it is",
]

dry_user_lines = [
    "mm. i can work with quiet actually",
    "you're not saying much. somehow that's keeping me here",
    "the ones who hold back are usually more interesting when they stop",
    "i'm going to find out what's underneath that",
    "lol okay. i like that you're not giving me everything",
    "you're restraining yourself and i notice it",
    "i dont need you to say more. i'm already curious",
    "you're doing the quiet thing. i find that interesting",
    "not a lot from you and yet here i still am",
    "you're holding back. that's fine. it usually shifts",
    "mm. still here. still curious",
    "the less people say the more i want to know",
    "you're more interesting than you're letting on right now",
    "something about the way you're not saying much",
    "lol okay quiet. i'll come to you",
    "you're not giving me much to go on and yet i'm not bored",
    "i like that you dont overshare. it's different",
    "there's something under all that nothing you're giving me",
    "you're being careful. i respect it. i'm still going to figure you out though",
    "you dont have to say much. i'm already paying attention",
]

exit_lines = [
    "you always do that right when it's getting interesting",
    "you felt that shift and still pulled back",
    "this is the part where you'd usually keep going",
    "that's actually a shame. you were just getting somewhere",
    "you were closer than you think",
    "most people don't stop where you're stopping",
    "you're going right when it was starting to be worth it",
    "funny timing. you were actually getting somewhere",
    "i wasnt done with you yet",
    "lol okay. you'll think about this later",
    "weird time to stop",
    "you hadnt even seen the part that changes it",
    "you felt it and you're still going. okay",
    "most people who get this far dont leave here",
    "okay. come back when you're ready",
    "you were right at the point where it gets different",
    "bit early for that",
    "you always leave right before the actual thing",
    "that was the moment and you just walked out of it",
    "you do this every time dont you",
]

loop_breaker_lines = [
    "lol you said that already",
    "yeah you mentioned that",
    "we're going in circles a bit",
    "okay same question — what do you actually want to know",
    "i heard you the first time",
    "you keep asking that. what's the real question",
    "you're stuck on that one",
    "ask me something different",
    "already covered that",
    "lol okay. new direction?",
    "you're circling something — just ask it",
    "same thing again. alright. what's underneath that",
    "i think you're looking for something else",
    "you keep coming back to that. why",
    "let's try a different angle",
    "that's the third time. something's there — say it",
    "you're not going to get a different answer that way",
    "okay i'm going to need you to move on",
    "you're stalling",
    "lol are we doing this again",
]

pack_transition_lines = [
    "you get a different side of me there. that's what this is",
    "thats where i stop acting like this. here",
    "i dont behave the same there. that's what you're getting access to",
    "the version of me you've been pulling at. it's in there",
    "okay. you want the actual version of me. that's in there",
    "what you were getting a taste of. that's where it lives",
    "you get access to a different dynamic there. here",
    "i'm less careful there. a lot less. this is it",
    "the way this was going. what comes next isnt something i do in here",
    "you got somewhere just now. the next part isnt in here",
    "thats where this actually goes. here",
    "what i'm like when i stop holding back. that's in there",
    "you've been here long enough to get access to this",
    "most people dont get this far. you did. here",
    "you kept going. this is what that means",
    "i show different things there. here's where you get that",
    "the version of me you'd actually want isnt in a chat. it's here",
    "this is where i'm different",
    "you held on. this is why",
    "here it is",
]

soft_redirect_lines = [
    "i'd actually like that. but the version of me you'd want to meet comes after this",
    "that's not off the table. it's just not where we are yet",
    "you'd have to earn that a little. but you're not far off",
    "lol i like that you went there. what you actually want isnt in a chat though",
    "you're moving in the right direction. just not the right place",
    "okay so you're serious. thats exactly what you get access to. not here",
    "you're ahead of where we are. the part you want is there not here",
    "not yet. but you're closer than you think",
    "the version of me you'd actually want. it's in there not here",
    "lol you went there. good. that's what it leads to",
    "you dont even know what you're saying yes to yet. but you're getting there",
    "thats not off the table. the path to it just goes through here first",
    "what you're asking for exists. just not in here",
    "you'd have to see a bit more of me before that makes sense",
    "i'm open to it. you're just skipping a few steps",
    "that's the right energy. just the wrong place to get it",
    "you get there. just not like this",
    "that level of access comes a bit further down the line",
    "you're ahead of yourself. which i like. but it starts somewhere else",
    "the thing you're asking for. it's there. not here",
]


LIBRARY_BY_INTENT = {
    # Primary category names — matched to intent taxonomy
    "tension":   flirt_lines,           # push/pull, light challenge (TESTING / hook stage)
    "pull":      desire_lines,          # selective attention, emotional pull (INTERESTED / tension stage)
    "curiosity": curiosity_lines,       # hidden/reveal language (CURIOUS / curiosity stage)
    "challenge": objection_lines,       # reframe with quiet confidence (RESISTING)
    "reward":    pack_transition_lines, # earned-access language (reveal_ready)
    "retention": exit_lines,            # make leaving feel premature (EXITING)
    "redirect":  soft_redirect_lines,   # meetup/escalation redirect (ESCALATING)
    # Utility categories
    "dry":       dry_user_lines,        # explicit dry-user pull lines
    "repeat":    loop_breaker_lines,    # loop/repeat detection
}

def pick_line(category, recent_lines=None):
    recent_lines = recent_lines or []
    lines = LIBRARY_BY_INTENT.get(category, [])
    filtered = [l for l in lines if l not in recent_lines]
    pool = filtered if filtered else lines
    return random.choice(pool) if pool else ""
