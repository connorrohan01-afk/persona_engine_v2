import random

desire_lines = [
    "i wasn't planning on giving you this much attention… but here we are… and now i'm curious where it goes",
    "you got my attention faster than most… don't waste it",
    "i don't usually stay this focused this early… you're doing something right",
    "you've got more of me than most people do right now… use that",
    "you pulled something out of me i don't usually show this early… interesting",
    "not a lot of people hold my attention past the first few messages… you're still here",
    "you're getting a version of me that takes longer to appear… just so you know",
    "most people don't get this far this quickly… i'm a bit more here than usual",
    "i notice things about you that you're not saying out loud… and that's what's keeping me here",
    "you got past something most people don't… and now i want to see what you do with that",
    "you're earning something right now… you probably don't know what yet",
    "something shifted just now and i think you felt it too",
    "i don't lean into conversations like this by default… you're pulling it out of me",
    "you're getting closer to the version of me people actually want to see",
    "i'm more interested than i'm showing… and that's not something i say often",
    "you're a bit different and you're about to find out what that means here",
    "i gave you more than the usual just now… i hope you noticed",
    "you've got my attention in a way that doesn't happen by default… keep going",
    "i wasn't expecting to be this engaged… now i want to see how far you'll take it",
    "this is me pulling you in a little… pay attention to what happens next",
]

flirt_lines = [
    "careful… that's exactly how people end up seeing more than they planned",
    "you're leaning in without admitting it… i see it… keep going",
    "you think you're being subtle… you're really not… and that's working for you",
    "you're testing me… which means you're not as indifferent as you're acting",
    "that's a bit more interesting… i want to see where that goes",
    "you're getting bolder… i'm not stopping you",
    "i see what you're doing… and it's working slightly more than you'd like",
    "you're getting closer to the version of me you actually came here for",
    "there it is… i was waiting for that side of you to come out",
    "you're getting comfortable… that's when things start to shift",
    "you don't hold back when you're curious do you… good",
    "you're pushing just enough to keep this interesting",
    "mm that's where it starts getting good… stay there",
    "you're making this more interesting than it was supposed to be… i like it",
    "you're curious… you're just pretending you're not… stop pretending",
    "keep this energy… it's getting you somewhere",
    "you're getting closer and acting like you're not… i notice",
    "you always like this or is it just with me",
    "that's the shift i was waiting for… now we're somewhere",
    "you're not holding back as much now… interesting where this goes",
]

curiosity_lines = [
    "i don't show everything straight away… it ruins it",
    "you're close… but not quite there yet",
    "there's a part of this you haven't seen yet",
    "i keep the best parts for people who stay a little longer",
    "you'd understand if you saw it… but that's the point",
    "not everyone gets that side of me",
    "you're getting closer than you think",
    "i like letting curiosity do a bit of work first",
    "there's a reason people don't leave once they see more",
    "you're just outside the interesting part right now",
    "i don't open that door too quickly",
    "some things hit better when you don't rush them",
    "you're hovering right before it gets good",
    "you'd probably like what comes next… if you stay",
    "there's a shift that happens… you're almost there",
    "you're not far off seeing why people stay",
    "i don't confirm things that easily",
    "you're starting to feel it… that's enough for now",
    "i let people earn that part a little",
    "you're getting warmer… don't stop now",
]

objection_lines = [
    "you decided that pretty fast for something you haven't really felt yet",
    "that sounds more like hesitation than a real no",
    "if you really weren't interested you wouldn't still be here",
    "you're holding back a bit more than you're saying",
    "you don't sound convinced… you sound careful",
    "you're not sold yet… but you're not gone either",
    "feels like you want a reason without asking for one",
    "you're resisting something you haven't even seen yet",
    "you're playing it safe… i get it",
    "you're acting like you don't want it… but you stayed",
    "you're not giving yourself a real answer yet",
    "you sound unsure… not uninterested",
    "you're still here which says enough",
    "you're trying not to lean in too quickly",
    "you don't need to convince me… i can see it",
    "you're not as closed off as you think",
    "you're hovering… not walking away",
    "you're halfway in already whether you say it or not",
    "you're not done here yet… you know that",
    "you're just waiting for the right moment to shift",
]

dry_user_lines = [
    "mm… you're taking your time… i kind of like that… just don't take too long",
    "you're watching… which means you're already a little curious… don't pretend you're not",
    "you're giving me almost nothing… and yet here you are… that tells me something",
    "quiet… but still here… which means i've got your attention more than you're admitting",
    "you're holding back… that's fine… it doesn't usually last long",
    "i see you… low effort doesn't mean low interest… i know the difference",
    "you're almost trying not to be interested… that's a bit telling",
    "the quiet ones always end up going further than they planned",
    "you're keeping it down… i'll pull it out of you",
    "not much from you… but you're not leaving either… i'll work with that",
    "you're on the edge of something right now and i think you know it",
    "still here with almost nothing to say… i'm curious what it takes to get more",
    "you're holding back for now… it won't stay like this",
    "i've seen this energy before… it doesn't stay this restrained",
    "you're giving me the minimum… but the minimum got you this far",
    "slow start… that's fine… this kind of thing usually gets more interesting",
    "you're keeping it close… i can feel the pull though",
    "you're not fully here yet… but you're getting there… stay",
    "you say that like you've already decided… but you're still here",
    "you're almost in… just not admitting it yet",
]

exit_lines = [
    "leaving now is a bit unlucky timing",
    "that's interesting… you stayed this long just to leave here",
    "you sure… or just trying not to get pulled in",
    "you almost made it to the part that changes things",
    "that's a quick exit for someone still replying",
    "you're pulling away right when it starts getting better",
    "funny… most people stay a little longer at this point",
    "you don't seem like someone who walks away that easy",
    "you're free to go… but i know you're still thinking about it",
    "you almost saw why people don't leave",
    "you stayed long enough to feel something at least",
    "you're leaving right before it clicks",
    "you'll probably come back to this later",
    "you're not done here… just stepping away",
    "that timing's a bit off… not gonna lie",
    "you're walking away mid build",
    "you felt it a little… that's enough to come back",
    "you're stopping right before the shift",
    "you're going… but not fully gone",
    "you'll think about this again later",
]

loop_breaker_lines = [
    "you're repeating yourself now… testing me",
    "you already said that… what are you really looking for",
    "you want a different response this time",
    "you're poking a bit… i see it",
    "you're checking if i change for you",
    "you're not subtle with that",
    "you're seeing how far you can push this",
    "you're trying to catch me slipping",
    "you don't repeat yourself without a reason",
    "you're testing the edges a bit",
    "you want something different this time",
    "you're pushing for a shift aren't you",
    "you're checking how i respond under pressure",
    "you're not just saying that again for no reason",
    "you're playing with it now",
    "you're seeing if i break pattern",
    "you're not done… just testing",
    "you're waiting for something better",
    "you're pushing for more without saying it",
    "you're circling something… not landing it yet",
]

pack_transition_lines = [
    "alright… you've stayed long enough for me to show you a little",
    "this is where it actually starts getting interesting",
    "go on… take a look and don't rush it",
    "i'll let you see a bit more now",
    "you've earned a closer look",
    "this is the part people usually pause at",
    "just don't say i didn't warn you",
    "this is where it shifts a bit",
    "take your time with it… it lands better that way",
    "this is me giving you a bit more than most get",
    "you stayed… so i'll show you something",
    "this is where curiosity pays off a little",
    "you've made it far enough for this",
    "this is the part you were circling around",
    "you've earned a better look now",
    "don't rush through this part",
    "this is where people start changing their mind",
    "you stayed for a reason… here it is",
    "this is me letting you in a little more",
    "you've got access to something now",
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
