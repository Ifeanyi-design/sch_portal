# School Academic Management System (SAMS) - V2.2

## Source of Truth

This document defines all system behavior and must be strictly followed during development.

---

## Project Overview

SAMS is a role-based web application for managing student academic results across Nursery, Primary, and Secondary school levels.

The system supports:
- Class-based organization
- Stream-based structure for Secondary classes only
- Flexible subject offerings
- Multi-level position ranking
- Admin-controlled result entry workflow
- Score-mode and assessment-mode reporting

---

## Core Goals

- Centralized result management
- Accurate academic calculations
- Real-world school workflow support
- Flexible role permissions
- Clean and usable UI
- Secure and auditable academic records

---

## User Roles

### Admin

Full system authority.

Capabilities:
- Manage users, classes, streams, subjects, sessions, and terms
- Assign teachers to classes
- Assign students to classes and streams
- Upload results manually or by CSV
- Enable or disable teacher result upload globally
- Lock and unlock results
- Override results with audit logs
- View all results and rankings
- Recalculate positions and annual results

### Teacher

Class-level academic manager.

Capabilities:
- Access assigned classes only
- Access all streams within an assigned Secondary class
- View student results within assigned classes
- Upload results only if teacher upload is enabled

Restrictions:
- Cannot access unassigned classes
- Cannot upload results if `allow_teacher_result_upload = false`
- Cannot manage system structure
- Cannot edit locked results

### Student

Capabilities:
- View personal report cards only
- See subject results, total score, percentage, grade summary, and positions
- Print and download report cards

---

## System Settings

### Global Setting

`allow_teacher_result_upload` (boolean)

Behavior:
- `true` -> teachers can upload results within their assigned class scope
- `false` -> only admin can upload results

When disabled:
- Teacher upload routes must reject uploads server-side
- Teacher upload UI must be hidden or disabled

---

## Academic Structure

### Levels

- Kindergarten
- Nursery
- Primary
- Secondary

### Streams

Streams apply to Secondary classes only.

Supported stream names:
- Science
- Commercial
- Arts

Rules:
- Only Secondary classes use streams
- Non-Secondary classes must not require or display stream selection
- Secondary students must belong to a stream when the class uses streams

---

## Subject System

Subject assignment rules:
- Kindergarten, Nursery, and Primary subjects are assigned at class level
- Secondary subjects are assigned at stream level

Each subject assignment may be:
- Compulsory
- Optional

Student offering rules:
- A student may belong to a subject-bearing class or stream
- A student may choose not to offer optional subjects
- Only subjects marked `is_offered = true` participate in score calculations and ranking

---

## Student Model

Each student record must include:
- `user_id`
- `student_code`
- `first_name`
- `last_name`
- `gender`
- `date_of_birth`
- `class_id`
- `stream_id` (nullable for non-Secondary classes)
- `admission_year`
- `active_status`
- `parent_name` (optional)
- `parent_phone` (optional)
- `address` (optional)

Rules:
- `stream_id` must be null for non-Secondary classes
- `stream_id` is required only when the student's class is Secondary and uses streams

---

## Session, Term, and Result Scope

Results must always be tied to:
- class
- term
- session

Session-term rules:
- A term belongs to a session
- Result locking is controlled within the session-term scope
- Annual results are computed from the three terms within the same session

---

## Result System

### Result Modes

#### Score Mode

Applies to:
- Primary
- Secondary

Each score-mode result includes:
- `ca_score` (0-40)
- `exam_score` (0-60)
- `total_score` (0-100, auto-calculated)
- `grade` (auto-calculated)
- `remark`
- `is_offered`

#### Assessment Mode

Applies to:
- Kindergarten
- Nursery

Each assessment-mode result includes:
- `assessment_json`
- `remark`

Rules:
- `assessment_json` must follow one consistent schema per class
- Assessment-mode results do not use numeric percentage or position ranking

### Result Status

Each result must have a workflow status:
- `draft`
- `submitted`
- `locked`

Workflow rules:
- Teachers may edit only `draft` results
- Admin may move `submitted` back to `draft`
- Locked results are final and cannot be edited by teachers
- Admin may unlock results back to `draft` when permitted by workflow

---

## Score Calculation

For score-mode results:

`total_score = ca_score + exam_score`

Rules:
- `ca_score` must be between `0` and `40`
- `exam_score` must be between `0` and `60`
- `total_score` must be between `0` and `100`
- Grade and remark are automatically generated from the grading scale

---

## Percentage Calculation

For each student in score mode:

`percentage = (total_score_sum / (subjects_taken * 100)) * 100`

Definitions:
- `total_score_sum` = sum of `total_score` for all results where `is_offered = true`
- `subjects_taken` = count of results where `is_offered = true`
- `100` = max score per subject for V2.2

Rules:
- Only `is_offered = true` results are included
- Percentage must be rounded to 2 decimal places
- If `subjects_taken = 0`, percentage must not be computed

---

## Position System

### Position Types

The system supports:
- overall class position
- stream position
- subject position

### Term Position Rules

#### Overall Class Position

Definition:
- Rank all students in a class using score-mode totals

Applies to:
- Primary
- Secondary

Rules:
- Only students with score-mode results are ranked
- Only subjects with `is_offered = true` are included

#### Stream Position

Definition:
- Rank students within the same stream

Applies to:
- Secondary only

Rules:
- Stream position must not exist for non-Secondary classes
- Only subjects with `is_offered = true` are included

#### Subject Position

Definition:
- Rank students in a class or stream based on subject `total_score`

Applies to:
- Primary
- Secondary

Rules:
- Only students where `is_offered = true` for that subject are included
- For Primary, subject position is within the class
- For Secondary, subject position is within the stream for stream-bound subjects

### Tie-Breaking Rules

If two or more students are tied:
1. Student with more `A+` grades ranks higher
2. If still tied, student with more `A` grades ranks higher
3. If still tied, student with higher average score ranks higher
4. If still tied, students share the same position

### Position Display Rules

- Kindergarten -> no position
- Nursery -> no position
- Primary -> overall class position and subject position
- Secondary -> overall class position, stream position, and subject position

### Position Visibility

Student-facing position display is controlled by `class.show_position`.

Rules:
- If `class.show_position = false`, positions must not be shown to students
- Admin may still view and recalculate positions internally

---

## Annual (Cumulative) Result System

### Overview

In addition to individual term results, the system must compute annual cumulative results after the third term.

Annual results:
- do not replace third-term results
- are computed, not manually entered
- are read-only

### Annual Eligibility

Annual results apply only to:
- Primary
- Secondary

Excluded:
- Kindergarten
- Nursery

Annual results must not be computed if:
- any of the three terms is missing for the student

### Annual Percentage

`annual_percentage = (first_term_percentage + second_term_percentage + third_term_percentage) / 3`

Rules:
- All three term percentages must exist
- Annual percentage must be rounded to 2 decimal places

### Annual Total

`annual_total_score = first_term_total + second_term_total + third_term_total`

This value may be displayed together with annual percentage.

### Annual Subject Performance

For each subject:

`annual_subject_average = (term1_subject_score + term2_subject_score + term3_subject_score) / 3`

Rules:
- Applies only to score-mode subjects
- A subject must have `is_offered = true` in all three terms for that student before annual subject average is computed
- If the subject is not offered in any one term, annual subject average for that subject must not be generated

### Annual Positions

Annual rankings must support:
- overall annual position
- stream annual position
- subject annual position

Rules:
- Overall annual position is based on annual totals or annual percentage within the class
- Stream annual position is based on annual totals or annual percentage within the stream
- Subject annual position is based on annual subject average
- Tie-breaking rules are the same as term-based ranking

### Annual Display Rules

Student report must show:
- first term result
- second term result
- third term result
- annual total
- annual percentage
- annual subject averages
- annual positions

Annual visibility rules:
- Annual results become visible only after third term is completed or locked

---

## Real-World Workflow

### Default Workflow

Expected real-world flow:
1. Subject teachers prepare raw results manually
2. Class teacher compiles class results
3. Admin uploads results into the system

### Optional Teacher Upload Workflow

If `allow_teacher_result_upload = true`:
- teachers may upload results directly for assigned classes

If `allow_teacher_result_upload = false`:
- only admin may upload results

---

## Teacher Assignment Model

Teachers are assigned to classes only.

Rules:
- No stream-based teacher restriction exists in V2.2
- A teacher assigned to a Secondary class can access all streams in that class
- Stream selection is a data-entry context, not an assignment boundary

---

## Result Entry Control

Rules:
- Results are tied to session and term
- Admin controls locking and unlocking
- Teachers cannot edit locked results
- Upload access must be enforced server-side
- Subject validation must ensure the subject belongs to the relevant class or stream

---

## UI and UX Rules

### Stream Visibility

If `class.level != secondary`:
- hide stream selection completely
- do not require stream in validation

If `class.level == secondary`:
- show stream selection
- require stream where the selected workflow depends on stream-bound subjects

### Table Scrolling

All result and report tables must support horizontal scrolling.

Required behavior:
- wrapper must use `overflow-x: auto`

### General UI

The interface must remain:
- clean
- SaaS-style
- responsive
- usable on mobile and desktop

---

## Student Report Features

### Term Report Section

The student report must display:
- subject list
- CA score
- exam score
- total score
- grade
- remark
- total score sum
- percentage
- grade summary
- overall position
- stream position (if applicable)
- subject positions

### Annual Report Section

The annual report must display:
- annual total
- annual percentage
- annual subject averages
- overall annual position
- stream annual position (if applicable)
- annual subject positions

Rules:
- Students must see only their own data
- Printable and downloadable layouts must remain clean

---

## Security and Audit

Required controls:
- role-based access control
- password hashing
- protected routes
- strict class-scope access for teachers
- student self-data-only access

Audit requirements:
- result upload tracking
- admin override logging
- override reason
- override timestamp
- user identity for override action

---

## Out of Scope

The following remain out of scope for V2.2:
- SMS notifications
- email notifications
- parent portal
- multi-school system
- advanced analytics

---

## Future Enhancements

Planned future improvements may include:
- configurable grading scales
- advanced branded PDF layouts
- multi-school SaaS support
- richer analytics and performance insights
