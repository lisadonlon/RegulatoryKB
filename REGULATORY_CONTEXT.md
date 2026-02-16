# Regulatory Context - User Requirements

## Domain Focus: Medical Devices

This knowledge base and intelligence system is focused on **medical device regulation**, not pharmaceuticals or biologics.

### Primary Regulatory Interests

**Device Regulations:**
- EU MDR (Medical Device Regulation)
- EU IVDR (In Vitro Diagnostic Regulation)
- FDA medical device regulations (510(k), PMA, De Novo)
- UK MDR/IVDR equivalents

**Device Categories:**
- Software as a Medical Device (SaMD)
- In Vitro Diagnostics (IVD)
- Active Implantable Medical Devices (AIMDs)
- Digital health technologies
- AI/ML-enabled medical devices

**Standards of Interest:**
- ISO 13485 (Quality Management Systems)
- ISO 14971 (Risk Management)
- IEC 62304 (Software Lifecycle)
- IEC 60601-1 (Electrical Safety)
- Cybersecurity standards

**Key Regulatory Bodies (Device-focused):**
- FDA (device division)
- EU Notified Bodies
- MHRA (UK)
- TGA (Australia)
- Health Canada (device division)
- Swissmedic (device division)
- NMPA (China)
- HSA Singapore

### Explicitly Excluded Content

The following are **pharmaceutical/biologics** focused and should be filtered out:

**Agencies to Exclude:**
- EMA (European Medicines Agency) - primarily pharma
- ICH (International Council for Harmonisation) - pharma harmonization
- EDQM - pharmaceutical quality
- Medsafe (NZ) - primarily medicines

**Keywords to Exclude:**
- Drug, pharmaceutical, medicine(s), medicinal product
- Clinical trial (pharma context)
- Biologics, biosimilar, vaccine
- Gene therapy
- Active substance, excipient
- GMP (pharma context)
- Pharmacovigilance
- eCTD, CTD (pharma submissions)
- CEP (Certificate of Suitability)

### Exception: Combination Products

Drug-device combination products ARE relevant:
- Prefilled syringes
- Drug-eluting devices
- Delivery devices
- Integral combination products

These should be included even if they mention pharmaceutical terms.

### Intelligence Filtering Logic

1. **Include** if entry has strong device indicators (medical device, IVD, SaMD, 510(k), MDR, IVDR, CE mark)
2. **Exclude** if entry has multiple pharma keywords (2+)
3. **Exclude** if entry is from pharma-focused agencies (EMA, ICH)
4. **Include** combination products even with pharma keywords

### Data Sources

- Index-of-Indexes newsletter (primary source)
- Regulatory agency websites
- Standards bodies (ISO, IEC)

---
*Last updated: January 2026*
