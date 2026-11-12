"""
Generates the sample (fictional) data used by the project.

Run:  python generate_sample_data.py

Creates inside ./data :
    student_master.csv   - 44 fictional students (Class 12, Section C)
    subject_master.csv   - 5 subjects with max theory / practical marks
    grade_master.csv     - grade bands (A1 ... E2)
    Sub1_Marks.csv ... Sub5_Marks.csv   - marks files "received from subject teachers"
    bad_examples/        - deliberately broken files to demo the validation screens

All names are randomly combined, fictional and NOT real people.
"""
import csv
import os
import random
from datetime import date, timedelta

random.seed(2026)
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(os.path.join(DATA, "bad_examples"), exist_ok=True)

N_STUDENTS = 44
CLASS_, SECTION = 12, "C"
FIRST_M = ["AARAV", "VIHAAN", "ARJUN", "KABIR", "ISHAAN", "RUDRA", "DEV", "NIKHIL",
           "ROHAN", "YASH", "KARTIK", "SAHIL", "AYAAN", "DHRUV", "PARTH", "VEER",
           "ADITYA", "MANAN", "TANAY", "HARSH", "KUSHAL", "NAMAN"]
FIRST_F = ["ANANYA", "DIYA", "MYRA", "KIARA", "RIYA", "SANVI", "TARA", "NISHA",
           "AVNI", "PIHU", "ISHITA", "MEERA", "SIA", "TRISHA", "VANYA", "ZOYA",
           "AADYA", "KAVYA", "LAVANYA", "NIDHI", "PRERNA", "RHEA"]
LAST = ["SHARMA", "VERMA", "GUPTA", "MEHTA", "KAPOOR", "SINGH", "NAIR", "IYER",
        "REDDY", "BHATIA", "CHOPRA", "DESAI", "JOSHI", "MALIK", "SETHI", "TANDON",
        "BAJAJ", "GROVER", "KHANNA", "LUTHRA", "OBEROI", "PURI", "RASTOGI", "SAHNI",
        "TRIVEDI", "WADHWA"]

# ---- subjects: file number -> (code, name, theory max, practical max) -------------
SUBJECTS = [  # order of files Sub1..Sub5 follows the report (42, 43, 41, 83, 301)
    (42, "Physics", 70, 30),
    (43, "Chemistry", 70, 30),
    (41, "Mathematics", 70, 30),
    (83, "Comp Science", 70, 30),
    (301, "English Core", 70, 30),
]

GRADES = [  # grade_cd, grade_desc, percent_from, percent_till
    ("A1", "Outstanding", 91, 100),
    ("A2", "Excellent", 81, 90),
    ("B1", "Very Good", 71, 80),
    ("B2", "Good", 61, 70),
    ("C1", "Above Average", 51, 60),
    ("C2", "Average", 41, 50),
    ("D", "Satisfactory", 33, 40),
    ("E1", "Needs Improvement", 21, 32),
    ("E2", "Poor", 0, 20),
]


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# ---- student_master ------------------------------------------------------------------
students, used = [], set()
while len(students) < N_STUDENTS:
    gender = random.choice(["MALE", "FEMALE"])
    first = random.choice(FIRST_M if gender == "MALE" else FIRST_F)
    last = random.choice(LAST)
    if (first, last) in used:
        continue
    used.add((first, last))
    students.append((first, last, gender))
students.sort(key=lambda s: (s[0], s[1]))  # roll numbers in alphabetical order

master_rows = []
for i, (first, last, gender) in enumerate(students, start=1):
    dob = date(2004, 1, 1) + timedelta(days=random.randint(0, 540))
    master_rows.append([10000 + i, f"{first} {last}", CLASS_, SECTION, i,
                        dob.isoformat(), first, last, gender])
write_csv(os.path.join(DATA, "student_master.csv"),
          ["scholar_no", "stud_name", "class", "section", "roll_no", "dob",
           "fname", "mname", "gender"], master_rows)

# ---- subject_master / grade_master ------------------------------------------------------
write_csv(os.path.join(DATA, "subject_master.csv"),
          ["sub_cd", "sub_name", "sub_th_total", "sub_pr_total"],
          [[cd, name, th, pr] for cd, name, th, pr in
           sorted(SUBJECTS, key=lambda s: (s[0] != 41, s[0] != 42, s[0] != 43, s[0]))])
write_csv(os.path.join(DATA, "grade_master.csv"),
          ["grade_cd", "grade_desc", "percent_from", "percent_till"], GRADES)

# ---- marks files ----------------------------------------------------------------------
# every student gets an "ability" so that marks are correlated across subjects
ability = {r[0]: min(1.0, max(0.25, random.gauss(0.80, 0.15))) for r in master_rows}
marks = {}  # (file_no) -> rows
for file_no, (cd, name, th_max, pr_max) in enumerate(SUBJECTS, start=1):
    rows = []
    for r in master_rows:
        sch, roll = r[0], r[4]
        a = min(1.0, max(0.2, random.gauss(ability[sch], 0.07)))
        th = int(round(th_max * a))
        pr = int(round(pr_max * min(1.0, max(0.5, random.gauss(0.5 + a / 2, 0.05)))))
        rows.append([roll, sch, cd, min(th, th_max), min(pr, pr_max)])
    marks[file_no] = rows
    write_csv(os.path.join(DATA, f"Sub{file_no}_Marks.csv"),
              ["roll_no", "scholar_no", "sub_cd", "sub_th", "sub_pr"], rows)

# ---- bad examples to demo validation ----------------------------------------------------
BAD = os.path.join(DATA, "bad_examples")
HDR = ["roll_no", "scholar_no", "sub_cd", "sub_th", "sub_pr"]

# 1) Null values (blank theory + practical marks)
rows = [list(r) for r in marks[2]]
rows[5][3] = ""
rows[5][4] = ""
write_csv(os.path.join(BAD, "Sub2_Marks_NULL_VALUES.csv"), HDR, rows)

# 2) Non-numeric values (text in numeric columns)
rows = [list(r) for r in marks[3]]
rows[8][3] = "AB"
rows[8][4] = "ABS"
write_csv(os.path.join(BAD, "Sub3_Marks_NON_NUMERIC.csv"), HDR, rows)

# 3) Record-count mismatch (last student missing)
write_csv(os.path.join(BAD, "Sub4_Marks_MISSING_ROW.csv"), HDR, marks[4][:-1])

print(f"Done. Files written to {DATA}")
