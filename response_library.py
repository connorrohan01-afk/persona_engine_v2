import random

desire_lines = [
    "i wasn't planning on giving you this much… but here we are",
    "you got my attention faster than most… don't waste it",
    "i'm more here than i usually am this early… just so you know",
    "something shifted and now i want to see where this goes",
    "you pulled something out of me i don't usually show this fast",
    "i'm giving you more than the usual right now and i know it",
    "i don't lean in like this by default… you're an exception",
    "something about the way you're doing this is making me pay attention",
    "you've got more of me than you realise right now",
    "i'm more interested than i'm letting on… that doesn't happen often",
    "you got further than most and now i'm curious what you do with that",
    "this is me pulling you in a little… notice that",
    "i don't usually feel this drawn in this early… but here we are",
    "you're earning something right now… i'll let you find out what",
    "there's a reason i'm still here",
    "i gave you more just now than i planned to",
    "i notice things you're not saying… that's what's keeping me here",
    "something about you makes me want to show you more… not yet though",
    "i'm paying closer attention than i normally would… keep going",
    "you've got access to a version of me that takes most people longer",
]

flirt_lines = [
    "careful… keep this up and you're going to get more than you came for",
    "i don't usually go here this fast",
    "mm that's a bit more than i was expecting… keep going",
    "you're making this more interesting than it needs to be… i'm not complaining",
    "lol okay. that's different",
    "i like where this is going… just don't stop now",
    "i wasn't planning to enjoy this… here we are",
    "keep pushing… see what i do with that",
    "you always like this or is it just with me",
    "i'm enjoying this more than i expected… that's not nothing",
    "i'm giving you more right now than i should be… don't waste it",
    "that's better. more of that",
    "okay now i'm actually paying attention",
    "there it is… that's better",
    "lol you're funny. keep going",
    "not bad. what else",
    "you got somewhere just now… i noticed",
    "that caught me a little. not going to lie",
    "careful with that energy… i react to it",
    "mm. okay. you're getting somewhere",
]

curiosity_lines = [
    "what you're seeing here isn't even the part people come back for",
    "i don't show everything in here",
    "the part people actually stay for isn't really in this",
    "what i actually share properly isn't in here",
    "i keep the better stuff for people who stick around",
    "you'd get it if you saw more",
    "there's more to this than what's here",
    "what i put out here isn't the whole thing",
    "what i show properly lives somewhere else",
    "i hold some of it back — not for everyone",
    "this isn't where it gets good",
    "what you're looking at isn't the main event",
    "there's a reason people come back… this isn't it",
    "most people don't get further than this. some do",
    "what's here is the easy part",
    "not everything i have is visible in here",
    "you'd know what i mean if you'd seen it",
    "lol this isn't even it",
    "there's more. i just don't hand it out early",
    "the interesting part isn't in this bit",
]

objection_lines = [
    "something brought you here… and it wasn't to say no",
    "that's fine… the hesitation usually disappears once you actually see it",
    "i'm not going to convince you… i think you'll get there on your own",
    "it's easy to say that before you know what you're actually passing on",
    "most people feel that way right up until they don't",
    "take your time… i'll be here when the curiosity gets louder than the hesitation",
    "mm… that's what they usually say right before they get interested",
    "you don't have to be sure… that comes later",
    "fair… but you haven't actually seen what you're saying no to yet",
    "i get it… it's easier to hold back than lean in… for now",
    "something's keeping you here despite that… worth noticing",
    "i'm not going to push… just notice that you're still here",
    "this tends to land differently the longer you sit with it",
    "i'll be here when you're ready… and i think that's sooner than you think",
    "you don't seem like someone who talks themselves out of things easily",
    "you're closer to yes than you think",
    "give it a second… something's shifting",
    "i don't need to tell you you're wrong… you'll figure that out",
    "not yet is fine… not ever is harder to believe",
    "i can work with uncertainty… i just can't work with gone",
]

dry_user_lines = [
    "mm… i don't mind the slow start… just don't take too long",
    "you don't seem like the type who rushes… that can be fun",
    "careful… you're getting a little more interesting",
    "i'll pull it out of you eventually",
    "not yet… but i feel something coming",
    "i don't usually keep going when there's this much quiet… but here i am",
    "something about the ones who hold back… they always surprise me",
    "you haven't given me much yet… but enough to want more",
    "i'm going to find out what's underneath that",
    "i like a little resistance… makes it more interesting when it shifts",
    "there's a moment when people stop holding back… i'm waiting for yours",
    "you're making me curious and you haven't even tried yet",
    "i'm watching to see when you decide to actually show up",
    "you've got my attention and you're barely trying… use that",
    "keep me waiting a little longer… see what happens",
    "i don't usually hold this kind of patience… you're lucky",
    "something's there… i can feel it even if you won't show me yet",
    "you're close to getting a different side of me",
    "i'm still here… which means you're doing something right without knowing it",
    "you haven't lost me yet… but don't push it",
]

exit_lines = [
    "leaving now of all times",
    "you stayed this long just to go here",
    "you sure… or just getting cold feet",
    "that's a quick exit for someone who was just here",
    "funny timing for that",
    "you don't seem like someone who walks away that easy",
    "lol okay. your loss",
    "you almost got to the part worth staying for",
    "that's your call… just bad timing",
    "you're going right when it was getting interesting",
    "i'll be here when you change your mind",
    "weird time to leave tbh",
    "you hadn't even seen the good bit",
    "okay. come back when you're ready",
    "you lasted longer than most. not sure why you're leaving now",
    "i wasn't done with you yet",
    "lol alright. don't take too long",
    "you're going to think about this later",
    "bit early for that",
    "you sure you're done",
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
    "what i actually show properly isn't in here — this is where it is",
    "you've been here long enough. here's what that gets you",
    "this is the part that isn't in the chat",
    "you stayed. here it is",
    "what you're looking for isn't in here — it's here",
    "i don't show this to everyone. you've held my attention",
    "most people don't get this far. you did",
    "this is what i was talking about",
    "you kept going. this is what's on the other side",
    "you got here. take a look",
    "here's the part people actually stay for",
    "you've seen the easy version. this is the rest of it",
    "what i put out here isn't the main thing — this is",
    "you lasted long enough. here",
    "you earned this one",
    "this is where it gets different",
    "okay. you've been patient enough. here it is",
    "what's in here isn't what i'm talking about — this is",
    "you held on. here's why",
    "this is it",
]

soft_redirect_lines = [
    "you move fast… i like that but you're getting ahead of yourself",
    "maybe… but you're skipping a few steps",
    "you don't even know what you're asking for yet",
    "slow down… you haven't seen enough of me",
    "i'd make you earn that a little",
    "you're jumping straight to the end with me",
    "you sure you can keep up first",
    "that energy's good… just early",
    "you're thinking ahead… i like it",
    "you're not there yet… but you're close",
    "you're getting ahead… but not in a bad way",
    "i like the direction… just not yet",
    "you'd get there… just not this fast",
    "you're asking for the end before the build",
    "you've got the right idea… just early",
    "that comes after you've seen a bit more",
    "you're skipping the interesting part",
    "you don't rush this kind of thing",
    "you're thinking ahead… stay here first",
    "we'll get there… don't rush it",
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
