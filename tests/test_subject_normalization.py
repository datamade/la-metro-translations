import pytest
from la_metro_translations.services.ocr import normalize_subject_lines

# Note that all test data should be written flush left so that we avoid problems
# with leading whitespace (which the Mistral OCR data does not have).


@pytest.mark.parametrize(
    "subjects, expected",
    [
        (
            """
SUBJECT: GENERAL PUBLIC COMMENT
SUBJECT: 1000 (MINUTES)
        """,
            """
**SUBJECT: GENERAL PUBLIC COMMENT**
**SUBJECT: 1000 (MINUTES)**
        """,
        ),
        (
            """
2. SUBJECT: 1000 MINUTES
58. SUBJECT: MEASURE M METRO ACTIVE TRANSPORT, TRANSIT AND FIRST/LAST MILE (MAT) PROGRAM CYCLE 2
        """,
            """
**2. SUBJECT: 1000 MINUTES**
**58. SUBJECT: MEASURE M METRO ACTIVE TRANSPORT, TRANSIT AND FIRST/LAST MILE (MAT) PROGRAM CYCLE 2**
        """,
        ),
        (
            """
3. SUBJECT: REMARKS BY THE CHAIR [2025-0834](https://metro.legistar.com/gateway.aspx?m=l&id=/matter.aspx?key=11853)
44. SUBJECT: PUBLIC HEARING ON RESOLUTIONS OF NECESSITY [2025-0596](https://metro.legistar.com?m=l&id=/123)
        """,
            """
**3. SUBJECT: REMARKS BY THE CHAIR [2025-0834](https://metro.legistar.com/gateway.aspx?m=l&id=/matter.aspx?key=11853)**
**44. SUBJECT: PUBLIC HEARING ON RESOLUTIONS OF NECESSITY [2025-0596](https://metro.legistar.com?m=l&id=/123)**
        """,
        ),
        (
            """
### SUBJECT: GENERAL PUBLIC COMMENT
### 3. SUBJECT: CONSTRUCTION ZONE ENHANCED ENFORCEMENT PROGRAM (COZEEP) SERVICES
### 14. SUBJECT: REPORT BY THE CHIEF EXECUTIVE OFFICER [2025-0835](https://metrom/gway.aspx?m=l&id=/mar.aspx?key=11615)
        """,
            """
**SUBJECT: GENERAL PUBLIC COMMENT**
**3. SUBJECT: CONSTRUCTION ZONE ENHANCED ENFORCEMENT PROGRAM (COZEEP) SERVICES**
**14. SUBJECT: REPORT BY THE CHIEF EXECUTIVE OFFICER [2025-0835](https://metrom/gway.aspx?m=l&id=/mar.aspx?key=11615)**
        """,
        ),
        (
            """
**SUBJECT: GENERAL PUBLIC COMMENT**
**5. SUBJECT: FEDERAL TRANSIT ADMINISTRATION SECTION 5310 PROGRAM**
**4. SUBJECT: REPORT BY THE CHIEF EXECUTIVE OFFICER [2025-0835](https://metrom/gway.aspx?m=l&id=/mar.aspx?key=11615)**
        """,
            """
**SUBJECT: GENERAL PUBLIC COMMENT**
**5. SUBJECT: FEDERAL TRANSIT ADMINISTRATION SECTION 5310 PROGRAM**
**4. SUBJECT: REPORT BY THE CHIEF EXECUTIVE OFFICER [2025-0835](https://metrom/gway.aspx?m=l&id=/mar.aspx?key=11615)**
        """,
        ),
    ],
)
def test_normalize_subject_lines(subjects, expected):
    assert normalize_subject_lines(subjects) == expected
