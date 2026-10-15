"""Map a job title (plus the company's own category label) to a 2018 SOC major group.

Rule-based and auditable: every assignment records which rule fired. Rules are evaluated in order;
the first match wins. Titles that match nothing fall back to the company category, then to "00".
"""
import re

SOC_MAJOR = {
    "11": "Management",
    "13": "Business and Financial Operations",
    "15": "Computer and Mathematical",
    "17": "Architecture and Engineering",
    "19": "Life, Physical, and Social Science",
    "21": "Community and Social Service",
    "23": "Legal",
    "25": "Educational Instruction and Library",
    "27": "Arts, Design, Entertainment, Sports, and Media",
    "29": "Healthcare Practitioners and Technical",
    "31": "Healthcare Support",
    "33": "Protective Service",
    "35": "Food Preparation and Serving Related",
    "37": "Building and Grounds Cleaning and Maintenance",
    "39": "Personal Care and Service",
    "41": "Sales and Related",
    "43": "Office and Administrative Support",
    "45": "Farming, Fishing, and Forestry",
    "47": "Construction and Extraction",
    "49": "Installation, Maintenance, and Repair",
    "51": "Production",
    "53": "Transportation and Material Moving",
    "55": "Military Specific",
    "00": "Unclassified",
}

_NON_PEOPLE_MANAGER = (r"program|project|account|relationship|case|category|territory|store|engagement|"
                       r"customer success|customer solutions|solutions|partner|release|delivery|community|content|"
                       r"technical account|portfolio|channel|alliance")

RULES = [
    ("27", "art director", r"\b(creative|art) director\b"),
    ("11", "executive", r"\b(chief|vice president|\bvp\b|svp|evp|head of|director|general manager|president)\b"),
    ("29", "healthcare practitioner", r"\b(registered nurse|\brn\b|nurse practitioner|nurse|pharmacist|physician|"
                                      r"medical director|clinician|therap(ist|y)|optometrist|optician|dietitian|radiolog|"
                                      r"sonograph|paramedic|\bemt\b|pharmacy technician|medical technologist|"
                                      r"clinical lab|audiolog|hearing aid|physician assistant|medical science liaison)"),
    ("31", "healthcare support", r"\b(medical assistant|nursing assistant|\bcna\b|phlebotom|dental assistant|"
                                 r"home health|pharmacy (aide|assistant)|patient care)"),
    ("23", "legal", r"\b(attorney|counsel\b|lawyer|paralegal|legal (assistant|specialist|analyst)|patent agent)"),
    ("33", "protective", r"\b(security officer|security guard|guard\b|firefighter|police|loss prevention|asset protection)"),
    ("35", "food", r"\b(cook|chef|barista|food service|dishwasher|bartender|deli\b|food prep)"),
    ("37", "building & grounds", r"\b(janitor|custodian|housekeep|groundskeep|landscap|cleaner\b|sanitation worker)"),
    ("39", "personal care", r"\b(child ?care|fitness instructor|hair ?stylist|personal trainer)"),
    ("25", "education", r"\b(teacher|professor|lecturer|librarian|tutor|instructional designer)"),
    ("21", "community & social", r"\b(social worker|counselor|community health worker|health educator)"),
    ("15", "computer & math",
     r"(?-i:\bIT\b)|information technology|power platform|copilot|\b(software|developer|programmer|\bsde\b|\bswe\b|sre\b|site reliability|devops|full[- ]?stack|front[- ]?end|"
     r"back[- ]?end|mobile engineer|ios engineer|android|machine learning|\bml\b|\bai\b|artificial intelligence|"
     r"deep learning|data scien|applied scientist|research scientist,? (ai|ml|machine)|data engineer|data analyst|"
     r"analytics engineer|business intelligence|database|\bdba\b|cloud|security engineer|cyber ?security|"
     r"information security|penetration|offensive security|red team|soc analyst|network engineer|network administrator|"
     r"systems? administrator|sysadmin|it support|help ?desk|desktop support|it (specialist|technician|analyst)|"
     r"solutions? architect|enterprise architect|technical consultant|infrastructure engineer|platform engineer|"
     r"qa engineer|test engineer|quality assurance engineer|sdet|statistician|actuar|mathematician|operations research|"
     r"web developer|ux|ui designer|user experience|interaction designer|product designer|forward deployed|"
     r"data center technician|dc(o)? tech|computer scientist|firmware|embedded software|systems engineer|"
     r"automation engineer|it auditor|technical product manager|\bgpu\b.*engineer|compiler|kernel)"),
    ("27", "arts, design & media", r"\b(designer|creative director|art director|writer|editor|copywriter|content|"
                                   r"producer|photograph|video|animator|translator|interpreter|public relations|"
                                   r"communications (specialist|manager|lead)|brand|journalist|illustrator)"),
    ("19", "science", r"\b(scientist|chemist|biologist|physicist|geolog|geoscien|geophysic|economist|epidemiolog|"
                      r"toxicolog|pharmacolog|clinical research|research associate|lab(oratory)? (technician|analyst)|"
                      r"reservoir|environmental specialist|regulatory scientist|bioinformatic)"),
    ("17", "engineering", r"\b(engineer|engineering|asic|silicon|\brf\b|analog|layout|verification|physical design|"
                          r"architect\b|drafter|surveyor|cad\b|process control)"),
    ("47", "construction & extraction", r"\b(electrician|plumber|carpenter|construction (worker|laborer)|pipefitter|"
                                         r"roustabout|driller|iron ?worker|apprentice lineman)"),
    ("49", "installation & repair", r"\b(mechanic|maintenance|repair|hvac|field service|service technician|"
                                     r"installer|facilities technician|engineering operations technician)"),
    ("51", "production", r"\b(production|assembler|assembly|fabricat|machine operator|process operator|plant operator|"
                         r"operator\b|manufacturing (technician|associate)|process technician|quality (inspector|technician)|"
                         r"welder|baker|butcher|meat cutter|processing technician|operation technician|packag)"),
    ("53", "transportation & material moving", r"\b(driver|\bcdl\b|truck|forklift|warehouse|material handler|picker|packer|"
                                                r"fulfillment|stocker|order filler|loader|unloader|delivery|pilot\b|"
                                                r"dock|yard|freight|cart attendant|terminal operator|logistics associate)"),
    ("41", "sales", r"\b(sales|account executive|account manager|business development|retail|cashier|store|"
                    r"specialist: seasonal|\bspecialist\b(?!.*(engineer|data|security))|expert\b|"
                    r"originator|trader|merchandis|customer solutions manager|technical account manager|"
                    r"relationship manager|banker|go[- ]to[- ]market|growth (lead|manager)|market activation|"
                    r"sales specialist|seller)"),
    ("43", "office & admin", r"\b(administrative|receptionist|customer service rep|clerk|teller|data entry|"
                             r"scheduler|executive assistant|call center|dispatcher|office (assistant|coordinator)|"
                             r"recruiting coordinator|engagement coordinator)"),
    ("13", "business & finance", r"\b(analyst|accountant|accounting|auditor|audit|tax\b|recruit|talent|human resources|"
                                 r"\bhr\b|buyer|procurement|sourcing|purchas|program manager|project manager|"
                                 r"consultant|compliance|risk|underwriter|claims|treasury|finance|financial|"
                                 r"controller|payroll|benefits|contracts?|cost engineer|planner|planning|"
                                 r"strategist|advisor|strategy|operations|organizational|logistics|supply chain|"
                                 r"marketing|program|project|product manager|epm\b|voyage|charter)"),
    ("45", "farming", r"\b(agricultur|farm(er|worker)|forestry)"),
    ("11", "manager (fallback)", r"\b(manager|lead|leader|head)\b"),
]

_COMPILED = [(code, name, re.compile(rx, re.I)) for code, name, rx in RULES]
_MGR = re.compile(r"\b(manager|mgr)\b", re.I)
_NOT_PEOPLE_MGR = re.compile(rf"\b({_NON_PEOPLE_MANAGER})\s+(manager|mgr)\b|\b(program|project)\b", re.I)

# Company category labels -> SOC, used only when the title matches no rule.
CATEGORY_RULES = [
    ("15", r"software|machine learning|data|information technology|\bit\b|cloud|security|solutions architect"),
    ("17", r"hardware|engineering|asic|silicon"),
    ("41", r"retail|sales|business development"),
    ("13", r"finance|accounting|human resources|legal|risk|operations|supply chain|procurement|marketing"),
    ("19", r"research science|science|r&d"),
    ("53", r"fulfillment|warehouse|transportation|logistics"),
    ("29", r"clinical|medical|pharmacy|nursing"),
]
_CAT = [(code, re.compile(rx, re.I)) for code, rx in CATEGORY_RULES]


def classify(title, category=None):
    """Return (soc_code, rule_name)."""
    t = title or ""
    for code, name, rx in _COMPILED[:2]:
        if rx.search(t):
            return code, name
    if _MGR.search(t) and not _NOT_PEOPLE_MGR.search(t):
        return "11", "people manager"
    for code, name, rx in _COMPILED[2:]:
        if rx.search(t):
            return code, name
    if category:
        for code, rx in _CAT:
            if rx.search(category):
                return code, "company category"
    return "00", "unclassified"
