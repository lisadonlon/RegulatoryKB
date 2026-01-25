"""
Acquisition list for missing regulatory documents with official source URLs.
Organized by priority: EU, UK, US, then other jurisdictions.
"""

ACQUISITION_LIST = {
    # ===========================================
    # TIER 1: EU
    # ===========================================
    "EU": {
        "regulations": [
            {
                "title": "MDR 2017/745",
                "description": "Medical Device Regulation (consolidated version)",
                "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:02017R0745-20230320",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "IVDR 2017/746",
                "description": "In Vitro Diagnostic Regulation (consolidated)",
                "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:02017R0746-20230320",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDD 93/42/EEC",
                "description": "Medical Device Directive (legacy, for reference)",
                "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:01993L0042-20071011",
                "mandatory": False,
                "free": True,
            },
            {
                "title": "AIMDD 90/385/EEC",
                "description": "Active Implantable Medical Device Directive (legacy)",
                "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:01990L0385-20071011",
                "mandatory": False,
                "free": True,
            },
        ],
        "mdcg_guidance": [
            # Classification & Qualification
            {
                "title": "MDCG 2022-5",
                "description": "Guidance on borderline between medical devices and other products",
                "url": "https://health.ec.europa.eu/document/download/57536af8-4904-40c9-8de5-b65e67bdc5bc_en",
                "mandatory": True,
                "free": True,
            },
            # Clinical Evaluation
            {
                "title": "MDCG 2020-13",
                "description": "Clinical evaluation assessment report template",
                "url": "https://health.ec.europa.eu/document/download/0ef76005-1dd5-4b74-a892-f96699c2eb38_en",
                "mandatory": True,
                "free": True,
            },
            # Post-Market Surveillance
            {
                "title": "MDCG 2020-7",
                "description": "Post-market surveillance plan template",
                "url": "https://health.ec.europa.eu/document/download/dc2bdabd-d15c-4c80-b4c6-43e5a60b0678_en",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDCG 2020-8",
                "description": "PMCF plan and evaluation report templates",
                "url": "https://health.ec.europa.eu/document/download/8cf39ecd-9376-4324-a988-fc15054ddb4b_en",
                "mandatory": True,
                "free": True,
            },
            # Technical Documentation
            {
                "title": "MDCG 2019-9 rev 1",
                "description": "Summary of Safety and Clinical Performance",
                "url": "https://health.ec.europa.eu/document/download/f2d1e6e7-fcd3-4f14-ab06-25bdfdbd3de2_en",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDCG 2022-14",
                "description": "GSPR mapping guidance",
                "url": "https://health.ec.europa.eu/document/download/a044c1a5-55a3-4ad4-8b94-319c68a5ef8b_en",
                "mandatory": True,
                "free": True,
            },
            # UDI & EUDAMED
            {
                "title": "MDCG 2018-1 rev 3",
                "description": "Guidance on UDI for devices under IVDR and MDR",
                "url": "https://health.ec.europa.eu/document/download/53f53a5e-9cb6-4e8f-8f08-38b5c01e3954_en",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDCG 2021-13",
                "description": "Q&A on registration of legacy devices in EUDAMED",
                "url": "https://health.ec.europa.eu/document/download/a1de35d3-d289-4b6c-9ceb-d3a8c1ff4db8_en",
                "mandatory": True,
                "free": True,
            },
            # Cybersecurity
            {
                "title": "MDCG 2019-16 rev 1",
                "description": "Guidance on cybersecurity for medical devices",
                "url": "https://health.ec.europa.eu/document/download/f3159ee3-94b3-4cf3-9f15-67e6a0b95c27_en",
                "mandatory": True,
                "free": True,
            },
            # Significant Changes
            {
                "title": "MDCG 2020-3 rev 1",
                "description": "Guidance on significant changes",
                "url": "https://health.ec.europa.eu/document/download/c5e69f14-f003-4b91-9a3c-3f2f33dafc1f_en",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDCG 2022-4",
                "description": "Guidance on appropriate surveillance regarding significant changes",
                "url": "https://health.ec.europa.eu/document/download/0f812def-39e0-4fa0-afd6-61fed80a8c98_en",
                "mandatory": True,
                "free": True,
            },
            # Labelling
            {
                "title": "MDCG 2019-7",
                "description": "Guidance on Article 10(11) - languages for IFU",
                "url": "https://health.ec.europa.eu/document/download/9d00fc95-7dcc-4e45-9a89-5e06a7be7c01_en",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDCG 2021-21 rev 1",
                "description": "Guidance on electronic instructions for use (eIFU)",
                "url": "https://health.ec.europa.eu/document/download/9c4e7e9d-f5d0-4c06-9cfd-de7c2a1d3b67_en",
                "mandatory": True,
                "free": True,
            },
            # Transition
            {
                "title": "MDCG 2024-2",
                "description": "Extended transition timelines guidance",
                "url": "https://health.ec.europa.eu/document/download/1d8f05b2-b7e8-4b89-a7b3-4e06df2b5ef2_en",
                "mandatory": True,
                "free": True,
            },
        ],
        "other_guidance": [
            {
                "title": "Blue Guide 2022",
                "description": "The 'Blue Guide' on the implementation of EU product rules",
                "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:52022XC0629(04)",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MEDDEV 2.7/1 rev 4",
                "description": "Clinical evaluation guidance (legacy but still referenced)",
                "url": "https://ec.europa.eu/docsroom/documents/17522/attachments/1/translations/en/renditions/native",
                "mandatory": False,
                "free": True,
            },
        ],
    },

    # ===========================================
    # TIER 1: UK
    # ===========================================
    "UK": {
        "regulations": [
            {
                "title": "UK MDR 2002 (as amended 2024)",
                "description": "The Medical Devices Regulations 2002 (consolidated)",
                "url": "https://www.legislation.gov.uk/uksi/2002/618/pdfs/uksi_20020618_en.pdf",
                "mandatory": True,
                "free": True,
            },
        ],
        "guidance": [
            {
                "title": "Regulating medical devices in the UK",
                "description": "MHRA core guidance for medical device regulation",
                "url": "https://www.gov.uk/guidance/regulating-medical-devices-in-the-uk",
                "mandatory": True,
                "free": True,
                "note": "Web page - multiple PDFs available from this link",
            },
            {
                "title": "Software and AI as a Medical Device",
                "description": "MHRA guidance on software qualification and classification",
                "url": "https://www.gov.uk/government/publications/software-and-artificial-intelligence-ai-as-a-medical-device/software-and-ai-as-a-medical-device",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Clinical investigations guidance",
                "description": "MHRA guidance on clinical investigations for medical devices",
                "url": "https://www.gov.uk/guidance/clinical-investigations-for-medical-devices",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Post-market surveillance for medical devices",
                "description": "MHRA requirements for PMS",
                "url": "https://www.gov.uk/guidance/post-market-surveillance-of-medical-devices",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Report a problem with a medicine or medical device",
                "description": "Yellow Card reporting requirements",
                "url": "https://www.gov.uk/guidance/report-a-problem-with-a-medicine-or-medical-device",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Using the UKCA marking",
                "description": "UKCA requirements for medical devices",
                "url": "https://www.gov.uk/guidance/using-the-ukca-marking",
                "mandatory": True,
                "free": True,
            },
        ],
    },

    # ===========================================
    # TIER 1: US (FDA)
    # ===========================================
    "US": {
        "regulations": [
            {
                "title": "21 CFR Part 820",
                "description": "Quality System Regulation",
                "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-820",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "21 CFR Part 803",
                "description": "Medical Device Reporting",
                "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-803",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "21 CFR Part 806",
                "description": "Medical Device Corrections and Removals",
                "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-806",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "21 CFR Part 807",
                "description": "Establishment Registration and Device Listing",
                "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "21 CFR Part 812",
                "description": "Investigational Device Exemptions",
                "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-812",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "21 CFR Part 814",
                "description": "Premarket Approval of Medical Devices",
                "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-814",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "21 CFR Part 830",
                "description": "Unique Device Identification",
                "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-830",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "21 CFR Part 860",
                "description": "Medical Device Classification Procedures",
                "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-860",
                "mandatory": True,
                "free": True,
            },
        ],
        "guidance": [
            # 510(k) Guidance
            {
                "title": "The 510(k) Program: Evaluating Substantial Equivalence",
                "description": "Core 510(k) guidance document",
                "url": "https://www.fda.gov/media/82395/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "The Abbreviated 510(k) Program",
                "description": "Abbreviated 510(k) pathway guidance",
                "url": "https://www.fda.gov/media/72647/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "The Special 510(k) Program",
                "description": "Special 510(k) for design control changes",
                "url": "https://www.fda.gov/media/116418/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Refuse to Accept Policy for 510(k)s",
                "description": "510(k) submission completeness checklist",
                "url": "https://www.fda.gov/media/83888/download",
                "mandatory": True,
                "free": True,
            },
            # Software Guidance
            {
                "title": "Policy for Device Software Functions (SaMD)",
                "description": "FDA policy on software as medical device",
                "url": "https://www.fda.gov/media/119722/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Clinical Decision Support Software",
                "description": "CDS guidance and exclusion criteria",
                "url": "https://www.fda.gov/media/109618/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "General Wellness: Policy for Low Risk Devices",
                "description": "General wellness device exclusions",
                "url": "https://www.fda.gov/media/90652/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Content of Premarket Submissions for Device Software Functions",
                "description": "Software documentation requirements",
                "url": "https://www.fda.gov/media/153781/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Cybersecurity in Medical Devices: Premarket Submissions",
                "description": "Premarket cybersecurity guidance (2023)",
                "url": "https://www.fda.gov/media/166772/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Postmarket Management of Cybersecurity in Medical Devices",
                "description": "Postmarket cybersecurity guidance",
                "url": "https://www.fda.gov/media/95862/download",
                "mandatory": True,
                "free": True,
            },
            # Clinical Guidance
            {
                "title": "IDE Applications for Early Feasibility Studies",
                "description": "Early feasibility IDE guidance",
                "url": "https://www.fda.gov/media/81784/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Breakthrough Devices Program",
                "description": "Breakthrough device designation guidance",
                "url": "https://www.fda.gov/media/108135/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "De Novo Classification Process",
                "description": "De Novo pathway guidance",
                "url": "https://www.fda.gov/media/72674/download",
                "mandatory": True,
                "free": True,
            },
            # Labeling & UDI
            {
                "title": "Device Labeling Guidance",
                "description": "General labeling requirements 21 CFR 801",
                "url": "https://www.fda.gov/media/72025/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "UDI System: Final Rule FAQ",
                "description": "UDI implementation guidance",
                "url": "https://www.fda.gov/media/87546/download",
                "mandatory": True,
                "free": True,
            },
            # Risk & Safety
            {
                "title": "Benefit-Risk Guidance for Premarket Approval",
                "description": "Benefit-risk framework",
                "url": "https://www.fda.gov/media/99769/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Use of ISO 10993-1 Biocompatibility Guidance",
                "description": "Biocompatibility evaluation guidance",
                "url": "https://www.fda.gov/media/85865/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Submission and Review of Sterility Information",
                "description": "Sterility documentation guidance",
                "url": "https://www.fda.gov/media/74445/download",
                "mandatory": True,
                "free": True,
            },
            # Post-market
            {
                "title": "Medical Device Reporting for Manufacturers",
                "description": "MDR requirements guidance",
                "url": "https://www.fda.gov/media/86420/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Medical Device Corrections and Removals",
                "description": "Recall guidance",
                "url": "https://www.fda.gov/media/72035/download",
                "mandatory": True,
                "free": True,
            },
        ],
    },

    # ===========================================
    # TIER 2: Canada
    # ===========================================
    "Canada": {
        "regulations": [
            {
                "title": "Medical Devices Regulations SOR/98-282",
                "description": "Canadian Medical Devices Regulations",
                "url": "https://laws-lois.justice.gc.ca/PDF/SOR-98-282.pdf",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Food and Drugs Act",
                "description": "Enabling legislation for medical devices",
                "url": "https://laws-lois.justice.gc.ca/PDF/F-27.pdf",
                "mandatory": True,
                "free": True,
            },
        ],
        "guidance": [
            {
                "title": "Medical Device Licence Application Guide",
                "description": "How to apply for an MDL",
                "url": "https://www.canada.ca/en/health-canada/services/drugs-health-products/medical-devices/application-information/guidance-documents/guidance-document-medical-device-licence-application.html",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Classification of Medical Devices",
                "description": "Device classification guidance",
                "url": "https://www.canada.ca/en/health-canada/services/drugs-health-products/medical-devices/application-information/guidance-documents/guidance-classification-medical-devices.html",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Software as a Medical Device (SaMD)",
                "description": "SaMD classification and requirements",
                "url": "https://www.canada.ca/en/health-canada/services/drugs-health-products/medical-devices/application-information/guidance-documents/software-medical-device-guidance.html",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Mandatory Problem Reporting",
                "description": "Adverse event reporting requirements",
                "url": "https://www.canada.ca/en/health-canada/services/drugs-health-products/medical-devices/reports-publications/regulations-guidance/mandatory-problem-reporting-medical-devices.html",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Medical Device Recalls",
                "description": "Recall requirements",
                "url": "https://www.canada.ca/en/health-canada/services/drugs-health-products/compliance-enforcement/information-health-product/medical-devices/medical-device-recall-guidance.html",
                "mandatory": True,
                "free": True,
            },
        ],
    },

    # ===========================================
    # TIER 2: Australia
    # ===========================================
    "Australia": {
        "regulations": [
            {
                "title": "Therapeutic Goods Act 1989",
                "description": "Primary legislation for therapeutic goods",
                "url": "https://www.legislation.gov.au/Details/C2024C00166",
                "mandatory": True,
                "free": True,
                "note": "Link to legislation.gov.au - select PDF download",
            },
            {
                "title": "Therapeutic Goods (Medical Devices) Regulations 2002",
                "description": "Medical device specific regulations",
                "url": "https://www.legislation.gov.au/Details/F2023C00959",
                "mandatory": True,
                "free": True,
            },
        ],
        "guidance": [
            {
                "title": "Australian regulatory guidelines for medical devices (ARGMD)",
                "description": "Core TGA guidance for medical devices",
                "url": "https://www.tga.gov.au/how-we-regulate/manufacturing/manufacture-medical-device/australian-regulatory-guidelines-medical-devices",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Essential Principles Checklist",
                "description": "Australian Essential Principles compliance",
                "url": "https://www.tga.gov.au/resources/resource/forms/conformity-assessment-medical-device-application-forms",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Clinical evidence guidelines for medical devices",
                "description": "Clinical evidence requirements",
                "url": "https://www.tga.gov.au/resources/resource/guidance/clinical-evidence-guidelines-medical-devices",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Software as a medical device",
                "description": "TGA SaMD guidance",
                "url": "https://www.tga.gov.au/resources/resource/guidance/software-based-medical-devices",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "Post-market requirements",
                "description": "Australian PMS and vigilance",
                "url": "https://www.tga.gov.au/how-we-regulate/monitoring-and-post-market-management/medical-devices",
                "mandatory": True,
                "free": True,
            },
        ],
    },

    # ===========================================
    # INTERNATIONAL: ISO Standards
    # ===========================================
    "ISO": {
        "note": "ISO standards require purchase from ISO, national standards bodies (BSI, ANSI, SAI), or may be available through subscription services. Some are available through NSAI (Ireland) or academic access.",
        "standards": [
            {
                "title": "ISO 14971:2019",
                "description": "Risk management for medical devices",
                "url": "https://www.iso.org/standard/72704.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 187",
            },
            {
                "title": "ISO/TR 24971:2020",
                "description": "Risk management guidance (application of ISO 14971)",
                "url": "https://www.iso.org/standard/74437.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 187",
            },
            {
                "title": "IEC 62304:2006+A1:2015",
                "description": "Medical device software lifecycle processes",
                "url": "https://www.iso.org/standard/64686.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 250",
            },
            {
                "title": "IEC 82304-1:2016",
                "description": "Health software - General requirements for product safety",
                "url": "https://www.iso.org/standard/59543.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 118",
            },
            {
                "title": "IEC 62366-1:2015+A1:2020",
                "description": "Usability engineering - Application to medical devices",
                "url": "https://www.iso.org/standard/77436.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 200",
            },
            {
                "title": "IEC 60601-1:2005+A1:2012+A2:2020",
                "description": "Medical electrical equipment - General requirements",
                "url": "https://www.iso.org/standard/72411.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 444",
            },
            {
                "title": "IEC 60601-1-2:2014+A1:2020",
                "description": "Medical electrical equipment - EMC requirements",
                "url": "https://www.iso.org/standard/79570.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 348",
            },
            {
                "title": "ISO 15223-1:2021",
                "description": "Symbols to be used with information supplied by manufacturer",
                "url": "https://www.iso.org/standard/77326.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 187",
            },
            {
                "title": "IEC 60417 (database)",
                "description": "Graphical symbols for use on equipment",
                "url": "https://www.iso.org/standard/77325.html",
                "mandatory": True,
                "free": False,
                "price_approx": "Subscription",
            },
            {
                "title": "ISO 10993-5:2009",
                "description": "Biological evaluation - Tests for in vitro cytotoxicity",
                "url": "https://www.iso.org/standard/36406.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 118",
            },
            {
                "title": "ISO 10993-10:2021",
                "description": "Biological evaluation - Skin sensitization",
                "url": "https://www.iso.org/standard/75279.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 167",
            },
            {
                "title": "ISO 10993-11:2017",
                "description": "Biological evaluation - Systemic toxicity",
                "url": "https://www.iso.org/standard/68426.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 167",
            },
            {
                "title": "ISO 10993-18:2020",
                "description": "Biological evaluation - Chemical characterization",
                "url": "https://www.iso.org/standard/64750.html",
                "mandatory": True,
                "free": False,
                "price_approx": "CHF 200",
            },
            {
                "title": "ISO 11135:2014",
                "description": "Sterilization - Ethylene oxide",
                "url": "https://www.iso.org/standard/56137.html",
                "mandatory": False,
                "free": False,
                "price_approx": "CHF 167",
            },
            {
                "title": "ISO 11137-1:2006",
                "description": "Sterilization - Radiation - Part 1: Requirements",
                "url": "https://www.iso.org/standard/33952.html",
                "mandatory": False,
                "free": False,
                "price_approx": "CHF 138",
            },
            {
                "title": "ISO 11607-1:2019",
                "description": "Packaging for terminally sterilized devices",
                "url": "https://www.iso.org/standard/70799.html",
                "mandatory": False,
                "free": False,
                "price_approx": "CHF 138",
            },
        ],
    },

    # ===========================================
    # INTERNATIONAL: IMDRF
    # ===========================================
    "IMDRF": {
        "guidance": [
            {
                "title": "IMDRF SaMD: Key Definitions",
                "description": "Software as Medical Device - framework definitions",
                "url": "https://www.imdrf.org/sites/default/files/docs/imdrf/final/technical/imdrf-tech-131209-samd-key-definitions-140901.pdf",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "IMDRF SaMD: Risk Categorization Framework",
                "description": "SaMD risk classification",
                "url": "https://www.imdrf.org/sites/default/files/docs/imdrf/final/technical/imdrf-tech-140918-samd-framework-risk-categorization-141013.pdf",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "IMDRF SaMD: Clinical Evaluation",
                "description": "Clinical evaluation of SaMD",
                "url": "https://www.imdrf.org/sites/default/files/docs/imdrf/final/technical/imdrf-tech-170921-samd-n41-clinical-evaluation_1.pdf",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "IMDRF Adverse Event Terminology",
                "description": "Standardized terminology for adverse events",
                "url": "https://www.imdrf.org/sites/default/files/docs/imdrf/final/technical/imdrf-tech-200318-ae-terminology-n43.pdf",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "IMDRF UDI Guidance",
                "description": "Unique Device Identification global framework",
                "url": "https://www.imdrf.org/sites/default/files/docs/imdrf/final/technical/imdrf-tech-190321-udi-application-guide.pdf",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "IMDRF Principles of Cybersecurity",
                "description": "Cybersecurity principles for medical devices",
                "url": "https://www.imdrf.org/sites/default/files/docs/imdrf/final/technical/imdrf-tech-200318-pp-mdc-n60.pdf",
                "mandatory": True,
                "free": True,
            },
        ],
    },

    # ===========================================
    # INTERNATIONAL: MDSAP
    # ===========================================
    "MDSAP": {
        "guidance": [
            {
                "title": "MDSAP Audit Model",
                "description": "Core MDSAP audit approach",
                "url": "https://www.fda.gov/media/107631/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDSAP QMS Companion Document",
                "description": "QMS requirements by jurisdiction",
                "url": "https://www.fda.gov/media/107633/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDSAP Nonconformity Grading System",
                "description": "How nonconformities are graded",
                "url": "https://www.fda.gov/media/107635/download",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDSAP AU P0002 - Australia Audit Approach",
                "description": "Australian regulatory requirements",
                "url": "https://www.tga.gov.au/sites/default/files/mdsap-au-p0002.pdf",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDSAP CA P0002 - Canada Audit Approach",
                "description": "Canadian regulatory requirements",
                "url": "https://www.canada.ca/content/dam/hc-sc/documents/services/drugs-health-products/compliance-enforcement/international-activities/ca-p0002.pdf",
                "mandatory": True,
                "free": True,
            },
            {
                "title": "MDSAP US P0002 - US Audit Approach",
                "description": "US FDA regulatory requirements",
                "url": "https://www.fda.gov/media/107634/download",
                "mandatory": True,
                "free": True,
            },
        ],
    },
}


def get_acquisition_list_flat():
    """Return flattened list of all documents to acquire."""
    flat_list = []
    for jurisdiction, categories in ACQUISITION_LIST.items():
        if jurisdiction == "note":
            continue
        for category, docs in categories.items():
            if category == "note":
                continue
            for doc in docs:
                entry = doc.copy()
                entry["jurisdiction"] = jurisdiction
                entry["category"] = category
                flat_list.append(entry)
    return flat_list


def get_mandatory_acquisitions():
    """Return only mandatory documents."""
    return [d for d in get_acquisition_list_flat() if d.get("mandatory", False)]


def get_free_acquisitions():
    """Return only free documents."""
    return [d for d in get_acquisition_list_flat() if d.get("free", True)]


def print_acquisition_list(mandatory_only=False, free_only=False):
    """Print formatted acquisition list."""
    docs = get_acquisition_list_flat()

    if mandatory_only:
        docs = [d for d in docs if d.get("mandatory", False)]
    if free_only:
        docs = [d for d in docs if d.get("free", True)]

    current_jur = None
    for doc in docs:
        if doc["jurisdiction"] != current_jur:
            current_jur = doc["jurisdiction"]
            print(f"\n{'='*60}")
            print(f"  {current_jur}")
            print(f"{'='*60}")

        mandatory = "[MANDATORY]" if doc.get("mandatory") else ""
        free = "[FREE]" if doc.get("free", True) else f"[~{doc.get('price_approx', 'PAID')}]"

        print(f"\n  {doc['title']} {mandatory} {free}")
        print(f"  {doc['description']}")
        print(f"  URL: {doc['url']}")


def export_acquisition_csv(output_path: str, mandatory_only=False, free_only=False):
    """Export acquisition list to CSV."""
    import csv

    docs = get_acquisition_list_flat()
    if mandatory_only:
        docs = [d for d in docs if d.get("mandatory", False)]
    if free_only:
        docs = [d for d in docs if d.get("free", True)]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Jurisdiction', 'Category', 'Title', 'Description', 'URL', 'Mandatory', 'Free', 'Notes'])

        for doc in docs:
            writer.writerow([
                doc['jurisdiction'],
                doc['category'],
                doc['title'],
                doc['description'],
                doc['url'],
                'Yes' if doc.get('mandatory') else 'No',
                'Yes' if doc.get('free', True) else 'No',
                doc.get('note', doc.get('price_approx', ''))
            ])
