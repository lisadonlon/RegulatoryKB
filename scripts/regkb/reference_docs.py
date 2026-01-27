"""
Reference checklist of essential regulatory documents for medical devices.
Organized by jurisdiction with priority: EU, UK, US, then other English-speaking jurisdictions.
"""

REFERENCE_DOCUMENTS = {
    # ===========================================
    # TIER 1: EU, UK, US
    # ===========================================
    "EU": {
        "regulations": [
            {
                "id": "EU-REG-001",
                "title": "MDR 2017/745",
                "description": "Medical Device Regulation",
                "mandatory": True,
            },
            {
                "id": "EU-REG-002",
                "title": "IVDR 2017/746",
                "description": "In Vitro Diagnostic Regulation",
                "mandatory": True,
            },
            {
                "id": "EU-REG-003",
                "title": "MDD 93/42/EEC",
                "description": "Medical Device Directive (legacy)",
                "mandatory": False,
            },
            {
                "id": "EU-REG-004",
                "title": "AIMDD 90/385/EEC",
                "description": "Active Implantable Medical Device Directive (legacy)",
                "mandatory": False,
            },
            {
                "id": "EU-REG-005",
                "title": "Common Specifications",
                "description": "EU Common Specifications for Annex XVI devices",
                "mandatory": True,
            },
        ],
        "mdcg_guidance": [
            # Classification & Qualification
            {
                "id": "EU-MDCG-001",
                "title": "MDCG 2019-11",
                "description": "Guidance on qualification and classification of software",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-002",
                "title": "MDCG 2021-24",
                "description": "Guidance on classification of medical devices",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-003",
                "title": "MDCG 2022-5",
                "description": "Guidance on borderline products",
                "mandatory": True,
            },
            # Clinical Evaluation
            {
                "id": "EU-MDCG-010",
                "title": "MDCG 2020-1",
                "description": "Clinical evaluation of medical device software",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-011",
                "title": "MDCG 2020-5",
                "description": "Clinical evaluation - equivalence",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-012",
                "title": "MDCG 2020-6",
                "description": "Sufficient clinical evidence for legacy devices",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-013",
                "title": "MDCG 2020-13",
                "description": "Clinical evaluation assessment report template",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-014",
                "title": "MDCG 2024-5",
                "description": "Clinical evaluation guidance update",
                "mandatory": True,
            },
            # Post-Market Surveillance & Vigilance
            {
                "id": "EU-MDCG-020",
                "title": "MDCG 2020-7",
                "description": "PMS plan template",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-021",
                "title": "MDCG 2020-8",
                "description": "PMCF plan and report templates",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-022",
                "title": "MDCG 2023-3",
                "description": "Q&A on vigilance",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-023",
                "title": "MDCG 2024-3",
                "description": "Vigilance guidance update",
                "mandatory": True,
            },
            # Technical Documentation
            {
                "id": "EU-MDCG-030",
                "title": "MDCG 2019-9",
                "description": "Summary of Safety and Clinical Performance",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-031",
                "title": "MDCG 2021-8",
                "description": "Q&A on Annex I requirements",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-032",
                "title": "MDCG 2022-14",
                "description": "GSPR mapping guidance",
                "mandatory": True,
            },
            # UDI & EUDAMED
            {
                "id": "EU-MDCG-040",
                "title": "MDCG 2018-1",
                "description": "UDI guidance",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-041",
                "title": "MDCG 2019-4",
                "description": "EUDAMED timelines",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-042",
                "title": "MDCG 2021-13",
                "description": "Q&A on registration EUDAMED",
                "mandatory": True,
            },
            # Software/Cybersecurity
            {
                "id": "EU-MDCG-050",
                "title": "MDCG 2019-16",
                "description": "Cybersecurity guidance",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-051",
                "title": "MDCG 2023-4",
                "description": "Software lifecycle guidance",
                "mandatory": True,
            },
            # Notified Bodies & Conformity Assessment
            {
                "id": "EU-MDCG-060",
                "title": "MDCG 2019-6",
                "description": "Q&A on Article 97",
                "mandatory": False,
            },
            {
                "id": "EU-MDCG-061",
                "title": "MDCG 2022-4",
                "description": "Significant changes guidance",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-062",
                "title": "MDCG 2023-7",
                "description": "Certification transfer guidance",
                "mandatory": True,
            },
            # Annex XVI (Non-medical aesthetic devices)
            {
                "id": "EU-MDCG-070",
                "title": "MDCG 2023-5",
                "description": "Annex XVI classification guidance",
                "mandatory": False,
            },
            # Labelling & IFU
            {
                "id": "EU-MDCG-080",
                "title": "MDCG 2019-7",
                "description": "Guidance on labelling",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-081",
                "title": "MDCG 2021-21",
                "description": "eIFU guidance",
                "mandatory": True,
            },
            # Transition & Legacy
            {
                "id": "EU-MDCG-090",
                "title": "MDCG 2020-3",
                "description": "Legacy devices transition",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-091",
                "title": "MDCG 2024-2",
                "description": "Extended transition timelines",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-092",
                "title": "MDCG 2025-4",
                "description": "Latest transition Q&A",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-093",
                "title": "MDCG 2025-6",
                "description": "Stockpiling guidance",
                "mandatory": True,
            },
            {
                "id": "EU-MDCG-094",
                "title": "MDCG 2025-9",
                "description": "PMCF for legacy devices",
                "mandatory": True,
            },
        ],
        "other_guidance": [
            {
                "id": "EU-OTH-001",
                "title": "Blue Guide 2022",
                "description": "Implementation of EU product rules",
                "mandatory": True,
            },
            {
                "id": "EU-OTH-002",
                "title": "MEDDEV 2.7/1 rev 4",
                "description": "Clinical evaluation guidance (legacy but useful)",
                "mandatory": False,
            },
            {
                "id": "EU-OTH-003",
                "title": "Team-NB Position Papers",
                "description": "Notified body consensus positions",
                "mandatory": False,
            },
            {
                "id": "EU-OTH-004",
                "title": "Borderline Manual",
                "description": "EC borderline and classification manual",
                "mandatory": True,
            },
        ],
    },
    "UK": {
        "regulations": [
            {
                "id": "UK-REG-001",
                "title": "UK MDR 2002 (as amended)",
                "description": "UK Medical Device Regulations",
                "mandatory": True,
            },
            {
                "id": "UK-REG-002",
                "title": "UKCA Marking Requirements",
                "description": "UK Conformity Assessment requirements",
                "mandatory": True,
            },
        ],
        "guidance": [
            {
                "id": "UK-GUID-001",
                "title": "MHRA Guidance: Regulating medical devices in the UK",
                "description": "Core MHRA guidance",
                "mandatory": True,
            },
            {
                "id": "UK-GUID-002",
                "title": "MHRA Software as Medical Device Guidance",
                "description": "SaMD classification and requirements",
                "mandatory": True,
            },
            {
                "id": "UK-GUID-003",
                "title": "MHRA Clinical Investigation Guidance",
                "description": "Requirements for clinical studies",
                "mandatory": True,
            },
            {
                "id": "UK-GUID-004",
                "title": "MHRA Post-Market Surveillance Guidance",
                "description": "UK PMS requirements",
                "mandatory": True,
            },
            {
                "id": "UK-GUID-005",
                "title": "MHRA Adverse Incident Reporting",
                "description": "UK vigilance requirements",
                "mandatory": True,
            },
            {
                "id": "UK-GUID-006",
                "title": "MHRA UKCA Transition Guidance",
                "description": "Transition from CE to UKCA",
                "mandatory": True,
            },
        ],
    },
    "US": {
        "regulations": [
            {
                "id": "US-REG-001",
                "title": "21 CFR Part 820",
                "description": "Quality System Regulation",
                "mandatory": True,
            },
            {
                "id": "US-REG-002",
                "title": "21 CFR Part 803",
                "description": "Medical Device Reporting",
                "mandatory": True,
            },
            {
                "id": "US-REG-003",
                "title": "21 CFR Part 806",
                "description": "Medical Device Corrections and Removals",
                "mandatory": True,
            },
            {
                "id": "US-REG-004",
                "title": "21 CFR Part 807",
                "description": "Establishment Registration and Device Listing",
                "mandatory": True,
            },
            {
                "id": "US-REG-005",
                "title": "21 CFR Part 812",
                "description": "Investigational Device Exemptions",
                "mandatory": True,
            },
            {
                "id": "US-REG-006",
                "title": "21 CFR Part 814",
                "description": "Premarket Approval",
                "mandatory": True,
            },
            {
                "id": "US-REG-007",
                "title": "21 CFR Part 830",
                "description": "Unique Device Identification",
                "mandatory": True,
            },
            {
                "id": "US-REG-008",
                "title": "21 CFR Part 860",
                "description": "Medical Device Classification Procedures",
                "mandatory": True,
            },
        ],
        "guidance": [
            # 510(k)
            {
                "id": "US-GUID-001",
                "title": "510(k) Program Guidance",
                "description": "Traditional 510(k) submission guidance",
                "mandatory": True,
            },
            {
                "id": "US-GUID-002",
                "title": "Abbreviated 510(k) Guidance",
                "description": "Abbreviated 510(k) pathway",
                "mandatory": True,
            },
            {
                "id": "US-GUID-003",
                "title": "Special 510(k) Guidance",
                "description": "Special 510(k) for design changes",
                "mandatory": True,
            },
            {
                "id": "US-GUID-004",
                "title": "Substantial Equivalence Guidance",
                "description": "Determining substantial equivalence",
                "mandatory": True,
            },
            {
                "id": "US-GUID-005",
                "title": "Refuse to Accept Policy for 510(k)s",
                "description": "510(k) submission completeness criteria",
                "mandatory": True,
            },
            # Software
            {
                "id": "US-GUID-010",
                "title": "Software as Medical Device Guidance",
                "description": "FDA SaMD guidance",
                "mandatory": True,
            },
            {
                "id": "US-GUID-011",
                "title": "Clinical Decision Support Software",
                "description": "CDS exclusion criteria",
                "mandatory": True,
            },
            {
                "id": "US-GUID-012",
                "title": "General Wellness Policy",
                "description": "Low-risk device exclusions",
                "mandatory": True,
            },
            {
                "id": "US-GUID-013",
                "title": "Software Premarket Submissions",
                "description": "Documentation for software submissions",
                "mandatory": True,
            },
            {
                "id": "US-GUID-014",
                "title": "Cybersecurity Premarket Guidance",
                "description": "Cybersecurity requirements",
                "mandatory": True,
            },
            {
                "id": "US-GUID-015",
                "title": "Postmarket Cybersecurity Guidance",
                "description": "Postmarket cybersecurity management",
                "mandatory": True,
            },
            # Clinical
            {
                "id": "US-GUID-020",
                "title": "IDE Guidance",
                "description": "Investigational Device Exemption",
                "mandatory": True,
            },
            {
                "id": "US-GUID-021",
                "title": "Breakthrough Devices Guidance",
                "description": "Breakthrough Device Designation",
                "mandatory": True,
            },
            {
                "id": "US-GUID-022",
                "title": "De Novo Classification Guidance",
                "description": "De Novo pathway",
                "mandatory": True,
            },
            # Labeling
            {
                "id": "US-GUID-030",
                "title": "Medical Device Labeling Guidance",
                "description": "General labeling requirements",
                "mandatory": True,
            },
            {
                "id": "US-GUID-031",
                "title": "UDI Guidance",
                "description": "Unique Device Identifier requirements",
                "mandatory": True,
            },
            # Risk
            {
                "id": "US-GUID-040",
                "title": "Benefit-Risk Guidance",
                "description": "Benefit-risk assessment framework",
                "mandatory": True,
            },
            # Biocompatibility
            {
                "id": "US-GUID-050",
                "title": "Biocompatibility Guidance",
                "description": "Use of ISO 10993-1",
                "mandatory": True,
            },
            # Sterilization
            {
                "id": "US-GUID-060",
                "title": "Sterility Guidance",
                "description": "Submission documentation for sterility",
                "mandatory": True,
            },
            # Post-market
            {
                "id": "US-GUID-070",
                "title": "MDR Guidance",
                "description": "Medical Device Reporting requirements",
                "mandatory": True,
            },
            {
                "id": "US-GUID-071",
                "title": "Corrections and Removals Guidance",
                "description": "Recall procedures",
                "mandatory": True,
            },
        ],
    },
    # ===========================================
    # TIER 2: Other English-Speaking Jurisdictions
    # ===========================================
    "Canada": {
        "regulations": [
            {
                "id": "CA-REG-001",
                "title": "Medical Devices Regulations SOR/98-282",
                "description": "Canadian Medical Devices Regulations",
                "mandatory": True,
            },
            {
                "id": "CA-REG-002",
                "title": "Food and Drugs Act",
                "description": "Enabling legislation",
                "mandatory": True,
            },
        ],
        "guidance": [
            {
                "id": "CA-GUID-001",
                "title": "Medical Device Licence Applications",
                "description": "MDEL application guidance",
                "mandatory": True,
            },
            {
                "id": "CA-GUID-002",
                "title": "Classification Rules",
                "description": "Device classification guidance",
                "mandatory": True,
            },
            {
                "id": "CA-GUID-003",
                "title": "Clinical Evidence Requirements",
                "description": "Clinical evidence for submissions",
                "mandatory": True,
            },
            {
                "id": "CA-GUID-004",
                "title": "Software as Medical Device",
                "description": "SaMD guidance for Canada",
                "mandatory": True,
            },
            {
                "id": "CA-GUID-005",
                "title": "Problem Reporting",
                "description": "Mandatory problem reporting",
                "mandatory": True,
            },
            {
                "id": "CA-GUID-006",
                "title": "Recalls and Corrections",
                "description": "Recall procedures",
                "mandatory": True,
            },
        ],
    },
    "Australia": {
        "regulations": [
            {
                "id": "AU-REG-001",
                "title": "Therapeutic Goods Act 1989",
                "description": "Primary legislation",
                "mandatory": True,
            },
            {
                "id": "AU-REG-002",
                "title": "Therapeutic Goods (Medical Devices) Regulations 2002",
                "description": "Device-specific regulations",
                "mandatory": True,
            },
        ],
        "guidance": [
            {
                "id": "AU-GUID-001",
                "title": "Australian medical device regulation overview",
                "description": "TGA device regulation guidance",
                "mandatory": True,
            },
            {
                "id": "AU-GUID-002",
                "title": "Essential Principles checklist",
                "description": "Australian Essential Principles",
                "mandatory": True,
            },
            {
                "id": "AU-GUID-003",
                "title": "Clinical evidence guidelines",
                "description": "Clinical evidence requirements",
                "mandatory": True,
            },
            {
                "id": "AU-GUID-004",
                "title": "Software medical devices",
                "description": "SaMD guidance Australia",
                "mandatory": True,
            },
            {
                "id": "AU-GUID-005",
                "title": "Post-market requirements",
                "description": "Australian PMS/vigilance",
                "mandatory": True,
            },
            {
                "id": "AU-GUID-006",
                "title": "Conformity assessment procedures",
                "description": "CA body requirements",
                "mandatory": True,
            },
        ],
    },
    # ===========================================
    # TIER 3: International Harmonization
    # ===========================================
    "ISO": {
        "qms": [
            {
                "id": "ISO-QMS-001",
                "title": "ISO 13485:2016",
                "description": "Medical devices QMS",
                "mandatory": True,
            },
            {
                "id": "ISO-QMS-002",
                "title": "ISO 13485 Practical Guide",
                "description": "Implementation guidance",
                "mandatory": False,
            },
        ],
        "risk": [
            {
                "id": "ISO-RISK-001",
                "title": "ISO 14971:2019",
                "description": "Risk management",
                "mandatory": True,
            },
            {
                "id": "ISO-RISK-002",
                "title": "ISO/TR 24971:2020",
                "description": "Risk management guidance",
                "mandatory": True,
            },
        ],
        "clinical": [
            {
                "id": "ISO-CLIN-001",
                "title": "ISO 14155:2020",
                "description": "Clinical investigations",
                "mandatory": True,
            },
        ],
        "software": [
            {
                "id": "ISO-SW-001",
                "title": "IEC 62304:2006+A1:2015",
                "description": "Medical device software lifecycle",
                "mandatory": True,
            },
            {
                "id": "ISO-SW-002",
                "title": "IEC 82304-1:2016",
                "description": "Health software requirements",
                "mandatory": True,
            },
            {
                "id": "ISO-SW-003",
                "title": "IEC 62443 series",
                "description": "Cybersecurity standards",
                "mandatory": False,
            },
        ],
        "biocompatibility": [
            {
                "id": "ISO-BIO-001",
                "title": "ISO 10993-1:2018",
                "description": "Biological evaluation - guidance",
                "mandatory": True,
            },
            {
                "id": "ISO-BIO-002",
                "title": "ISO 10993-5",
                "description": "Cytotoxicity testing",
                "mandatory": True,
            },
            {
                "id": "ISO-BIO-003",
                "title": "ISO 10993-10",
                "description": "Sensitization testing",
                "mandatory": True,
            },
            {
                "id": "ISO-BIO-004",
                "title": "ISO 10993-11",
                "description": "Systemic toxicity testing",
                "mandatory": True,
            },
            {
                "id": "ISO-BIO-005",
                "title": "ISO 10993-18",
                "description": "Chemical characterization",
                "mandatory": True,
            },
            {
                "id": "ISO-BIO-006",
                "title": "ISO/TS 10993-19",
                "description": "Material characterization",
                "mandatory": False,
            },
            {
                "id": "ISO-BIO-007",
                "title": "ISO/TS 10993-20",
                "description": "Immunotoxicity testing",
                "mandatory": False,
            },
        ],
        "sterilization": [
            {
                "id": "ISO-STER-001",
                "title": "ISO 11135",
                "description": "EO sterilization",
                "mandatory": False,
            },
            {
                "id": "ISO-STER-002",
                "title": "ISO 11137 series",
                "description": "Radiation sterilization",
                "mandatory": False,
            },
            {
                "id": "ISO-STER-003",
                "title": "ISO 17665-1",
                "description": "Moist heat sterilization",
                "mandatory": False,
            },
            {
                "id": "ISO-STER-004",
                "title": "ISO 11607-1",
                "description": "Sterile barrier packaging",
                "mandatory": False,
            },
        ],
        "usability": [
            {
                "id": "ISO-USE-001",
                "title": "IEC 62366-1:2015",
                "description": "Usability engineering",
                "mandatory": True,
            },
            {
                "id": "ISO-USE-002",
                "title": "IEC/TR 62366-2",
                "description": "Usability guidance",
                "mandatory": False,
            },
        ],
        "electrical": [
            {
                "id": "ISO-ELEC-001",
                "title": "IEC 60601-1",
                "description": "General safety and essential performance",
                "mandatory": True,
            },
            {
                "id": "ISO-ELEC-002",
                "title": "IEC 60601-1-2",
                "description": "EMC requirements",
                "mandatory": True,
            },
            {
                "id": "ISO-ELEC-003",
                "title": "IEC 60601-1-6",
                "description": "Usability",
                "mandatory": True,
            },
            {
                "id": "ISO-ELEC-004",
                "title": "IEC 60601-1-11",
                "description": "Home healthcare environment",
                "mandatory": False,
            },
        ],
        "labeling": [
            {
                "id": "ISO-LAB-001",
                "title": "ISO 15223-1",
                "description": "Symbols for labeling",
                "mandatory": True,
            },
            {
                "id": "ISO-LAB-002",
                "title": "IEC 60417",
                "description": "Graphical symbols",
                "mandatory": True,
            },
        ],
        "other": [
            {
                "id": "ISO-OTH-001",
                "title": "ISO 11070",
                "description": "Intravascular catheters",
                "mandatory": False,
            },
            {
                "id": "ISO-OTH-002",
                "title": "ISO 18562 series",
                "description": "Biocompatibility of breathing gas pathways",
                "mandatory": False,
            },
            {
                "id": "ISO-OTH-003",
                "title": "ISO 80369 series",
                "description": "Small-bore connectors",
                "mandatory": False,
            },
        ],
    },
    "IMDRF": {
        "guidance": [
            {
                "id": "IMDRF-001",
                "title": "IMDRF SaMD Framework",
                "description": "Software as Medical Device classification",
                "mandatory": True,
            },
            {
                "id": "IMDRF-002",
                "title": "IMDRF SaMD Clinical Evaluation",
                "description": "Clinical evidence for SaMD",
                "mandatory": True,
            },
            {
                "id": "IMDRF-003",
                "title": "IMDRF SaMD Risk Categorization",
                "description": "SaMD risk framework",
                "mandatory": True,
            },
            {
                "id": "IMDRF-004",
                "title": "IMDRF NCAR Exchange",
                "description": "Regulatory authority collaboration",
                "mandatory": False,
            },
            {
                "id": "IMDRF-005",
                "title": "IMDRF Adverse Event Terminology",
                "description": "Standardized AE coding",
                "mandatory": True,
            },
            {
                "id": "IMDRF-006",
                "title": "IMDRF UDI Guidance",
                "description": "Global UDI framework",
                "mandatory": True,
            },
            {
                "id": "IMDRF-007",
                "title": "IMDRF MDSAP",
                "description": "Single Audit Program requirements",
                "mandatory": True,
            },
            {
                "id": "IMDRF-008",
                "title": "IMDRF Cybersecurity Principles",
                "description": "Global cybersecurity guidance",
                "mandatory": True,
            },
        ],
    },
    "MDSAP": {
        "guidance": [
            {
                "id": "MDSAP-001",
                "title": "MDSAP Audit Model",
                "description": "Core audit approach",
                "mandatory": True,
            },
            {
                "id": "MDSAP-002",
                "title": "MDSAP QMS Companion",
                "description": "QMS requirements by jurisdiction",
                "mandatory": True,
            },
            {
                "id": "MDSAP-003",
                "title": "MDSAP Grading System",
                "description": "Nonconformity grading",
                "mandatory": True,
            },
            {
                "id": "MDSAP-004",
                "title": "MDSAP AU P0002",
                "description": "Australia audit approach",
                "mandatory": True,
            },
            {
                "id": "MDSAP-005",
                "title": "MDSAP BR P0002",
                "description": "Brazil audit approach",
                "mandatory": False,
            },
            {
                "id": "MDSAP-006",
                "title": "MDSAP CA P0002",
                "description": "Canada audit approach",
                "mandatory": True,
            },
            {
                "id": "MDSAP-007",
                "title": "MDSAP JP P0002",
                "description": "Japan audit approach",
                "mandatory": False,
            },
            {
                "id": "MDSAP-008",
                "title": "MDSAP US P0002",
                "description": "US audit approach",
                "mandatory": True,
            },
        ],
    },
}


def get_all_reference_docs():
    """Flatten all reference documents into a single list with jurisdiction info."""
    all_docs = []
    for jurisdiction, categories in REFERENCE_DOCUMENTS.items():
        for category, docs in categories.items():
            for doc in docs:
                doc_entry = doc.copy()
                doc_entry["jurisdiction"] = jurisdiction
                doc_entry["category"] = category
                all_docs.append(doc_entry)
    return all_docs


def get_mandatory_docs():
    """Get only mandatory documents."""
    return [d for d in get_all_reference_docs() if d.get("mandatory", False)]


def get_docs_by_jurisdiction(jurisdiction):
    """Get all reference docs for a specific jurisdiction."""
    return [d for d in get_all_reference_docs() if d["jurisdiction"] == jurisdiction]
