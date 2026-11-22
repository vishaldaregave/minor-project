"""e_number_map.py — Maps E-numbers to canonical substance names and health contexts.

Comprehensive registry covering colours, preservatives, antioxidants, emulsifiers,
flavour enhancers, sweeteners, and acidity regulators.
"""

from __future__ import annotations

import re
from typing import Optional


E_NUMBER_MAP: dict[str, str] = {
    # Colours
    "E100": "Curcumin",
    "E101": "Riboflavin",
    "E102": "Tartrazine",
    "E104": "Quinoline Yellow",
    "E110": "Sunset Yellow FCF",
    "E120": "Cochineal / Carmine",
    "E122": "Carmoisine / Azorubine",
    "E123": "Amaranth",
    "E124": "Ponceau 4R",
    "E127": "Erythrosine",
    "E129": "Allura Red AC",
    "E131": "Patent Blue V",
    "E132": "Indigotine",
    "E133": "Brilliant Blue FCF",
    "E140": "Chlorophylls",
    "E141": "Copper complexes of chlorophylls",
    "E150a": "Plain Caramel",
    "E150b": "Caustic sulphite caramel",
    "E150c": "Ammonia caramel",
    "E150d": "Sulphite Ammonia Caramel",
    "E151": "Brilliant Black BN",
    "E153": "Vegetable Carbon",
    "E155": "Brown HT",
    "E160a": "Beta-Carotene",
    "E160b": "Annatto / Bixin / Norbixin",
    "E160c": "Paprika extract",
    "E160d": "Lycopene",
    "E162": "Beetroot Red",
    "E163": "Anthocyanins",
    "E170": "Calcium Carbonate",
    "E171": "Titanium Dioxide",
    "E172": "Iron Oxides",

    # Preservatives
    "E200": "Sorbic Acid",
    "E202": "Potassium Sorbate",
    "E210": "Benzoic Acid",
    "E211": "Sodium Benzoate",
    "E212": "Potassium Benzoate",
    "E213": "Calcium Benzoate",
    "E220": "Sulphur Dioxide",
    "E221": "Sodium Sulphite",
    "E222": "Sodium Hydrogen Sulphite",
    "E223": "Sodium Metabisulphite",
    "E224": "Potassium Metabisulphite",
    "E249": "Potassium Nitrite",
    "E250": "Sodium Nitrite",
    "E251": "Sodium Nitrate",
    "E252": "Potassium Nitrate",
    "E260": "Acetic Acid",
    "E261": "Potassium Acetate",
    "E262": "Sodium Acetates",
    "E270": "Lactic Acid",
    "E280": "Propionic Acid",
    "E281": "Sodium Propionate",
    "E282": "Calcium Propionate",
    "E283": "Potassium Propionate",
    "E290": "Carbon Dioxide",
    "E296": "Malic Acid",
    "E297": "Fumaric Acid",

    # Antioxidants
    "E300": "Ascorbic Acid (Vitamin C)",
    "E301": "Sodium Ascorbate",
    "E304": "Fatty acid esters of ascorbic acid",
    "E306": "Tocopherols (Vitamin E)",
    "E307": "Alpha-Tocopherol",
    "E310": "Propyl Gallate",
    "E319": "TBHQ (Tertiary Butylhydroquinone)",
    "E320": "BHA (Butylated Hydroxyanisole)",
    "E321": "BHT (Butylated Hydroxytoluene)",
    "E322": "Lecithins",

    # Acidity regulators & Sequestering agents
    "E330": "Citric Acid",
    "E331": "Sodium Citrate",
    "E332": "Potassium Citrate",
    "E334": "Tartaric Acid",
    "E338": "Phosphoric Acid",
    "E339": "Sodium Phosphates",
    "E340": "Potassium Phosphates",
    "E341": "Calcium Phosphates",

    # Thickeners, Stabilisers & Emulsifiers
    "E400": "Alginic Acid",
    "E401": "Sodium Alginate",
    "E406": "Agar",
    "E407": "Carrageenan",
    "E407a": "Processed Eucheuma Seaweed",
    "E410": "Locust Bean Gum",
    "E412": "Guar Gum",
    "E414": "Acacia Gum (Gum Arabic)",
    "E415": "Xanthan Gum",
    "E418": "Gellan Gum",
    "E420": "Sorbitol",
    "E421": "Mannitol",
    "E422": "Glycerol",
    "E440": "Pectin",
    "E450": "Diphosphates",
    "E451": "Triphosphates",
    "E452": "Polyphosphates",
    "E460": "Cellulose",
    "E461": "Methyl Cellulose",
    "E466": "Sodium Carboxymethylcellulose",
    "E471": "Mono- and Diglycerides of Fatty Acids",
    "E472e": "DATEM (Mono- and diacetyl tartaric acid esters)",
    "E476": "Polyglycerol Polyricinoleate (PGPR)",
    "E481": "Sodium Stearoyl-2-Lactylate",
    "E482": "Calcium Stearoyl-2-Lactylate",

    # Flavour Enhancers
    "E620": "Glutamic Acid",
    "E621": "Monosodium Glutamate (MSG)",
    "E627": "Disodium Guanylate",
    "E631": "Disodium Inosinate",
    "E635": "Disodium 5'-ribonucleotides",

    # Sweeteners
    "E950": "Acesulfame K",
    "E951": "Aspartame",
    "E952": "Cyclamate",
    "E954": "Saccharin",
    "E955": "Sucralose",
    "E960": "Steviol Glycosides (Stevia)",
    "E965": "Maltitol",
    "E967": "Xylitol",
    "E968": "Erythritol",

    # Miscellaneous / Glazing / Gas
    "E500": "Sodium Carbonates (Baking Soda)",
    "E503": "Ammonium Carbonates",
    "E551": "Silicon Dioxide",
    "E901": "Beeswax",
    "E903": "Carnauba Wax",
    "E904": "Shellac",
}

# Reverse lookup dictionary (lowercase substance name -> E-number)
REVERSE_E_MAP: dict[str, str] = {
    name.lower(): e_num for e_num, name in E_NUMBER_MAP.items()
}


def normalise_e_number(text: str) -> Optional[dict]:
    """Extract and resolve an E-number from a raw text token or string.

    Handles formats like 'E102', 'E-102', 'INS 102', '102', etc.
    """
    cleaned = text.strip()
    match = re.search(r"\b(E|INS)?\s*[-]?\s*([1-9][0-9]{2}[a-z]?)\b", cleaned, re.IGNORECASE)
    if match:
        prefix = match.group(1) or ""
        code = match.group(2).lower()
        # Canonical e-key is uppercase E + code
        key = f"E{code.upper()}"
        if key in E_NUMBER_MAP:
            return {"e_number": key, "name": E_NUMBER_MAP[key]}
        # Also check without letter suffix
        base_key = f"E{re.sub(r'[a-z]$', '', code).upper()}"
        if base_key in E_NUMBER_MAP:
            return {"e_number": base_key, "name": E_NUMBER_MAP[base_key]}

    # Check text name against known reverse mapping
    lowered = cleaned.lower()
    for name_key, e_num in REVERSE_E_MAP.items():
        if name_key in lowered:
            return {"e_number": e_num, "name": E_NUMBER_MAP[e_num]}

    return None
