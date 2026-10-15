"""Skill and license/certification dictionaries.

Each entry: canonical name -> (family, regex). Regexes are case-insensitive unless the entry
name is in CASE_SENSITIVE (short tokens such as R, C, Go that collide with ordinary words).
Extend by adding rows; the build step reports which skills matched nothing so the list can grow.
"""
import re

SKILLS = {
    # Programming languages
    "Python": ("Programming", r"\bpython\b"),
    "Java": ("Programming", r"\bjava\b(?!script)"),
    "JavaScript": ("Programming", r"\bjavascript\b|\bnode\.?js\b"),
    "TypeScript": ("Programming", r"\btypescript\b"),
    "C++": ("Programming", r"\bc\+\+"),
    "C": ("Programming", r"(?<![\w+#/-])C(?=\s*(?:/|,|or|and)\s*C\+\+)|\bC programming\b|\bC language\b|"
                         r"(?:C\+\+|Java|Python),\s*C(?![\w+#-])"),
    "C#": ("Programming", r"\bc#|\.net\b"),
    "Go": ("Programming", r"\bgolang\b|(?<![\w-])Go(?=\s*(?:,|/|\)|and\b|or\b|programming|language))"),
    "Rust": ("Programming", r"\brust\b"),
    "Kotlin": ("Programming", r"\bkotlin\b"),
    "Swift": ("Programming", r"\bswift\b(?!ly)"),
    "Scala": ("Programming", r"\bscala\b"),
    "R": ("Programming", r"(?<![\w-])R(?=\s*(?:,|/|\)|and\b|or\b|programming|language|Studio))(?<!\bR&)"),
    "SQL": ("Data & Analytics", r"\bsql\b|\bpostgres|\bmysql\b|\bt-sql\b|\bpl/sql\b"),
    "Perl": ("Programming", r"\bperl\b"),
    "Bash/Shell": ("Programming", r"\bbash\b|\bshell script"),
    "MATLAB": ("Programming", r"\bmatlab\b"),
    "Verilog/SystemVerilog": ("Hardware & Semiconductors", r"\b(system ?)?verilog\b|\bvhdl\b"),
    "Object-oriented design": ("Programming", r"object[- ]oriented"),
    "Data structures & algorithms": ("Programming", r"data structures|algorithms"),
    "API design": ("Programming", r"\bapis?\b|\brest(ful)?\b"),
    "React": ("Programming", r"\breact(\.js)?\b"),
    "Android development": ("Programming", r"\bandroid\b"),
    "iOS development": ("Programming", r"\bios\b(?! ?xr)"),
    # Cloud, infrastructure, security
    "AWS": ("Cloud & Infrastructure", r"\baws\b|amazon web services"),
    "Microsoft Azure": ("Cloud & Infrastructure", r"\bazure\b"),
    "Google Cloud": ("Cloud & Infrastructure", r"google cloud|\bgcp\b"),
    "Kubernetes": ("Cloud & Infrastructure", r"\bkubernetes\b|\bk8s\b"),
    "Docker/containers": ("Cloud & Infrastructure", r"\bdocker\b|container"),
    "Linux": ("Cloud & Infrastructure", r"\blinux\b|\bunix\b"),
    "Networking (TCP/IP)": ("Cloud & Infrastructure", r"\btcp/ip\b|\bnetworking\b|layer [123]|\bbgp\b|\bdns\b"),
    "DevOps / CI/CD": ("Cloud & Infrastructure", r"\bdevops\b|\bci/cd\b|continuous integration|jenkins|terraform"),
    "Distributed systems": ("Cloud & Infrastructure", r"distributed systems?"),
    "Cybersecurity": ("Cloud & Infrastructure", r"cyber ?security|information security|red team|penetration test|threat"),
    "Hardware troubleshooting": ("Cloud & Infrastructure", r"hardware (troubleshoot|components)|server hardware|computer hardware"),
    # Data & AI
    "Machine learning": ("Data & AI", r"machine learning|\bml\b"),
    "Deep learning": ("Data & AI", r"deep learning|neural network"),
    "Generative AI / LLMs": ("Data & AI", r"generative ai|\bgenai\b|\bllms?\b|large language model|\brag\b|"
                                          r"retrieval[- ]augmented|multi-agent|conversational ai|foundation model"),
    "PyTorch/TensorFlow": ("Data & AI", r"pytorch|tensorflow|\bjax\b"),
    "CUDA / GPU computing": ("Data & AI", r"\bcuda\b|\bgpu\b"),
    "Statistics": ("Data & AI", r"statistic"),
    "Data analysis": ("Data & AI", r"data analysis|analytics|analytical"),
    "Data visualization": ("Data & AI", r"tableau|power bi|data visuali[sz]ation|looker"),
    "Spark/Big data": ("Data & AI", r"\bspark\b|hadoop|big data|databricks|snowflake"),
    "Recommendation systems": ("Data & AI", r"recommendation systems?|recommender"),
    "Vector databases": ("Data & AI", r"vector databases?"),
    "Excel": ("Business & Finance", r"\bexcel\b"),
    "Microsoft Office": ("Business & Finance", r"microsoft office|ms office|office suite"),
    # Hardware, engineering, energy
    "ASIC / chip design": ("Hardware & Semiconductors", r"\basic\b|tape[- ]?out|physical design|rtl\b|chip design"),
    "RF / test equipment": ("Hardware & Semiconductors", r"\brf\b|spectrum analy|oscilloscope|network analy"),
    "Semiconductor process": ("Hardware & Semiconductors", r"thin[- ]film|wafer|lithograph|etch\b|deposition"),
    "Electrical systems": ("Engineering & Operations", r"electrical systems?|power distribution"),
    "Mechanical systems": ("Engineering & Operations", r"mechanical systems?|hvac"),
    "CAD": ("Engineering & Operations", r"\bcad\b|autocad|solidworks|catia"),
    "CFD / simulation": ("Engineering & Operations", r"\bcfd\b|simulation|finite element|\bfea\b"),
    "Process control": ("Engineering & Operations", r"process control|\bdcs\b|\bplc\b|\bapc\b"),
    "Construction documents": ("Engineering & Operations", r"construction (drawings|documents)|building codes|design drawings"),
    "Equipment operation (forklift, cranes)": ("Engineering & Operations", r"forklift|crane|rigging|pallet jack"),
    "Quality / Six Sigma": ("Engineering & Operations", r"six sigma|lean manufacturing|quality systems?|\bgmp\b"),
    "Supply chain": ("Business & Finance", r"supply chain|logistics|procurement|sourcing|demand planning"),
    # Business & finance
    "Financial modeling": ("Business & Finance", r"financial model|valuation|forecasting"),
    "Accounting": ("Business & Finance", r"\baccounting\b|\bgaap\b|reconciliation"),
    "Risk management": ("Business & Finance", r"risk management|market risk|credit risk"),
    "Trading / markets": ("Business & Finance", r"\btrading\b|commodit|derivatives"),
    "SAP / ERP": ("Business & Finance", r"\bsap\b|\berp\b|oracle financials|workday"),
    "Project management": ("Business & Finance", r"project management|program management|agile|scrum"),
    "Budget management": ("Business & Finance", r"budget"),
    "Sales / business development": ("Business & Finance", r"\bsales\b|business development|go[- ]to[- ]market|pipeline"),
    "Marketing": ("Business & Finance", r"\bmarketing\b|campaign"),
    "Customer service": ("Business & Finance", r"customer service|customer experience|client relationships?"),
    "Recruiting / HR": ("Business & Finance", r"recruit|talent acquisition|human resources|\bhr\b"),
    # Health & life sciences
    "Clinical research": ("Health & Life Sciences", r"clinical (trial|research|development)|\bgcp\b guidelines"),
    "Regulatory affairs": ("Health & Life Sciences", r"regulatory (affairs|submissions)|\bfda\b"),
    "Patient care": ("Health & Life Sciences", r"patient care|patient"),
    "Laboratory techniques": ("Health & Life Sciences", r"laboratory|\bhplc\b|\bpcr\b|assay"),
    # Transferable
    "Communication": ("Transferable", r"communication skills|written and verbal|verbal and written|communicat"),
    "Leadership": ("Transferable", r"leadership|lead teams|people management"),
    "Collaboration": ("Transferable", r"collaborat|cross[- ]functional|teamwork"),
    "Problem solving": ("Transferable", r"problem[- ]solving|troubleshoot"),
    "Stakeholder management": ("Transferable", r"stakeholder"),
    "Technical writing": ("Transferable", r"technical writing|documentation"),
}

CASE_SENSITIVE = {"C", "Go", "R"}

LICENSES = {
    "Professional Engineer (PE)": r"\bprofessional engineer\b|\bP\.?E\.? licen|\bPE licen",
    "CPA": r"\bcpa\b|certified public accountant",
    "CFA": r"\bcfa\b|chartered financial analyst",
    "FINRA Series licenses": r"series (7|24|63|65|66|79)\b",
    "Registered Nurse (RN) license": r"\brn licen|registered nurse licen|\bregistered nurse\b",
    "Pharmacist license": r"pharmacist licen|licensed pharmacist|\brph\b",
    "Pharmacy technician cert": r"\bcpht\b|pharmacy technician (license|certification)",
    "BLS/ACLS": r"\bbls\b|\bacls\b|basic life support",
    "Medical license (MD/DO)": r"\bmd\b licen|medical licen|board[- ]certified",
    "Bar admission": r"admitted to (the|practice)|bar admission|licensed to practice law",
    "PMP": r"\bpmp\b|project management professional",
    "Scrum/Agile cert": r"\bcsm\b|certified scrum|\bsafe\b agil",
    "Six Sigma cert": r"six sigma (green|black|yellow) belt",
    "CISSP": r"\bcissp\b",
    "CISM/CISA": r"\bcism\b|\bcisa\b",
    "CompTIA (A+/Network+/Security+/Linux+/Cloud+)": r"\ba\+|\bnet(work)?\+|\bsec(urity)?\+|\blinux\+|\bcloud\+|comptia",
    "Cisco (CCNA/CCNP)": r"\bccna\b|\bccnp\b|\bccie\b",
    "GIAC (GSEC/GICSP etc.)": r"\bgsec\b|\bgicsp\b|\bgiac\b",
    "SSCP": r"\bsscp\b",
    "Cloud certification (AWS/Azure/GCP)": r"aws certif|aws or other cloud certification|azure certif|cloud certification|"
                                           r"certified solutions architect|google cloud certif",
    "Linux certification (LPIC/RHCE)": r"\blpic\b|\brhce\b|\brhcsa\b",
    "ITIL": r"\bitil\b",
    "Security clearance": r"security clearance|\bts/sci\b|top secret|secret clearance|polygraph",
    "Commercial driver's license (CDL)": r"\bcdl\b|commercial driver",
    "Driver's license": r"valid driver'?s licen",
    "Forklift certification": r"forklift (certif|licen)",
    "OSHA certification": r"\bosha\b ?(10|30|certif)",
    "Electrician license": r"journeyman|master electrician|electrical licen",
    "EPA 608": r"\bepa 608\b|epa section 608",
    "Food handler / ServSafe": r"servsafe|food handler",
}

_SK = [(name, fam, re.compile(rx, 0 if name in CASE_SENSITIVE else re.I)) for name, (fam, rx) in SKILLS.items()]
_LIC = [(name, re.compile(rx, re.I)) for name, rx in LICENSES.items()]
SKILL_FAMILY = {name: fam for name, (fam, _) in SKILLS.items()}


def find_skills(text):
    if not text:
        return []
    return [name for name, _, rx in _SK if rx.search(text)]


def find_licenses(text):
    if not text:
        return []
    return [name for name, rx in _LIC if rx.search(text)]
