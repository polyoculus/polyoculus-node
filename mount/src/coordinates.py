from dataclasses import dataclass


# empty for now. Fill with logic later.

"""
what do we need here?
- encode logic (converting the coordinates into something PyINDI can send to indiserver)
- decode logic (the reverse of the above)
- coordinate plane implementation (keeping track of where we have been and what we have done via a set (where duplicate coordinate entries do not exist))
"""


# for the encode and decode logic
class CoordinateTracking:
    pass


# a simple class to act as a wrapper for a tuple which are our coordinates
@dataclass
class Coordinate:
    pass


# a simple class to act as a wrapper for Right Ascension
@dataclass
class RightAscension:
    pass


# a simple class to act as a wrapper for Declination
@dataclass
class Declination:
    pass
