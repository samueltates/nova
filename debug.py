from random import choice, randrange

debug = {}
credentials = '{"token": "ya29.a0AWY7CkmXEArxPmjv6q0m23LMk_Yd6nXCiMK-wENAptDOnqkhaEiDsNFkL86pkevveYkKro6JbVsepcZL9Q5eZZAmwRnW_DV4SRHfaIS78d_tuGI3dVOkWeLULc9iw2Pv-VX1PDOCIs6hc9JdZ-auLmYpmIOlaCgYKAdUSARASFQG1tDrpkm5Jnrbl6inXcKPa574J5w0163", "refresh_token": "1//0gWDDLaYLHIbgCgYIARAAGBASNwF-L9IrNdKteGm4yI9wPqjTOl6n7A_dR6By6Kp5l4u-lQGTqnlfvW6YYtFd66xM6Xg7RnbQVjI", "token_uri": "https://oauth2.googleapis.com/token", "client_id": "901964319596-tieetv1opo684l71dcdjnraemhi5u6mh.apps.googleusercontent.com", "client_secret": "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", "scopes": ["https://www.googleapis.com/auth/userinfo.profile"], "expiry": "2023-06-01T15:44:09.229445Z"}'

##could we make an ezprint class (or debug object session fenced so calling that and it runs in that session) 

def eZprint(string):
    print('\n_____________')
    print(string )
    print('_____________\n')

def fakeResponse():
    return choice(["To be, or not to be, that is the question", "Love looks not with the eyes, but with the mind; and therefore is winged Cupid painted blind.", "Get thee to a nunnery. ",  "To be, or not to be: that is the question.",
    "All the world's a stage, And all the men and women merely players.",
    "The course of true love never did run smooth.",
    "We know what we are, but know not what we may be.",
    "A man can die but once.",
    "Nothing will come of nothing.",
    "Love all, trust a few, do wrong to none.",
    "Cowards die many times before their deaths; the valiant never taste of death but once.",
    "Better three hours too soon than a minute too late.",
    "The fault, dear Brutus, is not in our stars, but in ourselves, that we are underlings.",
    "All's well that ends well.",
    "Good night, good night! Parting is such sweet sorrow, That I shall say good night till it be morrow.",
    "Uneasy lies the head that wears a crown.",
    "Our doubts are traitors and make us lose the good we oft might win by fearing to attempt.",
    "What's in a name? A rose by any other name would smell as sweet.",
    "The eyes are the window to your soul.",
    "We are such stuff as dreams are made on, and our little life is rounded with a sleep.",
    "If music be the food of love, play on.",
    "There is nothing either good or bad, but thinking makes it so.",
    "Brevity is the soul of wit."])


async def get_fake_messages():
    eZprint('getting fake messages')
    messages = []
    convoID = 0
    messageID = 0
    for convo in fake_convos:
        # eZprint('fake convo '+ str(convoID) )
        fake_messages = convo.split('\n')

        for message in fake_messages:
            # eZprint('fake message ' + str(messageID) )

            if (convoID % 2) == 0:
                name = 'agent'
            else:
                name = 'human'

            messageObj = {
                'convoID' : convoID,
                'messageID' : messageID,
                'name' : name,
                'body' : message
            }
            
            messages.append(messageObj)
            messageID += 1
        convoID +=1

    return messages
    

def get_random_words(source, num):  
    words = source.split(' ')
    max = len(words)-1
    random_words = ''
    i = 0
    while i < num:
        random_words += ' ' + words[randrange(0, max)]
        i +=1
    return random_words

def get_random_array(source, num):  
    words = source.split(' ')
    max = len(words)-1
    random_array = []
    i = 0
    while i < num:
        random_array.append(words[randrange(0, max)])
        i +=1
    return random_array



def get_random_sentences(source, sentence_length, num): 
    words = source.split(' ')
    max = (len(words) - 1) - sentence_length
    random_sentences = ''
    i = 0
    while i < num:
        x = 0
        sample = randrange(1, max)
        while x < sentence_length:
            random_sentences += " " + words[sample+x]
            x+=1
        i += 1
    return str(random_sentences)

async def get_fake_summaries(batch):
    batch = str(batch['toSummarise'])
    fake_summary = {
        "title": get_random_words(batch,randrange(2,4) ),
        "timeRange": {"start": "...", "end": "..."},
        "body": get_random_sentences(batch, randrange(10,20), 3),
        "keywords": get_random_array(batch, randrange(2,4)),
        "notes": {
            get_random_words(batch, randrange(3,5)): get_random_sentences(batch, randrange(10,20), 2),
            get_random_words(batch, randrange(3,5)): get_random_sentences(batch, randrange(10,20), 2)
        }
    }
    return fake_summary



fake_convos = ["""
        A. Well, I used to, I lived right on Queen Street so I only had to run over to the school. I was only about four or five houses removed from the school so we didn’t have far to go and a typical day, let’s see, well I’d go and be there for nine o’ clock and we’d have classes and Miss. O’Brien, she was Mrs. Ida Dylan later,
        she taught us in grade two and there was Mrs. Moses, she taught us in grade one and Bessie Turnbull taught us in grade three and grade four, we’d thought we’d get rid of her in grade three but oh geeze, she followed us in grade four, god and she taught us all this, you know, arithmetic and stuff you had to learn by route, the timetables and things like that and spelling. We’d have spelling “B’s”, oh god, I hated them on Friday’s and I couldn’t spell worth a damn anyway, so that was pretty well my day in my lower classes and that was in the old school if you remember seeing it on Queen Street, it’s right by the Anglican Church, that’s the one we’re talking about and then, I don’t know what year it was, that was in nineteen what?, thirty-two or thirty-three I think it was, no about nineteen thirty-two I guess I went to school, well a little later on they built a piece on the back and they, I think they had grades five and six and upstairs was nine and ten so we went through, the old part of the school, we went from seven to eight in the front of it and then in the back end of it, we were in high school then so we changed classes, we didn’t sit in the class all day which was quite a privilege but we didn’t have anymore recess or anything like that and then down in the basement they had woodworking and manual training and it was good fun too. You’d get down there and you didn’t do much in classes, anyway, anyway that was about it, I guess.
        Q. Describe to me what the school would look like?
        A. Oh, the school. Well, it had great big windows, huge windows and I always remember, we’d go in, in September and the, you know, and they’d have, all the floors were oiled at the time so you could smell fresh oil and I don’t know what it was, pine tar or something mixed in it and that was to keep down the dust I suppose and then we had our wooden seats and then we got in the new school, of course, they had the ones that moved back and forth, you sit in them there at your own desk but before that we were always two of us in a seat together and then in, well no, I guess in about grade eight or something we got our single seats or something ‘cause I remember, well maybe in the, it doesn’t matter anyway ‘cause it was still two of us and then in high school of course, we had our single seats and the new classrooms and everything. It had nothing to do with school though, school was a boar.
        Q. How would you have been disciplined at school?
        A. Well, we had, teachers knew how to use the strap and we had one teacher, she used to grab you by the arm with her fingers, like between here and the two fingers and twist it and pinch you and, or by the ear, one or the other, you’d have black and blue marks. (Laughter)
        Q. Wow. What would a student have to do in order to.....?

        A. Be disciplined?
        Q. Yes.
        A. Oh, I don’t know. They had to talk, chew gum, you couldn’t chew gum, you couldn’t do anything like that, you couldn’t talk out of turn and usually somebody was always teasing you about something so they’d give you a whrap on the side of the head with a ruler or something and you’d answer them back and you’d get in trouble right away, of course immediately, things like that.
        Q. How many teachers would there have been per class?
        A. Oh, just one in the lower grades. I remember Miss. Moses taught, they used to have little grade one and big grade one so she taught the both grades and then in grade two Mrs. O’Brien was, she just had, I was lookin’ at a picture not too long ago, I think it was in grade two, there were fifty- three of us for grade two, I’ve got the pictures here somewhere.
        Q. Wow. It must have been hard for her to teach all those children.
        A. Yeah, well I suppose. I don’t know but it was sort of a battle of attrition, like by the time you got to grade eleven, there was only about seven or eight students left. They didn’t have grade twelve until, I don’t know, grade twelve, it would be about, oh I guess it was just before the War they started grade and we always had just grade eleven before that as high as you went.
        Q. Why was it that there were so few students left in the high grades?
        A. I have no idea. The kids just tired of going to school, (Laughter) I guess, I don’t know, but that’s what it was all through the years. Well, when I went to school, of course, the War came along and a lot of kids from grade eight on joined the army or whatever it was because they would be fifteen, sixteen years old, seventeen, you know, and, so that was a lot of the attrition then but by the time you got to grade twelve I suppose there’d be only seven or eight in grade twelve at the most, then, they didn’t, kids didn’t want to go past grade eleven, there was no need of it, really, past grade ten really in those days. You didn’t need an education to join the army, yeah.
        Q. Describe to me what your mother’s workday would be like?
        A. My mother’s workday? Oh gosh, I don’t know. Let’s see, I’d get up and build a fire in the morning in the kitchen and, so she’d cook breakfast for

        us and we always had porridge so she’d do that and then I suppose she’d just dust around the
        house, I never took much notice to that (Laughter). I’m a boy, I don’t have anything to do with the housework, that’s woman’s work, god, geeze.
        Q. What did your father do for a living?
        A. He was a dentist so he took off and he’d be gone, he used to come home around, between six and seven at night and his office was downtown and we, as I said, we lived on Queen street so he didn’t, he used to walk to work and walk home. We never had a car in those days, it wasn’t ‘till we moved out in the country they got a car.
        Q. Would he do the dentist work on you guys when you were younger?
        A. Oh sure, oh my yes. I remember the first time I ever saw it, he had, they didn’t have any electricity really and they used to run the treadle, it was for grinding your teeth and he used to have a foot treadle and they used to, they would drill with that and then years later, of course, they got, they got the machines and the electricity and he had an electric machine that did it. It wasn’t very high speed, it’s speed was all, you could hear it grinding away, it’s not like today, it doesn’t go geeeeeeeeeeeeeee (Sfx) and he always had, if you see the cords going around making the drill go, he always put a little cotton baton on it see, and he’d get the kids to watch the rabbit run around the thing, fascinating. They never used to, the never, they didn’t freeze your teeth in those days, my father, so you just sat there and took it.
        Q. He must have been one of the few dentists probably around here at that time was he?
        A. Well, all in all there was two of them. There was always two, before he bought his practice from Dr. McGreggor who lived in Bear River and after him there was, when he went in the army Dr. Rogers came here for a while and he went into the army and then Dr. Outhouse, Burley Outhouse, he was here after the War and then my father came back and there was always two, two or three dentists around.
        Q. What would your daily chores consist of?
        A. Well, I always had to fill the wood box for one thing and keep the woodshed clean and I always chopped the kindling and things like that and stoke the furnace and, we always used wood in the furnace so I always had to keep that going. In the fall I had to put the wood in and I used to, I always remember we had seven quarts of wood in the cellar and

        three quarts of wood in the wood shed for the winter and I used to have to put that in and pile it up as part of my chores. In the summer we’d mow the lawn and things like that. I didn’t spend many summers
        here, I used to go to a boy’s camp in the summer, mostly from the time I was about eleven, I think, I went away every summer.
        Q. Where was that camp?
        A. It was down in Weymouth at the time and it was run by a Mr. Blakum from the states and it was mostly boys from the states that were there and we always had a good time.
        Q. What sorts of things would you do there?
        A. Well, it was like, it was a boys camp so you did, it was run on athletics and just living together and there was swimming pools and we played games all day and we had rest periods and that sort of thing and we used to, in the evenings, they had a huge fireplace in the main building and particularly in August when the days got shorter and the weather got a little cool, they’d always have a big fire going and the senior councilor, everybody would sit around and they took boys from ten to eleven years old right up to eighteen, nineteen, and the senior councilor would, everybody would gather around and the senior councilor would read some story about Jack Armstrong or something like this, always a chapter every night so everybody would settle down and listen to this.
        Q. How would the people, the boy’s get up from the states?
        A. Well, they used to come here on the, they would come by trains, or in the years before they'd come by a boat from Boston to Yarmouth and then they’d take from Yarmouth, drive up and the people would go out and get them or they’d come over to Saint John and come across on the boat and go down and during the summer they’d go back in the woods and Ned Sullivan’s camps were back in Sprague Lake, they had a camp there for, they’d stay there and you’d learn canoeing and this sort of thing, it was a nice, great place to be in the summer.
        Q. Did you find the boys from the states to be any different from you?
        A. Oh yeah, yeah, they were quite a bit different. It was interesting to be with them. They always had better clothes than we did, no matter how well dressed we were they’d have something better. I always remember their running shoes were great, oh man, they had beautiful shoes and we’d have these old damn sneakers, you know, (Laughter) this sort of thing, oh my.
    """,

    """
        After you were finished your chores at home, what would you like to do with your spare time?
        A. Listen to the radio and read, we used to read a lot in those days because we didn’t have a t.v, we had radio.
        Q. It must have been one of the old battery radios?
        A. No, oh no, no, we were plugged in. (Laughter) The, oh no, it was electricity, we had electricity, geeze. I can remember though when I was just very small and my grandmother always had electricity and it was only twenty-five watt bulbs, very dim, so they used to use lanterns a lot and then my great grandmother, I used to clean her lanterns, she lived down on First Avenue and she was ninety-two, or three, or four, or something like that when she died, so I remember doing the work for her. When I’d go down to her place I used to take her, her lunch down in the summer times for her and I’d pack a lunch and I’d carry it down on a basket and she had an organ in her house and I’d play the organ for her and she’d sit there and rock (Laughter) and I couldn’t play the organ worth beans but she’d thump on it but I found out years later that she’d been brought up in the old style where the man of the house was supreme, you know, he could do anything he wanted and they sort of always showed appreciation for it, so I suppose she was board to tears listening to me (Laughter) and she was a great old soul, she was.
        Q. What would you say your favorite holiday was as a child?
        A. Favorite holiday as a child? Oh, Christmas, oh my yeah. I remember, I was just thinking about it the other day, we’d get the, there used to be in the funny papers, there was always a Christmas one they had run everyday up until, well I don’t know how long before Christmas, but it was a Christmas story of some sort, some kids that would get in trouble and get out of trouble and we’d always look forward to this and as soon as we got the paper we’d push it down on the floor, looking at this and trying to read this and get somebody to read it to us ‘cause you’d get the pictures but you couldn’t get all the whole story, of yeah, yeah.
        Q. What was it like at your house when the catalogue would arrive?
        A. Oh, I don’t remember much about the catalogue. We didn’t have much to do with catalogues. We used to go, I remember we used to go once or twice a year into Halifax shopping, my mother would take us in and we’d stay at the Lord Nelson, usually the Lord Nelson and she’d go shopping for the year for us for clothes and this sort of thing and I remember one year she bought me one of these hats, caps you wore, you know, it looked like hell on me, so we were coming back on the train and I deliberately
        stuck my head out like this to see where the train was and it took my cap away, so I didn’t have to wear that god damn thing anymore, oh I hated that thing with a passion.
        Q. Do you remember that train ride well?
        A. Oh, I remember that. I certainly remember that. (Laughter) Q. Tell me about it?
        A. What?
        Q. What the train was like?
        A. We used to leave here in night time and have, take the sleeping car to Halifax and that was great fun ‘cause you’d, I’d like to get, I’d get all this room where I always had upper berth, you know, you’d climb up in there and, gee, the nice clean sheets and the people were waiting on you and this sort (Laughter) of thing and then we’d come back and usually we came back in the day time and we always sat in the parlor car which had big swivel chairs in it and gosh, you’d sit in there and fell just like a king, oh, it was good fun.
        Q. How much spending money would you have had as a child?
        A. Well, I, god, I used to get a penny once and a while and I remember I got my allowance one day and, I was just a little fella and I got a penny to go to Mrs. Clinton’s place, a candy store and there was two ladies, spinster ladies, the Mrs. Clinton’s and my father gave me a penny and I dropped it on the sidewalk and Judge Woolaver, he was there and he made a grab for it and the two of us got in a fight over this penny and he was bigger than me at the time but I got my penny back. (Laughter)
        Q. Where else would you get the things that you needed if you wouldn’t get them out of the catalogue?
        A. Oh god, I don’t know, I don’t know, I never had much to do with that when I was a kid. I don’t remember, you know, ever having to think about things like that.
        Q. Do you remember what stores would have been here in Digby?
        A. Oh gosh, yeah. There’s all kinds of them. Well, Mike Parker just wrote a history on it. Did you see that?
        Q. I didn’t.

        A. You haven’t seen it yet. Yeah, it’s a good little book on, pretty well all of the stores were in it of the time except you didn’t have B.J Roope’s store which was a
        clothing store years ago and we were talking about other places the other day, restaurants and things that were around but I don’t, I had nothing to do with buying anything, it was just, my parents looked after that. I didn’t worry about clothes, god almighty.
        Q. What was your religion?
        A. Anglican, Church of England.
        Q. So, what would Sunday’s be like at your house when you were growing up?
        A. Oh, I used to, yeah, we’d go to church in the morning and Sunday school and in earlier years we used to go to church in the evening too and then when I was growing up in my teens I went in the mornings, probably once a month for communion but most of the time I used to like to go to evening services, the rest of the time, daytime, I’d go for walks on Sunday’s ‘cause we weren’t allowed to do anything else, there wasn’t anything else to do, (Laughter) geeze.
    """,
    """
        What things would you have to grow and raise yourself, would your parents have had to grow and raise themselves?
        A. We didn’t raise anything. We lived in town and there was nothing to, no, well father had a little garden, I can remember helping him with that but there wasn’t very much in it.
        Q. What sort of things would people have bartered for? A. Bartered?
        Q. Yes.
        A. Oh god. Well, I, they did a lot of bartering with my father because I used to have to go and bring home the groceries and things that people would trade for doing the, he’d work on their teeth and, like if he was a fishermen he’d trade and give him so many fish for doing a tooth or doing his teeth. There wasn’t very much around, there wasn’t very much money in those days and I know I’ve read, I’ve kept some of fathers stuff that people would write and say, “I’m sending my granddaughter up to work, you know, that you can do some work on, she needs fillings and this sort of thing and I know I haven’t paid you myself or my son hasn’t paid you
        but none of us are working but we will when we get around to it”, and I was talking to a chap the other day and it took him twenty years to pay off my father and my father was retired after the last payment but they did, they’d do their very best, the people around. Most of them didn’t have any money,
        fishermen, farmers, nobody had any money years ago. It’s not like today, everybody’s got money today, even no matter how poor you are, you got money today, but they didn’t have any, anyway, you know, he’d get paid with, I don’t know, some fish or something and I’d have to take the cart down or the sled down in the winter time and lug it home (Laughter) and that sort of thing and, yep, apparently it didn’t cost very much to live, I don’t know. It didn’t seem like to me, as I said, I was just a kid, I didn’t know what the hell was going on most of the time, (Laughter) I wasn’t interested.
        Q. How much of what you needed, or what your parents needed would they have made themselves?
        A. God, I don’t think they made, well, I don’t, I really don’t think they made anything themselves until the later years. My mother used to make things but she didn’t need to, she did that for a hobby, I suppose but we never had to make anything, really, not that I know of. (Laughter)
        Q. Who was the doctor when you were growing up?
        A. Oh, Dr. Duverney, and Dr. McCleave, Dr. Ferguson, oh god, who, I forget who they all were now, Dr. Dickey, did I say him?
        Q. No.
        A. No, gee, I can’t think of anything else. They pretty well all lived on Queen Street too. (Laughter)
        Q. How often would you have left Digby? A. When I was growing up?
        Q. Yep.
        A. Oh gee, not very often. As I said, we went once, maybe once or twice a year to Halifax, probably not a, oh no, that would be it, that was it, and then going to Weymouth in the summer which was just like going to Siberia maybe, you never got home.
        Q. What were the roads like back then?

        A. Oh, they were all dirt roads (Laughter) and I clearly remember the day they paved Queen Street. This other young fella and I, we were just kids, we got into the tar on the sides of the road before it hardened, you know, and you could pick it up
        and chew it, and that stuff, we used to chew that stuff, yeah, and then we got it all over our clothes and everything but that was, everybody did that, all kids but before that we used to have, I remember the kids down the road, Paul Morehouse, and we’d get in a rock fight and we’d throw stones at each other. (Laughter) We’d stand in the street and throw stones at each other. (Laughter) when they paved it, that put a stop to that because you couldn’t find a stone anymore. (Laughter)
        Q. Who would have been in charge of maintaining them?
        A. Oh god, well I think Frank Robinson probably. He had a livery stable down where the, down on First Avenue and, gee, Church Street, yeah I guess it’s Church Street, he had a big livery barn there and had horses, teams of horses and things so I think he did a lot of maintenance around town at that time too and looked after that.
        Q. What had you expected to do when you were growing up? A. What did I expect to do?
        Q. Yes.
        A. When I was growing up?
        Q. Yep.
        A. Oh, I was gonna go to sea for a living, that’s what I expected to do and I don’t think it ever changed?
        Q. As a teen, what kinds of things would you do for fun? A. As a teenager?
        Q. Yep.
        A. Gee, not very much. We used to bowling once and a while and, they had the bowling alleys underneath the Catholic Church at the time, played basketball, played badminton, they used to have badminton at the Scout Hall, dances once and a while and that was about it.
        Q. Where did you say the bowling alley was?

        A. It was underneath the Catholic Church.
        Q. In....?
        A. On.....
        Q. On Queen street?
        A. Yep, yep, where the Catholic church is now, yep, but that’s what they..... Q. I didn’t know that was there.
        A. Yep.
        Q. I’ve never heard anyone talk about it.
        A. Didn’t you? Oh yeah, and the Scout Hall was right next door to it and that’s where they had the, used to have badminton, basketball, that’s sort of where the gym was for the school and they, when they were building the Catholic Church, they built it in bits and pieces, so that underneath it, the basement was the, at the time, was the, were making money by having a bowling alley there, they had four lanes. (Laughter)
        Q. Who would your screen idols have been?
        A. Geeze, god, oh, Hop Along Cassady, (Laughter) that was one, and Jean Autry, yep, William Boyd was Hop Along Cassady, I don’t remember ever having any other screen idols, these were when I was a little kid, gee, Tom Minks, oh I remember Tom Minks, he was a great guy, god.
        Q. What kind of music would you have liked?
        A. Well, I didn’t like any music until Wartime came along and I was old enough to start appreciating music or thinkin’ I did. I liked all the songs they had then but I don’t think there was, we never had, we never took any interest in Classical music or anything. We never had, other than the radio in the house, we never had anything, no victrolla’s or recorders or, you know, anything like that, so we only heard the radio. Sometimes we’d hear, we’d all hear all the modern music on the radio but that was it, that was all we ever had.
        Q. What stations would you listen to on your radio?
        A. Well, we used to listen to WEI in Boston, WOR in New Jersey, Loll Thomas used to broadcast from Chicago, I don’t know the name of the station but we never had any local stations, we used to get them, mostly American stations and

        we’d listen to them. Sunday night we’d listen to Charlie McCarthy and the Shadow, and the Green Hornet, and I forget who else we’d listen to in the day time ‘cause every time you’d got sick you’d stay home and I used to get sick a lot and I’d listen to Ma Perkin’s and all these Soap Operas that were going on. (Laughter)
        Q. Soap Operas?
        A. Oh yeah, just like they have today only they have them on t.v, but they had them on radio then, oh yeah, yeah, god what was it, I can’t, Argyle Sunday and, I can’t remember them all now.
        Q. What do you remember about dating?
        A. Dating, oh god. Not very much, I was awful shy. I had, well I guess it was in, I was in grade ten before I had a girlfriend, grade ten?, nine or ten before I had a girlfriend. I don’t remember much before that, we never had time for girls, god we had too many things to do. We’d go rabbit hunting and things like that, running around the woods playing. We used to, the kids and I in the neighborhood, we used to play kick the can and hide and, you know, things like this. There was always kids around, so we’d always play and there was always Scout trips and we had, there was always kids around, boys, girls, we didn’t have much time for them, god.
        Q. Once you left school, what did you do?
        A. Well, I went to sea for a living. That’s what I did my whole life after that, once I left school.
        Q. Tell me about being a sea captain?
        A. Well, I was, I didn’t get to be a sea captain ‘till nineteen sixty-two and before that, when you’re a sea captain you just sit back and, it’s like, they did a time in motion study one time and I was captain of a ship and they were figuring out what everybody did, so when they interviewed me, I said, “Well, I don’t do anything”, and I don’t do anything, I’m just here just in case somebody needs me, oh I used to enjoy my life.
        Q. How dangerous would your work have been?
        A. Oh, it was, sometimes it was dangerous, it was mostly boredom, and then there was a great, and then there was all these certain, things would happen and all of a sudden it was a panic and then you’d get back to a routine again. It depended on

        where you were and what you were doing. Some days it was kind of hectic and other days there was nothing. You could sit out and sun yourself all day. (Laughter)
        Q. Would you usually sail with big crews?
        A. Yep, yep. I was with the Hydrographic Service for a number of years and we always had large crews because we were doing hydrographic work and we’d, we had, we carried launches and they always, with the hydrographers they would go away and we’d have, depending on what we were doing, we’d have over a hundred in crew, so, and they would go away and the launches, there was always six launches, so there’d be six coxens and six, twelve helpers and the two hydrographers would go away on each launch, so we had big crews and they’d be gone all day and sometimes we’d loose them and have to go searchin’ for them depending on where we were and how foggy it was and this sort of thing, but it was great fun.
        Q. How did you meet your wife?
        A. I don’t know, how did I meet you? (Yelling to wife) I haven’t the faintest idea.
        Other. (Archer’s wife) (Laughter) Gee, what a short memory.
        A. Geeze, it’s only, it’s only forty-seven years ago.
        Other. (Archer’s wife) He knew a friend I was working with.
        A. Oh yeah, yeah, yeah, but I still don’t remember. I knew her, what’s her name?, Theriault, was it? (Yelling to wife)
        Other. (Archer’s wife) Yep, keep going.
        A. Yeah, yeah, and she was working at the, she was a nurse at the Digby Hospital then, what a mistake. (Laughter)
        Q. (Laughter) Could you tell me my wife’s full name? A. Joan Patricia.
        Q. How old were you when you got married?
        A. Twenty-four.
    """
    ]

# fake_summaries = {
#         {"title": "fake summary",
#         "timeRange": {"start": "[Start time]", "end": "[End time]"},
#         "body": "this is a fake summary, and is summary number one",
#         "keywords": ["Keyword1", "Keyword2", "Keyword3"],
#         "notes": {
#             "[Note Title1]": "[Note Body1]",
#             "[Note Title2]": "[Note Body2]"
#         }}

# }

# 'summary': 'this is a fake summary, and is summary number one.' 
# 'tags' : ['fake 1','fake 2', 'fake 3']
# `