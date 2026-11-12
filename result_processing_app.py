"""
Result Processing and Report Generation  (Computer Science project)
===================================================================
Menu-driven Tkinter application: validates the marks CSV files, stores the merged
result in a database (MySQL or SQLite), publishes PDF report cards and analysis reports.

Run:   python result_processing_app.py
Setup: pip install -r requirements.txt   (see README.md for the database settings / .env file)

"""


# ========================================================================================
# 1. IMPORTS
# ========================================================================================
import os
from tkinter import (Tk, Toplevel, Frame, Menu, Message, Label, Entry,
                     Button, Listbox, IntVar, StringVar, END, TclError, messagebox)

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from reportlab.pdfgen import canvas

import matplotlib
matplotlib.use("Agg")              # charts are only saved to PDF, never drawn on screen
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


# ========================================================================================
# 2. CONFIGURATION
# ========================================================================================
def load_env(path=".env"):
    """Tiny .env reader (KEY=VALUE per line) so no extra package is needed."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env()

# ---- database -------------------------------------------------------------------------
DB_BACKEND     = os.environ.get("DB_BACKEND", "mysql").lower()      # "mysql" or "sqlite"
DB_HOST        = os.environ.get("DB_HOST", "localhost")
DB_PORT        = int(os.environ.get("DB_PORT", "3306"))
DB_USER        = os.environ.get("DB_USER", "root")
DB_PASSWORD    = os.environ.get("DB_PASSWORD", "")
DB_NAME        = os.environ.get("DB_NAME", "cs_project")
DB_AUTH_PLUGIN = os.environ.get("DB_AUTH_PLUGIN", "")
SQLITE_FILE    = os.environ.get("SQLITE_FILE", "cs_project.db")

# ---- folders & files ------------------------------------------------------------------
DATA_DIR   = "data"        # input CSVs (marks files + master tables)
OUTPUT_DIR = "output"      # generated PDFs are saved here
os.makedirs(OUTPUT_DIR, exist_ok=True)

SUBJECT_FILES    = ["Sub1_Marks.csv", "Sub2_Marks.csv", "Sub3_Marks.csv",
                    "Sub4_Marks.csv", "Sub5_Marks.csv"]
REQUIRED_COLUMNS = ["roll_no", "scholar_no", "sub_cd", "sub_th", "sub_pr"]

# ---- report card header  ---------------------------------------
SCHOOL_NAME      = "SAMPLE PUBLIC SCHOOL"
SCHOOL_ADDRESS_1 = "Sample Colony, Sector-1"
SCHOOL_ADDRESS_2 = "New Delhi-110001"
SESSION          = "2021-22"
DEFAULT_CLASS    = 12
DEFAULT_SECTION  = "C"

print(f"Database backend : {DB_BACKEND}")
print(f"Data folder      : {os.path.abspath(DATA_DIR)}")
print(f"Output folder    : {os.path.abspath(OUTPUT_DIR)}")


# ========================================================================================
# 3. DATABASE LAYER
# ========================================================================================
def _mysql_kwargs(include_db=True):
    kwargs = dict(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD)
    if include_db:
        kwargs["database"] = DB_NAME
    if DB_AUTH_PLUGIN:
        kwargs["auth_plugin"] = DB_AUTH_PLUGIN
    return kwargs


def get_connection():
    """Open a connection to the configured database (MySQL or SQLite)."""
    if DB_BACKEND == "sqlite":
        import sqlite3
        return sqlite3.connect(SQLITE_FILE)
    import mysql.connector
    return mysql.connector.connect(**_mysql_kwargs())


def sqlq(query):
    """Queries are written with %s placeholders (MySQL style); SQLite needs ? instead."""
    return query.replace("%s", "?") if DB_BACKEND == "sqlite" else query


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS subject_master (
           sub_cd        INT PRIMARY KEY,
           sub_name      VARCHAR(15),
           sub_th_total  INT,
           sub_pr_total  INT)""",
    """CREATE TABLE IF NOT EXISTS student_master (
           scholar_no  INT PRIMARY KEY,
           stud_name   VARCHAR(45),
           class       INT,
           section     VARCHAR(1),
           roll_no     INT,
           dob         DATE,
           fname       VARCHAR(50),
           mname       VARCHAR(50),
           gender      VARCHAR(6))""",
    """CREATE TABLE IF NOT EXISTS grade_master (
           grade_cd      VARCHAR(2) PRIMARY KEY,
           grade_desc    VARCHAR(25),
           percent_from  INT,
           percent_till  INT)""",
    """CREATE TABLE IF NOT EXISTS student_marks (
           scholar_no    INT,
           sub_cd        INT,
           sub_th_marks  FLOAT,
           sub_pr_marks  FLOAT,
           total_marks   FLOAT,
           PRIMARY KEY (scholar_no, sub_cd))""",
]

MASTER_FILES = {                      # table name -> CSV file in DATA_DIR
    "subject_master": "subject_master.csv",
    "grade_master":   "grade_master.csv",
    "student_master": "student_master.csv",
}


def setup_database(reload_master=False):
    """Create database + tables and load the master tables from CSV (if they are empty)."""
    if DB_BACKEND == "mysql":
        import mysql.connector
        server = mysql.connector.connect(**_mysql_kwargs(include_db=False))
        cur = server.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
        server.commit()
        cur.close()
        server.close()

    con = get_connection()
    cur = con.cursor()
    for ddl in SCHEMA:
        cur.execute(ddl)

    for table, csv_name in MASTER_FILES.items():
        if reload_master:
            cur.execute(f"DELETE FROM {table}")
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        if cur.fetchone()[0] == 0:
            df = pd.read_csv(os.path.join(DATA_DIR, csv_name))
            rows = [tuple(r) for r in df.astype(object).where(df.notna(), None).values.tolist()]
            placeholders = ", ".join(["%s"] * len(df.columns))
            cur.executemany(sqlq(f"INSERT INTO {table} ({', '.join(df.columns)}) "
                                 f"VALUES ({placeholders})"), rows)
            print(f"  loaded {len(rows):>3} rows into {table}")
    con.commit()
    cur.close()
    con.close()
    print(f"Database ready ({DB_BACKEND}).")


def reset_student_marks():
    """Empty the student_marks table so that 'Merge Files & Generate Result' can be run again."""
    con = get_connection()
    cur = con.cursor()
    cur.execute("DELETE FROM student_marks")
    con.commit()
    cur.close()
    con.close()
    print("student_marks cleared.")

setup_database()


# ========================================================================================
# 4. FILE OPERATIONS: UPLOAD, VALIDATE, MERGE AND STORE *(INTEGRATED MODULE)*
# ========================================================================================
# ---------- helpers to show messages inside the main window ----------
def show_msg(text, ok=True, width=500):
    """Green label for success, yellow label for a problem."""
    msgVar = Message(frame, text=text)
    msgVar.config(bg="lightgreen" if ok else "yellow", width=width)
    msgVar.pack()


def clear_messages():
    for widget in frame.winfo_children():
        if isinstance(widget, Message):
            widget.destroy()


SubScores = []          # the five uploaded DataFrames (filled by upload_validate)

FIELDS = [("roll_no", "Roll No."), ("scholar_no", "Scholar No."), ("sub_cd", "Subject Code"),
          ("sub_th", "Theory Marks"), ("sub_pr", "Practical Marks")]


def _file_label(i):
    return os.path.splitext(SUBJECT_FILES[i])[0]            # e.g. "Sub1_Marks"


def _subject_codes(df):
    codes = df["sub_cd"].dropna().unique()
    return ", ".join(str(c) for c in codes) or "unknown"


def _require_upload():
    if not SubScores:
        show_msg("Please upload the files first (File Operation -> Upload & Validate Data).",
                 ok=False, width=700)
        return False
    return True


# ---------- 1. read the five csv files and verify the number of records ----------
def upload_validate():
    global SubScores
    clear_messages()
    SubScores = []
    problems, loaded = [], []

    for fname in SUBJECT_FILES:
        try:
            df = pd.read_csv(os.path.join(DATA_DIR, fname))
        except FileNotFoundError:
            problems.append(f"{fname} was not found in the '{DATA_DIR}' folder")
        except (IOError, pd.errors.EmptyDataError, pd.errors.ParserError) as e:
            problems.append(f"{fname} could not be opened for reading ({e})")
        except Exception as e:
            problems.append(f"{fname}: unhandled exception - {e}")
        else:
            missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
            if missing:
                problems.append(f"{fname} is missing column(s): {', '.join(missing)}")
            else:
                loaded.append(df)

    # exception handling: a file is missing / unreadable
    if problems:
        show_msg("One of the five subject score files was not found in directory or couldn't "
                 "be opened for reading. " + "; ".join(problems) + ". Can't proceed further.",
                 ok=False, width=700)
        return

    SubScores = loaded
    show_msg("All five subject files successfully uploaded")

    # check that all files contain the same number of records
    lengths = [len(df) for df in SubScores]
    print("Lengths of dataset = ", *lengths)
    for i in range(len(lengths) - 1):
        if lengths[i] != lengths[i + 1]:
            show_msg(f"Number of records in file {i + 1} is {lengths[i]} and in file {i + 2} is "
                     f"{lengths[i + 1]}. Please correct data before uploading.", ok=False)
            return
    show_msg("All files contain equal number of records")


# ---------- 2. validate that no null (blank) values are present ----------
def null_validation():
    if not _require_upload():
        return
    for i, df in enumerate(SubScores):
        found = False
        for col, label in FIELDS:
            if df[col].isnull().values.any():
                n = int(df[col].isnull().sum())
                show_msg(f"Null values present in {label} data ({n} blank). Please correct the "
                         f"data in file {_file_label(i)} (subject code - {_subject_codes(df)}).",
                         ok=False, width=1500)
                found = True
        if not found:
            show_msg(f"No Null values present in data for file {_file_label(i)} "
                     f"(subject code - {_subject_codes(df)})", width=1500)


# ---------- 3. validate that only numeric data is present ----------
def numeric_validation():
    if not _require_upload():
        return
    for i, df in enumerate(SubScores):
        found = False
        for col, label in FIELDS:
            if not is_numeric_dtype(df[col]):
                show_msg(f"Non Numeric values present in {label} data. Please correct the data "
                         f"in file {_file_label(i)} (subject code - {_subject_codes(df)}).",
                         ok=False, width=1500)
                print("Non numeric present in ", _file_label(i), "column", col)
                found = True
        if not found:
            show_msg(f"Only numeric data present in file {_file_label(i)} "
                     f"(subject code - {_subject_codes(df)})", width=1500)


# ---------- 4. merge the files and insert the records into the database ----------
# In case of any error in the data the whole insert is rolled back (nothing is half-saved).
def calculate_result():
    if not _require_upload():
        return

    # merge all 5 files using pandas
    AllSubScore = pd.concat(SubScores, axis=0)
    # add a new column holding the subject total (theory + practical)
    AllSubScore["sub_total"] = AllSubScore.sub_th + AllSubScore.sub_pr
    # sort the data on the basis of roll number
    AllSubScoreSorted = AllSubScore.sort_values("roll_no")
    show_msg("All five subject files successfully merged")

    try:
        myconn = get_connection()
        print("Successfully connected to database")
    except Exception as e:
        print("Error connecting to database:", e)
        show_msg("Error connecting to database. Please check the database settings.",
                 ok=False, width=1500)
        return

    cursor1 = myconn.cursor()
    try:
        # int() / float() convert numpy types to plain python types for the database
        rows = [(int(r.scholar_no), int(r.sub_cd), float(r.sub_th), float(r.sub_pr), float(r.sub_total))
                for r in AllSubScoreSorted.itertuples(index=False)]
        print(AllSubScoreSorted.info())
        print(AllSubScoreSorted)
        cursor1.executemany(
            sqlq("insert into student_marks "
                 "(scholar_no, sub_cd, sub_th_marks, sub_pr_marks, total_marks) "
                 "values (%s, %s, %s, %s, %s)"), rows)
    except Exception as e:      # in case of any exception, incomplete data is not written
        print("Unhandled exception: %s" % e)
        myconn.rollback()
        show_msg("Error writing data to database. Please verify the data for correctness.",
                 ok=False, width=1500)
        myconn.close()
        return

    myconn.commit()
    show_msg("Data of all five files, successfully inserted in database", width=1500)
    myconn.close()


# ========================================================================================
# 5. REPORT CARD PDF GENERATION *(REPORTCARDPDFGEN MODULE)*
# ========================================================================================
def initDb():
    """Returns a connection to the main database."""
    try:
        mydb = get_connection()
        print("Connection successful.")
        return mydb
    except Exception as e:
        print("SORRY, CONNECTION UNSUCCESSFUL! PLEASE TRY AGAIN", e)
        messagebox.showerror("Database error", "Could not connect to the database.\n" + str(e))
        return None


def getDataFromDb(cursor, table_name, raw_data):
    # raw_data[table_name] = list with one dictionary (column name -> value) per record
    cursor.execute("SELECT * FROM " + table_name)
    column_names = [i[0] for i in cursor.description]
    raw_data[table_name] = [dict(zip(column_names, row)) for row in cursor.fetchall()]


def getAllData(cursor):
    """Master dictionary: table name -> list of record dictionaries."""
    raw_data = {}
    getDataFromDb(cursor, "student_master", raw_data)
    getDataFromDb(cursor, "grade_master", raw_data)
    getDataFromDb(cursor, "subject_master", raw_data)
    getDataFromDb(cursor, "student_marks", raw_data)
    return raw_data


def organizeRawData(raw_data):
    # info of every student: key = scholar no, value = dictionary with that student's info
    student_dict = {row["scholar_no"]: row for row in raw_data["student_master"]}
    # grade bands sorted from the highest "percent_from" to the lowest
    grade_list = sorted(((row["percent_from"], row) for row in raw_data["grade_master"]),
                        key=lambda item: item[0], reverse=True)
    subject_dict = {row["sub_cd"]: row for row in raw_data["subject_master"]}
    marks_dict = {(row["scholar_no"], row["sub_cd"]): row for row in raw_data["student_marks"]}
    return student_dict, grade_list, subject_dict, marks_dict


def getMaxStudentTotal(subject_dict):
    """Maximum possible marks (grand total of all subjects, e.g. 500)."""
    max_total = 0
    for sub_details in subject_dict.values():
        max_total += sub_details["sub_th_total"] + sub_details["sub_pr_total"]
    return max_total


def getFinalStudentInfo(raw_data):
    student_final_data = {}
    student_dict, grade_list, subject_dict, marks_dict = organizeRawData(raw_data)
    student_max_total = getMaxStudentTotal(subject_dict)

    for scholar_no, student_row in student_dict.items():
        roll = student_row["roll_no"]
        student_final_data[roll] = {}
        student_final_data[roll].update(student_row)
        student_final_data[roll]["subs"] = {}
        student_marks_total = 0

        for sub_cd, sub_details in subject_dict.items():
            sub_marks = marks_dict.get((scholar_no, sub_cd))
            if sub_marks is None:               # no marks uploaded for this subject
                continue
            sub_total = sub_marks["sub_th_marks"] + sub_marks["sub_pr_marks"]
            student_marks_total += sub_total
            student_final_data[roll]["subs"][sub_details["sub_cd"]] = {
                "th_marks": sub_marks["sub_th_marks"],
                "pr_marks": sub_marks["sub_pr_marks"],
                "sub_name": sub_details["sub_name"],
                "total_marks": sub_total}

        student_perc = 100 * (student_marks_total / student_max_total)
        student_final_data[roll]["total_marks"] = student_marks_total
        student_final_data[roll]["perc"] = student_perc

        for percent_from, grade_row in grade_list:      # first band whose lower limit is reached
            if student_perc >= percent_from:
                student_final_data[roll]["grade"] = grade_row["grade_cd"]
                student_final_data[roll]["grade_desc"] = grade_row["grade_desc"]
                break
    return student_final_data


student_final_data = {}


def main_getinfo():
    """Reads the database and builds student_final_data. Returns True when data is available."""
    global student_final_data
    db = initDb()
    if db is None:
        return False
    cursor = db.cursor()
    raw_data = getAllData(cursor)
    db.close()
    if not raw_data["student_marks"]:
        messagebox.showwarning("No marks found",
                               "The student_marks table is empty.\nRun File Operation -> "
                               "'Merge Files & Generate Result' first.")
        student_final_data = {}
        return False
    student_final_data = getFinalStudentInfo(raw_data)
    return True

def fmt(x):
    """70.0 -> '70', 72.5 -> '72.50' (marks are stored as floats in the database)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return str(x)
    return str(int(x)) if x == int(x) else f"{x:.2f}"


def createPdf():
    # values typed by the user in the form (see main_form)
    try:
        roll_num_start = rno_in1.get()
        roll_num_end = rno_in2.get()
        class_sel = cl_in.get()
        sec_sel = sec_in.get().strip().upper()
    except TclError:
        messagebox.showerror("Invalid input", "Please enter numbers for the class and roll numbers.")
        return

    count = 0
    for roll_no, data in sorted(student_final_data.items()):
        if roll_no < roll_num_start or roll_no > roll_num_end:
            continue
        if class_sel and data["class"] != class_sel:                   # optional class filter
            continue
        if sec_sel and str(data["section"]).upper() != sec_sel:        # optional section filter
            continue

        fname = os.path.join(OUTPUT_DIR, "Roll No. " + str(roll_no) + " Report_Card.pdf")

        # ------------------------ PDF format ------------------------
        c = canvas.Canvas(fname)
        c.drawCentredString(297, 820, SCHOOL_NAME)
        c.drawCentredString(297, 800, SCHOOL_ADDRESS_1)
        c.drawCentredString(297, 780, SCHOOL_ADDRESS_2)
        c.line(60, 770, 535, 770)
        c.drawCentredString(297, 750, "REPORT CARD")
        c.drawCentredString(297, 730, "SESSION " + SESSION)
        c.line(60, 720, 535, 720)

        c.drawString(60, 700, "Name: " + data["stud_name"])
        c.drawRightString(535, 700, "Scholar Number: " + str(data["scholar_no"]))
        c.drawString(60, 660, "Class: " + str(data["class"]))
        c.drawRightString(535, 660, "Section: " + data["section"])
        c.drawString(60, 620, "Roll Number: " + str(data["roll_no"]))
        c.drawRightString(535, 620, "Date Of Birth: " + str(data["dob"]))
        c.drawString(60, 580, "Gender: " + data["gender"])

        # marks table (grid)
        c.line(60, 570, 500, 570)
        c.line(60, 570, 60, 410)
        c.line(180, 570, 180, 410)
        c.line(280, 570, 280, 410)
        c.line(390, 570, 390, 410)
        c.line(500, 570, 500, 410)

        c.drawString(60, 550, "Subject")
        c.drawString(200, 550, "Theory Marks")
        c.drawString(300, 550, "Practical Marks")
        c.drawString(400, 550, "Total Marks")
        c.line(60, 520, 500, 520)

        i = 0
        for sub_cd, sub_details in data["subs"].items():
            c.drawString(60, 500 - 20 * i, sub_details["sub_name"] + " " + "(" + str(sub_cd) + ")")
            c.drawString(200, 500 - 20 * i, fmt(sub_details["th_marks"]))
            c.drawString(300, 500 - 20 * i, fmt(sub_details["pr_marks"]))
            c.drawString(400, 500 - 20 * i, fmt(sub_details["total_marks"]))
            c.line(60, 490 - 20 * i, 500, 490 - 20 * i)
            i += 1

        c.drawString(60, 360, "Total Marks: " + fmt(data["total_marks"]))
        c.drawRightString(535, 360, "Percentage: " + f"{data['perc']:.2f}")
        c.line(60, 350, 535, 350)

        c.drawString(60, 330, "Grade: " + str(data.get("grade", "-")))
        c.drawString(60, 290, "Result: " + str(data.get("grade_desc", "-")))
        c.drawString(60, 250, "Signature: ")
        c.line(60, 240, 535, 240)

        c.save()
        count += 1

    if count:
        messagebox.showinfo("Report cards published",
                            f"{count} report card(s) saved in:\n{os.path.abspath(OUTPUT_DIR)}")
    else:
        messagebox.showwarning("Nothing to publish",
                               "No student found for the class / section / roll number range entered.")


def main_form():
    if not main_getinfo():                  # load all the data from the database
        return
    form = Toplevel()                       # Toplevel: opens on top of the main window
    form.geometry("350x300")
    form.title("Publish Report Card")
    header = Label(form, text="Publish Report Card", width="350", height="2", bg="orange")
    header.pack()

    cl_la = Label(form, text="Class: ")
    cl_la.place(x=60, y=60)
    sec_la = Label(form, text="Section: ")
    sec_la.place(x=60, y=100)
    rno_la1 = Label(form, text="From Roll Number: ")
    rno_la1.place(x=60, y=140)
    rno_la2 = Label(form, text="To Roll Number: ")
    rno_la2.place(x=60, y=180)

    global cl_in, sec_in, rno_in1, rno_in2
    cl_in = IntVar(value=DEFAULT_CLASS)
    sec_in = StringVar(value=DEFAULT_SECTION)
    rno_in1 = IntVar(value=1)
    rno_in2 = IntVar(value=5)

    cl_en = Entry(form, textvariable=cl_in, width="10")
    sec_en = Entry(form, textvariable=sec_in, width="10")
    rno_en1 = Entry(form, textvariable=rno_in1, width="10")
    rno_en2 = Entry(form, textvariable=rno_in2, width="10")
    cl_en.place(x=200, y=60)
    sec_en.place(x=200, y=100)
    rno_en1.place(x=200, y=140)
    rno_en2.place(x=200, y=180)

    but1 = Button(form, text="Publish", width="10", bg="light grey", command=createPdf)
    but1.place(x=200, y=220)


# ========================================================================================
# 6. ANALYSIS REPORTS *(FINALREPORTS MODULE)*
# ========================================================================================
# ---------- fetching subject name and subject code for which the report is required ----------
def selected_subname():
    for i in listbox1.curselection():
        return listbox1.get(i)


def selected_subcd(c):
    subname = selected_subname()
    c.execute(sqlq("select sub_cd from subject_master where sub_name=%s"), (str(subname),))
    data = c.fetchall()
    return data[0][0]


# ---------- lists of grades, grade ranges, subject codes and subject names ----------
def fetchgradelist(cursor):
    cursor.execute("select grade_cd from grade_master order by percent_from desc")
    return [i[0] for i in cursor.fetchall()]


def fetchpercent_from(cursor):
    cursor.execute("select percent_from from grade_master order by percent_from desc")
    return [i[0] for i in cursor.fetchall()]


def fetchpercent_till(cursor):
    cursor.execute("select percent_till from grade_master order by percent_from desc")
    return [i[0] for i in cursor.fetchall()]


def fetchsub_cdlist(cursor):
    cursor.execute("select sub_cd from subject_master order by sub_cd")
    return [i[0] for i in cursor.fetchall()]


def fetchsub_namelist(cursor):
    cursor.execute("select sub_name from subject_master order by sub_cd")
    return [i[0] for i in cursor.fetchall()]


# ---------- number of students receiving a particular grade in a subject (bar graph, pie chart) ----------
def nstud(obj, sub_cd):
    c = obj.cursor()
    gradelist = fetchgradelist(c)
    percent_from = fetchpercent_from(c)
    percent_till = fetchpercent_till(c)
    temp = list()
    for n in range(len(gradelist)):
        c.execute(sqlq("select * from student_marks where sub_cd=%s "
                       "and total_marks between %s and %s"),
                  (sub_cd, percent_from[n], percent_till[n]))
        temp.append(len(c.fetchall()))
    return temp


def showMsg():
    messagebox.showinfo("Report generated",
                        "Report generated successfully!\nSaved in: " + os.path.abspath(OUTPUT_DIR))

# ---------- PLOTTING BAR GRAPH ----------
def plotbg(obj):
    # fetching required data
    c = obj.cursor()
    subname = selected_subname()
    subcd = selected_subcd(c)
    gradelist = fetchgradelist(c)

    bg_pdf = PdfPages(os.path.join(OUTPUT_DIR, str(subname).capitalize() + "_BarGraph.pdf"))
    fig, ax = plt.subplots()

    # plotting graph
    x_grade = np.array(gradelist)
    ax.bar(x_grade, nstud(obj, subcd), color="blue")
    ax.set(title=str(subname).upper() + "(Subject Code: " + str(subcd) + ")",
           xlabel="Grades", ylabel="Number of Students")

    # saving in a pdf
    bg_pdf.savefig(fig)
    bg_pdf.close()
    plt.close(fig)
    showMsg()


# ---------- PLOTTING PIE CHART ----------
def plotpc(obj):
    # fetching required data
    c = obj.cursor()
    subname = selected_subname()
    subcd = selected_subcd(c)
    gradelist = fetchgradelist(c)

    x = np.array(gradelist)
    y = np.array(nstud(obj, subcd))

    pc_pdf = PdfPages(os.path.join(OUTPUT_DIR, str(subname).capitalize() + "_PieChart.pdf"))
    fig, ax = plt.subplots()

    # plotting chart
    ax.pie(y, shadow=True, startangle=90)
    porcent = 100. * y / y.sum()
    labels = ["{0} - {1:1.2f} %".format(i, j) for i, j in zip(x, porcent)]
    ax.legend(labels, bbox_to_anchor=(0.85, 1.025), loc="upper left", title="KEY:")
    ax.set(title=str(subname).upper() + "(Subject Code: " + str(subcd) + ")")

    # saving in a pdf
    pc_pdf.savefig(fig, bbox_inches="tight")
    pc_pdf.close()
    plt.close(fig)
    showMsg()

# ---------- helpers shared by the two table reports ----------
def fetch_names(obj):
    cursor = obj.cursor()
    cursor.execute("select stud_name from student_master order by scholar_no")
    return [i[0] for i in cursor.fetchall()]


def fetch_scholar_nos(obj):
    cursor = obj.cursor()
    cursor.execute("select scholar_no from student_master order by scholar_no")
    return [j[0] for j in cursor.fetchall()]


def fetch_subject_marks(obj, subcd, schlist):
    """Total marks (theory + practical) of every student in one subject."""
    mrklist = list()
    cursor3 = obj.cursor()
    for k in schlist:
        cursor3.execute(sqlq("select total_marks from student_marks where sub_cd=%s and scholar_no=%s"),
                        (subcd, k))
        for m in cursor3.fetchall():
            mrklist.append(m[0])
    return mrklist


def save_table_pdf(df, pdf_path, col_widths):
    """Draw a dataframe as a matplotlib table and save it into a pdf."""
    with PdfPages(pdf_path) as pdf:
        plt.figure(figsize=(8.27, 2))
        colors = ["c"] * len(df.columns)
        plt.table(cellText=df.values, colLabels=df.columns, loc="top", colLoc="center",
                  bbox=None, colColours=colors, colWidths=col_widths)
        plt.axis("off")
        plt.tight_layout()
        pdf.savefig(bbox_inches="tight", pad_inches=0.4)
        plt.close()


# ---------- CREATING LIST OF SUBJECT TOPPERS ----------
def sub_top(obj):
    c = obj.cursor()
    subname = selected_subname()
    subcd = selected_subcd(c)

    namelist = fetch_names(obj)                       # list of names
    schlist = fetch_scholar_nos(obj)                  # list of scholar numbers
    marks = fetch_subject_marks(obj, subcd, schlist)  # marks of each child in the subject

    # generating dataset for the subject: sorted by marks, rank = (index + 1)
    col = "MARKS IN " + str(subname).upper()
    mydataset = {"NAME OF STUDENT": namelist, col: marks}
    df = pd.DataFrame(mydataset).sort_values(by=col, ascending=False, ignore_index=True)
    df["RANK"] = df.index + 1

    save_table_pdf(df, os.path.join(OUTPUT_DIR, str(subname).capitalize() + "_SubToppers.pdf"),
                   col_widths=[0.3 for _ in range(df.columns.size)])
    showMsg()


# ---------- CREATING OVERALL RANK LIST ----------
def ranklist(obj):
    c = obj.cursor()
    sub_cdlist = fetchsub_cdlist(c)
    sub_namelist = fetchsub_namelist(c)

    namelist = fetch_names(obj)                       # list of names
    schlist = fetch_scholar_nos(obj)                  # list of scholar numbers

    # list of total marks (all subjects) of each student
    tmarks_list = []
    for z in schlist:
        cursor4 = obj.cursor()
        cursor4.execute(sqlq("select sum(total_marks) from student_marks where scholar_no=%s"), (z,))
        tmarks_list.append(cursor4.fetchall()[0][0])

    # generating the overall dataset: name | marks in every subject | total | rank
    dataset1 = {"NAME OF STUDENT": namelist}
    dataset2 = {sub_namelist[i].upper(): fetch_subject_marks(obj, sub_cdlist[i], schlist)
                for i in range(len(sub_namelist))}
    dataset3 = {"TOTAL MARKS": tmarks_list}
    dataset1.update(dataset2)
    dataset1.update(dataset3)

    df = pd.DataFrame(dataset1).sort_values(by="TOTAL MARKS", ascending=False, ignore_index=True)
    df["RANK"] = df.index + 1

    n = len(df.columns)
    save_table_pdf(df, os.path.join(OUTPUT_DIR, "Class Rank List.pdf"),
                   col_widths=[0.3] + [0.2] * (n - 2) + [0.1])
    showMsg()

# ---------- GUI: choose class / section / subject and click a report button ----------
def PublishReports():
    obj = get_connection()
    c = obj.cursor()

    form = Toplevel()
    form.geometry("350x420")
    form.title("Publish Reports")
    form.protocol("WM_DELETE_WINDOW", lambda: (obj.close(), form.destroy()))

    header = Label(form, text="GENERATE ANALYSIS REPORTS", width="350", height="2", bg="orange")
    header.pack()

    # defining and placing labels
    cl_la = Label(form, text="Class: ")
    cl_la.place(x=60, y=60)
    sec_la = Label(form, text="Section: ")
    sec_la.place(x=60, y=100)
    subname = Label(form, text="Subject Name: ")
    subname.place(x=60, y=140)

    cl_in = IntVar(value=DEFAULT_CLASS)
    sec_in = StringVar(value=DEFAULT_SECTION)

    # entry widgets for class and section
    cl_en = Entry(form, textvariable=cl_in, width="15")
    sec_en = Entry(form, textvariable=sec_in, width="15")
    cl_en.place(x=200, y=60)
    sec_en.place(x=200, y=100)

    # listbox for subject name
    global listbox1
    listbox1 = Listbox(form, exportselection=False, height=5)
    sub_names = fetchsub_namelist(c)
    for n in range(min(5, len(sub_names))):
        listbox1.insert(END, str(sub_names[n]))
    listbox1.selection_set(0)
    listbox1.place(x=200, y=140)

    # checks that the entries are filled, that the class exists and a subject is selected;
    # if the checks pass the requested report is generated
    def check(b):
        var1 = cl_en.get()
        var2 = sec_en.get()
        if var1 == "" or var2 == "":
            messagebox.showinfo("Alert!", "Please enter both class and section")
            return
        ctemp = obj.cursor()
        ctemp.execute("select class,section from student_master")
        existing = {(str(r[0]), str(r[1]).upper()) for r in ctemp.fetchall()}
        if (var1.strip(), var2.strip().upper()) not in existing:
            messagebox.showinfo("Alert!", "Data for entered class does not exist")
            return
        if not listbox1.curselection():
            messagebox.showinfo("Alert!", "Please select a subject")
            return
        if b == "b1":
            plotbg(obj)
        elif b == "b2":
            plotpc(obj)
        elif b == "b3":
            sub_top(obj)
        elif b == "b4":
            ranklist(obj)

    # buttons to generate the various reports
    but1 = Button(form, text="Grade Wise Performance", command=lambda: check("b1"), width="30", bg="light grey")
    but1.place(x=80, y=240)
    but2 = Button(form, text="Grade Wise % of Students", command=lambda: check("b2"), width="30", bg="light grey")
    but2.place(x=80, y=280)
    but3 = Button(form, text="Subject Toppers", command=lambda: check("b3"), width="30", bg="light grey")
    but3.place(x=80, y=320)
    but4 = Button(form, text="Class Rank Wise Report\n(overall)", command=lambda: check("b4"),
                  width="30", bg="light grey")
    but4.place(x=80, y=360)


# ========================================================================================
# 7. RUN THE APPLICATION
# ========================================================================================
def about():
    messagebox.showinfo("About", "CS Project - Result Processing and Report Generation\n\n"
                                 "Upload & validate marks, publish report cards and analysis reports.\n\n"
                                 "Modules: Integrated (Jhanavi Malhotra), Report Card (Swaanshi Jain), "
                                 "Reports (Prashi)")


def run_app():
    # create main window
    global main, frame, menu
    main = Tk()
    main.title("CS Project - Result Processing and Report Generation")
    main.geometry("800x500")       # sets the window size, it remains fixed throughout the navigation
    frame = Frame(main)
    frame.pack()
    menu = Menu(frame)
    main.config(menu=menu)

    # Invoking a function using lambda ensures that the function doesn't get executed on loading
    # of the program and gets called only on the click of the menu option.
    filemenu = Menu(menu)
    menu.add_cascade(label="File Operation", menu=filemenu)
    filemenu.add_command(label="Upload & Validate Data", command=lambda: upload_validate())
    filemenu.add_command(label="Null Values Validation", command=lambda: null_validation())
    filemenu.add_command(label="Numeric Data Validation", command=lambda: numeric_validation())
    filemenu.add_command(label="Merge Files & Generate Result", command=lambda: calculate_result())
    filemenu.add_separator()
    filemenu.add_command(label="Exit", command=main.destroy)

    rptcardmenu = Menu(menu)
    menu.add_cascade(label="Report Card", menu=rptcardmenu)
    rptcardmenu.add_command(label="Publish Report Card", command=lambda: main_form())

    reportmenu = Menu(menu)
    menu.add_cascade(label="Reports", menu=reportmenu)
    reportmenu.add_command(label="Generate Reports", command=lambda: PublishReports())

    helpmenu = Menu(menu)
    menu.add_cascade(label="Help", menu=helpmenu)
    helpmenu.add_command(label="About", command=lambda: about())

    # bring the window to the front, then keep running till the window is closed
    main.lift()
    main.attributes("-topmost", True)
    main.after(500, lambda: main.attributes("-topmost", False))
    main.mainloop()


if __name__ == "__main__":
    run_app()


# ========================================================================================
# 8. UTILITIES (OPTIONAL)
# ========================================================================================
# reset_student_marks()                      # empty student_marks so the merge step can be repeated
# setup_database(reload_master=True)         # re-load student / subject / grade master tables from CSV

