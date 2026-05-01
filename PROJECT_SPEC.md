# 🎓 School Academic Management System (SAMS)

## 🧠 Project Overview

This is a role-based web application designed for managing student academic results in a school environment that includes Nursery, Primary, and Secondary levels.

The system allows:
- Admins to manage school structure, users, and academic sessions
- Teachers to upload and manage results for assigned classes
- Students to securely view and download their report cards

The system is built to be scalable, secure, and flexible for different grading systems across educational levels.

---

## 🎯 Core Goals

- Centralized result management system for schools
- Role-based access control (Admin, Teacher, Student)
- Flexible result structure for different class levels
- Secure authentication and data protection
- Simple and responsive UI for all users

---

## 👥 User Roles

### 🔴 Admin
Responsible for full system control.

Capabilities:
- Create and manage teachers
- Create classes (Nursery, Primary, Secondary)
- Assign teachers to classes
- Add/import students
- Assign students to classes
- Manage academic sessions (e.g. 2025/2026)
- Lock/unlock result publication
- View all system data

---

### 🟡 Teacher
Responsible for academic data entry.

Capabilities:
- View assigned classes only
- Upload student results
- Edit results before final lock
- Bulk upload results (CSV supported)
- View class student list

Restrictions:
- Cannot access other classes
- Cannot modify system structure

---

### 🟢 Student
End user.

Capabilities:
- Login with student ID
- View personal report card
- Filter results by term/session
- Download/print report cards

---

## 🏫 Academic Structure

The system supports:

- Nursery (Nursery 1–2)
- Primary (Primary 1–6)
- Secondary (JSS1–SS3)

Each class contains:
- Students
- Assigned teachers
- Subjects
- Results per term

---

## 📊 Result System Design (Flexible)

Instead of separate tables per level, a single flexible structure is used.

### Key idea:
Results are stored in a generic format with flexible metadata support.

Each result includes:
- Score (optional)
- Grade (optional)
- Remark (optional)
- Meta-data JSON field (for custom grading systems)

### Examples of flexibility:
- Nursery: behavior, attendance, comments
- Primary: test scores + exam + total
- Secondary: CA + exam + final score

---

## 🧾 Core Features

### Authentication
- Role-based login system
- Password hashing
- Session management

### Admin Features
- Full system control dashboard
- Class and subject management
- Student and teacher management
- Result approval and locking

### Teacher Features
- Class-specific dashboard
- Result upload system
- Result editing before lock
- CSV upload support

### Student Features
- Secure result viewing
- Report card display
- Downloadable results

---

## 🗄️ Database Overview

Core tables:
- users
- students
- teachers
- classes
- subjects
- results (flexible JSON support)
- sessions
- class_teacher_map

---

## 🔐 Security Model

- Role-Based Access Control (RBAC)
- Password hashing
- Route protection per role
- Teachers restricted to assigned classes
- Admin override control

---

## ⚙️ Automation Features

- Automatic grade calculation from scores
- Auto student ID generation
- Session-based result grouping
- Class filtering by teacher assignment

---

## 🎨 UI Design Philosophy

- Clean SaaS-style interface
- Sidebar-based dashboards (Admin/Teacher)
- Minimal design for speed and usability
- Mobile-friendly student interface

---

## 🚀 Future Improvements (V2+)

- Student profile images
- PDF report card generation
- Parent portal access
- Notification system (SMS/email)
- Advanced analytics dashboard