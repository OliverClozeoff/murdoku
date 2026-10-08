"""Flavor text: why the murderer did it. Shown after the case is solved."""
from __future__ import annotations

import random

# {m} = murderer, {v} = victim, {room} = where it happened. Names only, no pronouns.
MOTIVES = [
    "{v} had found out that {m} was secretly forging the family will. One quiet moment in the {room} was all {m} needed to keep it that way.",
    "Years ago, {v} took the credit for {m}'s greatest invention. {m} never forgot, and the {room} was where the debt was finally settled.",
    "{v} was about to reveal that {m} had been embezzling from the family business. {m} made sure the meeting in the {room} was {v}'s last.",
    "{m} had loved the same person as {v} for twenty years. When {v} announced the engagement over dinner, something in {m} snapped.",
    "{v} knew {m}'s real name, and the crime that came with it. Blackmail had worked for years, until {m} decided it wouldn't anymore.",
    "{v} had changed the inheritance at the last minute, cutting {m} out completely. {m} found out an hour before visiting the {room}.",
    "{m} had been poisoning {v}'s tea for weeks, but {v} was finally getting suspicious. The {room} offered a quicker solution.",
    "{v} had accidentally seen {m} burying something in the garden. {m} couldn't take the risk that {v} would start digging.",
    "{v} was the only witness to the fire that ruined {m}'s rival. Without {v}, nobody could ever connect the dots.",
    "{m} had been selling the family heirlooms one by one and replacing them with fakes. {v}, an amateur appraiser, noticed.",
    "{v} had threatened to publish {m}'s secret diary. {m} decided some stories are better left unfinished.",
    "{m} owed {v} a fortune in gambling debts. {v} wanted to be paid by midnight. {m} paid in a different way.",
    "{v} was about to sell the house, the one place {m} had ever called home. {m} wasn't going anywhere.",
    "{v} had discovered that the 'lucky' lottery ticket {m} cashed last spring actually belonged to {v}.",
    "{m} and {v} were rival authors, and {v}'s new novel was {m}'s stolen manuscript. Publication day never came.",
    "{v} had reported {m} to the police years ago. {m} spent a decade planning this reunion in the {room}.",
    "{m} had faked a death once before. {v} recognized the face behind the new name, and {m} couldn't risk a second exposure.",
    "{v} was quietly changing the recipe {m} had sworn to protect. To {m}, the family secret was worth more than {v}.",
    "{v} had been reading {m}'s letters for months. When {v} hinted at what they contained, {m} lured {v} into the {room}.",
    "{m} was the true heir, and {v} was the only one who could prove it. {v} preferred to keep that proof hidden. {m} didn't.",
    "{v} kept beating {m} at chess, every single Sunday, for thirty years. Some grudges simply grow too big for the board.",
    "{v} had sabotaged {m}'s wedding, career and garden competition. The prize-winning roses were the last straw.",
    "{m} had been impersonating a doctor for years. {v}, an actual doctor, asked one question too many in the {room}.",
    "{v} was planning to expose the smuggling ring operating out of the cellar. {m} ran that ring.",
    "{v} had insured {m}'s life for an enormous sum and was looking very interested in the stairs. {m} simply struck first.",
    "{m} wanted the {room} renovated. {v} refused, again. Nobody will refuse {m} about the {room} ever again.",
]


def make_motive(murderer: str, victim: str, room: str, rng: random.Random) -> str:
    return rng.choice(MOTIVES).format(m=murderer, v=victim, room=room)
