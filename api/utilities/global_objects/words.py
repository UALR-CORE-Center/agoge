import random


class Words:
    actions = [
        "Encrypting", "Decrypting", "Authenticating", "Authorizing", "Bypassing", "Compromising", "Defending",
        "Detecting", "Exposing",
        "Hijacking", "Intercepting", "Monitoring", "Obfuscating", "Patching", "Quarantining", "Recovering", "Scanning",
        "Screening",
        "Securing", "Shielding", "Spoofing", "Spying", "Tracking", "Validating", "Verifying", "Attacking", "Breaching",
        "Defacing", "Disabling",
        "Exploiting", "Filtering", "Fortifying", "Guarding", "Logging", "Masking", "Neutralizing", "Reinforcing",
        "Rescuing", "Restoring",
        "Retaliating", "Revoking", "Safeguarding", "Strengthening", "Thwarting", "Uncovering", "Warning", "Wiping",
        "Blocking"
    ]
    animals = [
        "Lion", "Tiger", "Elephant", "Giraffe", "Zebra", "Hippopotamus", "Kangaroo", "Panda", "Gorilla", "Rhinoceros",
        "Cheetah", "Bear", "Wolf", "Fox", "Deer", "Owl", "Eagle", "Falcon", "Parrot", "Swan", "Dolphin", "Shark",
        "Whale", "Octopus", "Turtle", "Crocodile", "Alligator", "Rabbit", "Squirrel", "Rat", "Bat", "Beaver", "Moose",
        "Buffalo", "Porcupine", "Raccoon", "Lynx", "Hedgehog", "Skunk", "Ferret", "Lemur", "Otter", "Sloth", "Anteater",
        "Chameleon", "Cobra", "Frog", "Toad", "Salamander", "Newt"
    ]
    colors = [
        "Red", "Blue", "Green", "Yellow", "Orange", "Purple", "Pink", "Black", "White", "Gray", "Brown", "Beige",
        "Cyan",
        "Magenta", "Lime", "Maroon", "Navy", "Olive", "Teal", "Aqua", "Coral", "Fuchsia", "Gold", "Ivory", "Khaki",
        "Lavender", "Silver", "Tan", "Violet", "Wheat", "Amber", "Azure", "Bronze", "Charcoal", "Chocolate", "Cobalt",
        "Cream", "Emerald", "Indigo", "Jade", "Mauve", "Peach", "Ruby", "Saffron", "Salmon", "Sapphire", "Scarlet",
        "Sepia", "Ultramarine"
    ]
    item = [
        "Battery", "Staple", "Pencil", "Chair", "Table", "Laptop", "Book", "Notebook", "Pen", "Cup",
        "Plate", "Spoon", "Fork", "Knife", "Lamp", "Bag", "Wallet", "Keys", "Clock", "Phone",
        "Scissors", "Paper", "Clip", "Monitor", "Mouse", "Keyboard", "Printer", "Plant", "Fan", "Heater",
        "Mug", "Bottle", "Glasses", "Shirt", "Pants", "Shoes", "Socks", "Hat", "Towel", "Soap",
        "Shampoo", "Toothbrush", "Toothpaste", "Comb", "Brush", "Tissue", "Picture", "Vase", "Candle", "Remote"
    ]

    def generate_str(self) -> str:
        item = random.choice(self.item)
        animal = random.choice(self.animals)
        action = random.choice(self.actions)
        phrase = f'{random.randint(0, 9)}{item}{action}{animal}{random.randint(0, 9)}'

        if len(phrase) < 12:
            color = random.choice(self.colors)
            phrase = f"{color}{phrase}"
        return phrase

