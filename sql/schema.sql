-- MySQL schema for the project (the notebook creates the same tables automatically via setup_database()).
-- Use this file only if you prefer to create the database yourself in MySQL Workbench.

CREATE DATABASE IF NOT EXISTS cs_project;
USE cs_project;

CREATE TABLE IF NOT EXISTS subject_master (
    sub_cd        INT PRIMARY KEY,          -- Subject code
    sub_name      VARCHAR(15),              -- Subject name
    sub_th_total  INT,                      -- Total subject marks - theory
    sub_pr_total  INT                       -- Total subject marks - practical
);

CREATE TABLE IF NOT EXISTS student_master (
    scholar_no  INT PRIMARY KEY,            -- Scholar number
    stud_name   VARCHAR(45),
    class       INT,
    section     VARCHAR(1),
    roll_no     INT,
    dob         DATE,
    fname       VARCHAR(50),                -- First name
    mname       VARCHAR(50),                -- Last name
    gender      VARCHAR(6)
);

CREATE TABLE IF NOT EXISTS grade_master (
    grade_cd      VARCHAR(2) PRIMARY KEY,   -- Grade code (A1 ... E2)
    grade_desc    VARCHAR(25),              -- Description (Outstanding, Excellent, ...)
    percent_from  INT,                      -- Lower limit of percentage
    percent_till  INT                       -- Upper limit of percentage
);

-- Transaction table: filled by "File Operation -> Merge Files & Generate Result"
CREATE TABLE IF NOT EXISTS student_marks (
    scholar_no    INT,
    sub_cd        INT,
    sub_th_marks  FLOAT,                    -- Marks scored in theory
    sub_pr_marks  FLOAT,                    -- Marks scored in practical
    total_marks   FLOAT,                    -- Theory + practical
    PRIMARY KEY (scholar_no, sub_cd)
);
