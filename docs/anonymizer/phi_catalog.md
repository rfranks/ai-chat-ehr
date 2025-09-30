# PHI Catalog

This catalog summarizes the Protected Health Information (PHI) elements tracked by the anonymizer service, the detection techniques used for each element, guidance on how the detected values are replaced, and references to the underlying regulatory requirements. It follows the HIPAA Privacy Rule "Safe Harbor" list of 18 identifiers that must be removed to consider data de-identified.

## Detection and Replacement Strategy by PHI Element

| PHI Element | Detection Approach | Replacement Rule | Regulatory Reference |
|-------------|-------------------|------------------|----------------------|
| Personal names | [Presidio `PersonNameRecognizer`](https://microsoft.github.io/presidio/analyzer/predefined_recognizers/#person-names) with contextual confidence scoring. | Replace with the placeholder `[NAME]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(A). |
| Geographic subdivisions smaller than a state (street address, city, county, precinct, ZIP codes except initial three digits when population >20,000) | Combination of Presidio `LocationRecognizer`, curated lookup tables for U.S. cities/counties, and regular expressions for ZIP code formats. | Replace with `[LOCATION]`. If the ZIP code cannot be generalized to the first three digits, redact entirely. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(B)-(C). |
| All elements of dates (except year) directly related to an individual, including birth, admission, discharge, death, and exact age over 89 | Presidio `DateRecognizer` augmented with custom regex for clinical date formats (e.g., `MM/DD/YYYY`, `YYYY-MM-DD`, textual months). | Replace with `[DATE]`. Ages over 89 are replaced with `90+`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(C)-(D). |
| Telephone numbers | Presidio `PhoneRecognizer` supplemented by regex for international formats. | Replace with `[PHONE]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(E). |
| Fax numbers | Regex patterns derived from ITU-T E.123 formats and context keywords ("fax"). | Replace with `[FAX]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(E). |
| Email addresses | Presidio `EmailRecognizer`. | Replace with `[EMAIL]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(F). |
| Social Security Numbers | Presidio `UsSsnRecognizer` and strict regex (`XXX-XX-XXXX` variants). | Replace with `[SSN]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(G). |
| Medical record numbers | Custom regex for common MRN formats coupled with keyword proximity ("MRN", "Med Rec"). | Replace with `[MRN]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(H). |
| Health plan beneficiary numbers | Presidio `UsBankRecognizer` and custom dictionaries of insurer prefixes, validated by context words ("member ID", "subscriber"). | Replace with `[PLAN_ID]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(H). |
| Account numbers | Presidio `UsBankRecognizer` and numeric pattern heuristics. | Replace with `[ACCOUNT]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(H). |
| Certificate/license numbers | Regex patterns for professional licenses (e.g., state RN, DEA) and keyword context ("license", "cert"). | Replace with `[LICENSE]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(I). |
| Vehicle identifiers and license plates | Lookup tables for vehicle makes/models plus regex for plate formats by state. | Replace with `[VEHICLE]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(J). |
| Device identifiers and serial numbers | Presidio `ImeiRecognizer`, custom regex for medical device serial patterns, and context keywords ("serial", "device"). | Replace with `[DEVICE]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(K). |
| Web URLs | Presidio `UrlRecognizer`. | Replace with `[URL]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(L). |
| IP addresses | Presidio `IpRecognizer` for IPv4/IPv6. | Replace with `[IP]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(L). |
| Biometric identifiers (including finger and voice prints) | Keyword triggers ("fingerprint", "voiceprint"), mention detection via clinical terminologies, and manual tagging workflows. | Replace with `[BIOMETRIC]`. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(M). |
| Full-face photographs and comparable images | Detection via metadata tags (DICOM headers) and image processing pipeline flags external to text anonymization. In textual contexts, keywords like "photo attached" trigger redaction. | Replace with `[IMAGE]` or remove embedded image content. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(N). |
| Any other unique identifying number, characteristic, or code | Presidio custom recognizers tuned to project-specific identifiers (e.g., study IDs), regular expressions, and lookup tables. | Replace with `[ID]` or project-specific placeholder. | HIPAA Privacy Rule, 45 CFR §164.514(b)(2)(i)(O)-(P). |

## Additional Guidance

* When multiple PHI elements co-occur (e.g., name and date of birth), each element is redacted independently to ensure compliance with the Safe Harbor standard.
* Custom recognizers can be added for institution-specific identifiers following [Microsoft Presidio's extensibility guidelines](https://microsoft.github.io/presidio/analyzer/custom_recognizers/).
* The anonymizer aligns with the [U.S. Department of Health & Human Services (HHS) de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/privacy/special-topics/de-identification/index.html), with operational controls documented in the anonymizer architecture.

## References

1. U.S. Department of Health & Human Services. *Guidance Regarding Methods for De-identification of Protected Health Information in Accordance with the Health Insurance Portability and Accountability Act (HIPAA) Privacy Rule*. Available at: <https://www.hhs.gov/hipaa/for-professionals/privacy/special-topics/de-identification/index.html>.
2. 45 C.F.R. §164.514(b)(2) – Safe Harbor method for de-identification. Available at: <https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-E/section-164.514>.
3. Microsoft Presidio documentation. Available at: <https://microsoft.github.io/presidio/>.
