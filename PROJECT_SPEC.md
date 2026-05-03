# School Academic Management System (SAMS) - V2.1

## 1. Project Overview

SAMS is a role-based web application for managing student academic results across Nursery, Primary, and Secondary school levels.

The system supports:
- Class-based organization for all levels
- Stream-based structure for Secondary classes only
- Flexible subject offerings per student
- Accurate academic calculations for totals, percentages, grades, and positions

The platform enables:
- Admins to manage the academic structure and all users
- Teachers to manage results only for their assigned classes and streams
- Students to securely access their report cards

This document is the implementation source of truth for the first production version of the system.

## Source of Truth

This document defines all system behavior and must be strictly followed during development.

---

## 2. Core Goals

- Centralize academic result management in one system
- Enforce Role-Based Access Control for Admin, Teacher, and Student users
- Support Secondary streams and optional subjects without breaking Nursery and Primary workflows
- Produce accurate and fair result calculations
- Keep the system secure, auditable, and scalable

---

## 3. User Roles

### 3.1 Admin

Admin users have full system authority.

Capabilities:
- Create, update, activate, and deactivate teachers
- Create, update, activate, and deactivate students
- Create and manage classes
- Create and manage streams for Secondary classes
- Create and manage subjects
- Assign subjects to streams
- Assign teachers to classes
- Assign teachers to streams where applicable
- Assign students to classes and streams
- Create and manage academic sessions
- Open and close result entry for a session-term
- Toggle whether position is visible for each class
- View all results
- Override incorrect results when necessary

Restrictions:
- None within the system

---

### 3.2 Teacher

Teacher users are academic data managers.

Capabilities:
- Access only assigned classes
- For Secondary classes, access only assigned streams within those classes
- View students only within their allowed assignment scope
- Enter and edit results for allowed students and subjects
- Mark a subject as not offered for a student
- Bulk upload results through CSV

Restrictions:
- Cannot access classes not assigned to them
- Cannot access streams not assigned to them
- Cannot manage users, classes, streams, subjects, or sessions
- Cannot edit results for locked session-terms

---

### 3.3 Student

Student users are end users of the portal.

Capabilities:
- Log in with student ID or assigned username
- View report cards for available session-term combinations
- View subject results, total score, percentage, grade summary, and position when enabled
- Download or print a report card

Restrictions:
- Can view only their own data

---

## 4. Academic Structure

### 4.1 Levels

The system supports three levels:
- Nursery
- Primary
- Secondary

Each class belongs to exactly one level.

### 4.2 Classes

A class is the main academic grouping for students.

Examples:
- Nursery 1
- Primary 4
- JSS 2
- SS 1

Each class:
- Has a name
- Belongs to one level
- May have an optional arm such as A or B
- Has a boolean `show_position` setting
- Is active or inactive

### 4.3 Streams

Streams apply only to Secondary classes.

Allowed stream names for the first release:
- Science
- Commercial
- Arts

Rules:
- Nursery and Primary classes do not have streams
- A Secondary class may have zero or more streams
- A stream belongs to exactly one class
- A student in a Secondary class may belong to at most one stream
- If a Secondary class uses streams, every student in that class must belong to one stream before results can be entered

---

## 5. Subjects and Subject Offering

### 5.1 Subjects

A subject is a reusable academic subject such as Mathematics, English Language, Physics, or Government.

Each subject:
- Has a unique name
- Is active or inactive

### 5.2 Stream Subject Assignment

Subjects are assigned to a stream through a `stream_subjects` mapping.

Each `stream_subjects` record contains:
- `stream_id`
- `subject_id`
- `is_compulsory` boolean

Rules:
- A subject may appear in multiple streams
- A stream may contain many subjects
- A subject assigned to a stream is available to students in that stream
- Optional subjects are still valid stream subjects; they simply have `is_compulsory = false`

### 5.3 Nursery and Primary Subject Assignment

Nursery and Primary do not use streams.

For implementation consistency:
- Nursery and Primary classes must have an implicit default stream internally for subject assignment, or
- The system may store subject assignment directly at class level

For V2.1, the required business rule is:
- Every resultable subject for every student must be traceable to the student's academic group

Implementation note:
- If the codebase already supports class-based subjects for Nursery and Primary, that is acceptable
- If the schema is redesigned, using a unified academic-group abstraction is also acceptable

### 5.4 Student Subject Offering

A student may not take every available subject in their stream or class.

The final source of truth for whether a student offered a subject in a given session-term is the `results.is_offered` field.

Rules:
- `is_offered` is stored on the result record
- `is_offered` defaults to `true`
- If `is_offered = false`, the subject is treated as not taken by that student for that session-term
- Subjects marked as not offered must not contribute to total score, percentage, grade summary, or position

---

## 6. Academic Period Model

### 6.1 Session

A session represents one academic year.

Examples:
- 2025/2026
- 2026/2027

Each session:
- Has a unique name
- Is active or inactive

### 6.2 Term

Terms are fixed system values:
- First
- Second
- Third

### 6.3 Session-Term

All result entry and report cards are based on a session-term combination.

Rules:
- A result always belongs to exactly one session and one term
- The system may have many sessions, but only one active session-term at a time for result entry
- Locking and unlocking results is done per session-term, not per session only

Implementation requirement:
- The database must represent both `session` and `term` explicitly, whether term is stored on the results table, on a session-period table, or on an equivalent normalized structure

---

## 7. Result Modes

The system supports two result modes.

### 7.1 Score Mode

Score Mode is used for:
- Primary
- Secondary

Each result record in Score Mode contains:
- `ca_score`
- `exam_score`
- `total_score`
- `grade`
- `remark`
- `is_offered`
- `result_status`

Rules:
- `ca_score` is numeric and must be between 0 and 40 inclusive
- `exam_score` is numeric and must be between 0 and 60 inclusive
- `total_score = ca_score + exam_score`
- `total_score` must therefore be between 0 and 100 inclusive
- `grade` is auto-calculated from `total_score`
- `remark` is auto-calculated from `total_score` unless manually overridden by Admin
- `result_status` must be one of `draft`, `submitted`, or `locked`

### 7.2 Assessment Mode

Assessment Mode is used for:
- Nursery

Each result record in Assessment Mode may contain:
- `assessment_json`
- `remark`
- `is_offered`
- `result_status`

The `assessment_json` field stores structured non-score data such as:
- Behavior ratings
- Attendance
- Participation notes
- Teacher comments

Rules:
- Nursery results do not use `ca_score`, `exam_score`, `total_score`, or `position`
- Nursery report cards may display assessment entries and remarks only
- Nursery students must not be included in numeric ranking logic
- `result_status` must be one of `draft`, `submitted`, or `locked`
- `assessment_json` must follow one consistent schema per Nursery class

Implementation requirement:
- Each Nursery class must have one defined assessment schema used by all its assessment-mode results
- Report card rendering for Nursery must read from that class-defined assessment schema, not from arbitrary keys

---

## 8. Grade and Remark Rules

### 8.1 Default Grading Scale

The default grading scale for Score Mode is:

- 90 to 100: `A+` = Outstanding
- 80 to 89: `A` = Excellent
- 70 to 79: `B` = Very Good
- 60 to 69: `C` = Good
- 50 to 59: `D` = Pass
- 40 to 49: `E` = Below Average
- 0 to 39: `F` = Fail

### 8.2 Grade Calculation

Rules:
- Grade is calculated automatically from `total_score`
- Remark is calculated automatically from `total_score`
- Admin may override grade or remark only if the system explicitly stores override metadata

Implementation requirement:
- If override is supported, store `overridden_by_user_id`, `override_reason`, and `overridden_at`

---

## 9. Percentage Calculation

Percentage applies only to Score Mode.

For each student:

`percentage = total_score_sum / (subjects_taken_count * 100) * 100`

Definitions:
- `total_score_sum` = sum of `total_score` for all result records where `is_offered = true`
- `subjects_taken_count` = count of subjects where `is_offered = true`
- `max_score_per_subject = 100` for V2.1
- `max_score_per_subject` is configurable per class in future versions

Rules:
- If `subjects_taken_count = 0`, percentage must be stored and displayed as `0`
- Results with `is_offered = false` are ignored completely
- Nursery students do not have a percentage

Display rule:
- Percentage should be rounded to two decimal places for display
- Stored precision may be higher if needed

---

## 10. Position System

Position applies only to Score Mode and only when `classes.show_position = true`.

### 10.1 Ranking Scope

Rules:
- Primary position is based on the full class
- Secondary position is based on the student's stream
- Nursery does not have position

### 10.2 Ranking Formula

Ranking is based on:
- Higher `total_score_sum` ranks higher

Only results where `is_offered = true` are included.

### 10.3 Tie-Breaking

Tie-breaking rules are applied in this order:

1. Student with more `A+` grades ranks higher
2. If still tied, student with more `A` grades ranks higher
3. If still tied, student with higher average score ranks higher
4. If still tied, students share the same position

### 10.4 Shared Position Behavior

If two or more students share a position:
- They receive the same displayed position number
- The next position number skips accordingly

Example:
- 1st, 2nd, 2nd, 4th

### 10.5 Position Visibility

Rules:
- Position is calculated only when `show_position = true`
- If `show_position = false`, position must not be displayed to students
- Admins may still view internal ranking data for audit purposes

---

## 11. Result Entry and Locking Rules

### 11.1 Result Uniqueness

For Score Mode, there must be at most one result record per:
- student
- subject
- session
- term

For Assessment Mode, there must be at most one assessment result record per:
- student
- subject or assessment category
- session
- term

Implementation requirement:
- Enforce this with a database unique constraint

### 11.2 Locking

Rules:
- `draft` results are editable by teachers within their assignment scope
- `submitted` results are no longer editable by teachers and are awaiting admin review or finalization
- `locked` results are final and cannot be edited by teachers
- When a session-term is locked, teachers cannot create, edit, submit, or bulk upload results for that session-term
- Admins may unlock the session-term to allow changes
- If Admin override is supported during lock, every override must be auditable

### 11.3 Bulk Upload

CSV upload must validate:
- Student belongs to the class being uploaded
- For Secondary, student belongs to the selected stream
- Subject is valid for the student's class or stream
- Numeric values are within allowed ranges
- Duplicate rows are rejected or merged deterministically

V2.1 deterministic rule:
- Within one upload file, the last valid duplicate row wins
- Across the database, upload updates the existing result instead of creating duplicates

---

## 12. Teacher Assignment Model

The first release must support teacher access control at two scopes:

- Class scope for Nursery and Primary
- Class plus stream scope for Secondary

Required business rule:
- A teacher must never be able to enter or view results outside their assignment scope

Implementation requirement:
- A simple `class_teacher_map` is sufficient only for Nursery and Primary
- Secondary requires a stream-aware assignment model

Acceptable implementations:
- Extend `class_teacher_map` with nullable `stream_id`
- Create a separate `teacher_stream_map`
- Create a unified assignment table with `teacher_id`, `class_id`, and optional `stream_id`

The chosen schema must enforce:
- `stream_id` is null for Nursery and Primary assignments
- `stream_id` is required when restricting a Secondary teacher to one stream

---

## 13. Data Model Requirements

The minimum logical entities are:
- users
- students
- teachers
- classes
- streams
- subjects
- subject assignment mapping
- teacher assignment mapping
- sessions
- result periods or explicit terms
- results

### 13.1 Users

Stores authentication data and role.

Required fields:
- id
- username
- password_hash
- role
- is_active
- created_at

### 13.2 Students

Required fields:
- id
- user_id
- student_code
- first_name
- last_name
- class_id
- stream_id nullable
- level
- is_active

Rules:
- `stream_id` must be null for Nursery and Primary
- `stream_id` may be required for Secondary depending on whether the class uses streams

### 13.3 Teachers

Required fields:
- id
- user_id
- first_name
- last_name
- staff_code nullable
- phone nullable
- is_active

### 13.4 Classes

Required fields:
- id
- name
- level
- arm nullable
- show_position
- is_active

### 13.5 Streams

Required fields:
- id
- class_id
- name
- is_active

Unique rule:
- Stream name must be unique within a class

### 13.6 Subjects

Required fields:
- id
- name
- is_active

Unique rule:
- Subject name must be globally unique for V2.1

### 13.7 Subject Assignment Mapping

Required fields:
- id or composite key
- academic_group reference
- subject_id
- is_compulsory

### 13.8 Results

Required fields for all result records:
- id
- student_id
- subject_id
- class_id
- stream_id nullable
- session_id
- term
- mode
- is_offered
- result_status
- created_at
- updated_at
- uploaded_by_user_id

Additional fields for Score Mode:
- ca_score nullable only when `is_offered = false`
- exam_score nullable only when `is_offered = false`
- total_score nullable only when `is_offered = false`
- grade nullable only when `is_offered = false`
- remark nullable

Additional fields for Assessment Mode:
- assessment_json nullable false
- remark nullable

Rules:
- `mode` is either `score` or `assessment`
- `result_status` is one of `draft`, `submitted`, or `locked`
- `stream_id` must be null for Nursery and Primary results
- `stream_id` is required for Secondary results when the class uses streams

---

## 14. Security and Audit Requirements

- All protected routes require authentication
- All role-specific routes require explicit role checks
- Result entry routes must validate assignment scope server-side
- Passwords must be stored only as hashes
- Every result create or update must record `uploaded_by_user_id`
- Every admin override must record who changed it, when, and why

---

## 15. UI and UX Requirements

### 15.1 Admin Interface

Must support:
- User management
- Class management
- Stream management
- Subject management
- Teacher assignment
- Session-term management
- Result lock control
- Result review

### 15.2 Teacher Interface

Must support:
- Class selection
- Stream selection for Secondary
- Student list view
- Single result entry
- Bulk CSV upload
- Editing unlocked results

### 15.3 Student Interface

Must support:
- Session-term filter
- Report card view
- Download or print report
- Clear visibility of total, percentage, and position when applicable

---

## 16. Out of Scope for V2.1

The following are not required for the first implementation:
- Parent portal
- SMS notifications
- Email notifications
- Student profile image upload
- Advanced analytics dashboard
- Multi-school tenancy

---

## 17. Future Enhancements

Planned future enhancements may include:
- PDF report card generation
- Parent portal access
- SMS and email notifications
- Student profile images
- Advanced analytics dashboards
- Configurable grading scales per class or level
