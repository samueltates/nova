import random

debug = {}
credentials = '{"token": "ya29.a0AWY7CkmXEArxPmjv6q0m23LMk_Yd6nXCiMK-wENAptDOnqkhaEiDsNFkL86pkevveYkKro6JbVsepcZL9Q5eZZAmwRnW_DV4SRHfaIS78d_tuGI3dVOkWeLULc9iw2Pv-VX1PDOCIs6hc9JdZ-auLmYpmIOlaCgYKAdUSARASFQG1tDrpkm5Jnrbl6inXcKPa574J5w0163", "refresh_token": "1//0gWDDLaYLHIbgCgYIARAAGBASNwF-L9IrNdKteGm4yI9wPqjTOl6n7A_dR6By6Kp5l4u-lQGTqnlfvW6YYtFd66xM6Xg7RnbQVjI", "token_uri": "https://oauth2.googleapis.com/token", "client_id": "901964319596-tieetv1opo684l71dcdjnraemhi5u6mh.apps.googleusercontent.com", "client_secret": "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", "scopes": ["https://www.googleapis.com/auth/userinfo.profile"], "expiry": "2023-06-01T15:44:09.229445Z"}'

##could we make an ezprint class (or debug object session fenced so calling that and it runs in that session) 

def eZprint(string):
    print('\n_____________')
    print(string )
    print('_____________\n')

def fakeResponse():
    return random.choice(["To be, or not to be, that is the question", "Love looks not with the eyes, but with the mind; and therefore is winged Cupid painted blind.", "Get thee to a nunnery. ",  "To be, or not to be: that is the question.",
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

