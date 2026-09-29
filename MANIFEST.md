# MarkTask
## A Local-First Productivity System for Knowledge Work

This document is the long-term vision. For the implemented alpha, supported features and limitations, see [README.md](README.md).

> Markdown first. Tasks second. Tools third.

---

# Executive Summary

MarkTask is a local-first productivity system built on top of Markdown, PARA, Obsidian, Python, and Dash.

The goal of MarkTask is not to create another isolated task management application. The goal is to establish a durable and portable operating system for personal knowledge work.

MarkTask combines:

- Project management
- Task management
- Knowledge management
- Kanban workflows
- Recurring activities
- Due dates
- Reminders
- Project documentation
- Meeting notes
- Decisions and context

Markdown files are the authoritative source of truth.

Obsidian, VS Code, Python, Dash, and any future applications are interfaces placed on top of those files. Every application should remain replaceable without losing the underlying information.

The primary design principle is:

> Data must outlive tools.

MarkTask therefore prioritizes:

- Open formats over proprietary formats
- Local ownership over cloud dependency
- Knowledge management over isolated task management
- Long-term durability over short-term convenience
- Portability over vendor lock-in
- Explicit structure over hidden application logic
- Recoverability over feature complexity

The first major implementation will be a local Python Dash application that scans the active projects in the PARA vault and provides an interactive dashboard across all active work.

The dashboard will aggregate tasks, deadlines, recurring activities, project statuses, and Kanban boards without replacing the Markdown files as the primary system of record.

---

# Vision

Most productivity tools assume that the user primarily manages tasks.

MarkTask assumes that the user manages knowledge, projects, responsibilities, and decisions, with tasks embedded in that context.

A task is only one component of a larger system consisting of:

- Projects
- Notes
- Research
- Documentation
- Decisions
- Meeting outcomes
- Follow-ups
- Waiting items
- Recurring responsibilities
- Deadlines
- Supporting material
- Historical context

Traditional task managers focus primarily on task execution.

MarkTask focuses on maintaining the complete context around the work.

The system should not only answer:

> What should I do today?

It should also help answer:

- Why am I doing this?
- Which project does this task support?
- Where did the task originate?
- What information is related to the task?
- What decisions have already been made?
- What work has already been completed?
- What am I waiting for?
- Which projects currently require attention?
- Which recurring responsibilities are approaching?
- Where can I find the supporting documentation?

MarkTask therefore combines task execution with project and knowledge context.

---

# Why MarkTask Exists

MarkTask emerged from a practical productivity problem.

The previous workflow relied heavily on Todoist for:

- Multiple concurrent projects
- Separate workflows or sections within each project
- Due dates
- Recurring tasks
- Kanban-style task organization
- Reminders and notifications
- Global task views
- Rapid task capture

This worked well functionally, but the system depended on access to an external cloud service.

In a restricted or offline environment, access to external applications and URLs cannot be assumed to remain available.

A blocked URL can make the complete productivity system inaccessible even though the underlying work and responsibilities continue.

This creates a structural weakness.

MarkTask is intended to remove that dependency.

---

# Problems Addressed by MarkTask

## SaaS Dependency

Cloud tools depend on conditions outside the user's control.

Potential failure points include:

- URL blocking
- Network restrictions
- Network or device policy changes
- Software approval requirements
- Vendor decisions
- Subscription changes
- Authentication problems
- Internet availability
- Service outages

A productivity system should not become unusable merely because a website is inaccessible.

MarkTask reduces this risk by keeping the source data in local Markdown files.

---

## Vendor Lock-In

Many productivity applications store information in proprietary formats or application-controlled databases.

Even where exports are possible, exports may not preserve:

- Internal links
- Task relationships
- Project structure
- Recurrence rules
- Comments
- Status history
- Custom fields
- Application-specific views

MarkTask seeks to minimize this dependency.

The primary information should remain readable without MarkTask, Obsidian, Dash, or any specific plugin.

---

## Fragmentation

Knowledge work is often distributed across multiple systems:

- Task managers
- Email
- Calendars
- OneNote
- Planner
- Local documents
- Project folders
- Wikis
- Meeting notes
- Documentation systems

This creates fragmentation between the task and the context required to complete the task.

A task might exist in one application while the following information exists elsewhere:

- Meeting notes
- Supporting analysis
- Previous decisions
- Relevant files
- Open questions
- Links to related projects

MarkTask seeks to bring the operational task and its knowledge context closer together.

---

## Loss of Context

Traditional task managers are good at recording short actions such as:

```text
Review project assumptions
```

However, the task alone does not explain:

- Which analysis should be reviewed
- Why the review is required
- What previous conclusions exist
- Which meeting created the task
- Which people or systems are involved
- Where the supporting files are stored

MarkTask treats the surrounding project note as part of the task system.

---

## Longevity

Markdown is plain text.

Plain text is:

- Human-readable
- Machine-readable
- Searchable
- Version-controllable
- Application-independent
- Easy to transform
- Easy to back up

Markdown files created today should remain readable even if the current applications are no longer available.

This is less certain for proprietary productivity databases.

---

# Core Philosophy

The files are the system.

Applications are interfaces.

The correct architecture is:

```text
Markdown files
      ↓
Parser and index
      ↓
Dashboard and other interfaces
```

The incorrect architecture is:

```text
Markdown files
      ↑
Proprietary dashboard database
```

The dashboard must not silently become the authoritative source of information.

If the dashboard is removed, the productivity system must continue to function.

This is the most important architectural principle of MarkTask.

---

# The MarkTask Principle

Every component must be replaceable.

If Obsidian becomes unavailable:

- The vault survives
- The notes remain readable
- The tasks remain readable
- The project folders remain available
- The files can be opened in VS Code or another editor

If Dash becomes unavailable:

- The vault survives
- The Markdown files remain authoritative
- A different dashboard can be developed
- Existing searches and scripts can continue to operate

If Python becomes unavailable:

- The vault survives
- Manual task management remains possible
- Another programming language can process the same files

If community plugins become unavailable:

- Standard Markdown remains readable
- Checkboxes remain readable
- Headings remain readable
- Tags remain readable
- Folder structures remain readable

If operating systems change:

- The files survive
- The data model remains portable
- The system can be rebuilt on another platform

The vault is the durable product.

Everything else is an interface.

---

# Why Markdown

Markdown is the foundation of MarkTask because it provides an appropriate balance between human readability and machine processing.

Markdown files can be:

- Written manually
- Read without specialized software
- Parsed by Python
- Displayed in Obsidian
- Edited in VS Code
- Searched using standard command-line tools
- Stored in Git
- Compared using diffs
- Transformed into other formats

Markdown does not provide every task-management feature natively.

However, Markdown provides something more fundamental:

> Control over the underlying data.

---

# Why PARA

PARA provides the organizational backbone for MarkTask.

The core structure is:

```text
1-Projects/
2-Areas/
3-Resources/
4-Archive/
```

The primary meanings are:

## Projects

Active work with a defined outcome or current objective.

Examples:

```text
1-Projects/
├── Website-Refresh/
├── Research-Notes/
├── Product-Launch/
├── Community-Event/
└── MarkTask/
```

## Areas

Ongoing responsibilities without a single completion date.

Examples:

```text
2-Areas/
├── Planning/
├── Knowledge-Management/
├── Software-Development/
└── Professional-Development/
```

## Resources

Reference material that may support multiple projects or areas.

Examples:

```text
3-Resources/
├── Python/
├── Statistics/
├── Research-Methods/
└── Data-Engineering/
```

## Archive

Completed or inactive material.

Examples:

```text
4-Archive/
├── Completed-Projects/
├── Previous-Reviews/
└── Historical-Analyses/
```

---

# Primary Scope

The initial MarkTask dashboard will focus on:

```text
1-Projects/
```

This directory represents active work and therefore contains the information most relevant to day-to-day execution.

The initial dashboard should not attempt to index the entire vault equally.

The first priority is to provide operational visibility across active projects.

Support for Areas, Resources, and Archive content may be added later where it provides clear value.

---

# Current Workload Model

The expected workload consists of:

- Approximately ten or more active projects
- Multiple states or Kanban columns per project
- Project-specific tasks
- Cross-project deadlines
- Recurring activities
- Follow-ups
- Waiting items
- Research tasks
- Meeting actions
- Documentation tasks
- Technical implementation work

Each project may contain several workflow states, such as:

```text
Inbox
Backlog
Next
In Progress
Waiting
Done
```

The challenge is not merely storing these tasks.

The challenge is maintaining a reliable overview across all projects without manually opening every project board.

---

# Current Pain Points

Without a central dashboard, important questions require manual review:

- What is due today?
- What is overdue?
- What is due this week?
- Which tasks are currently blocked?
- What am I waiting for?
- Which project has too many open tasks?
- Which projects have not changed recently?
- Which recurring tasks need to be generated?
- Which project should receive attention next?
- Where are the relevant project notes?
- Which tasks have no deadline?
- Which tasks exist outside a defined workflow?

The dashboard should make these questions directly answerable.

---

# Goal

The goal of MarkTask is to create a local-first personal operating system for knowledge work.

The system should provide:

- A stable project structure
- Durable task storage
- Global task visibility
- Kanban-style project execution
- Due-date management
- Recurring-task support
- Selective reminders
- Project context
- Searchable documentation
- Programmatic extensibility
- Minimal dependence on external services

The system should remain useful even if individual components become unavailable.

---

# Product Definition

MarkTask is not just a dashboard.

MarkTask consists of several layers:

```text
Layer 1: Markdown data model
Layer 2: PARA folder structure
Layer 3: Obsidian user interface
Layer 4: Community plugins
Layer 5: Python processing
Layer 6: Dash dashboard
Layer 7: Optional notification integration
```

Each higher layer depends on the lower layers.

The lower layers should not depend on the higher layers.

For example:

- The dashboard may depend on Markdown
- Markdown must not depend on the dashboard

This dependency direction protects portability.

---

# System Architecture

## High-Level Architecture

```text
Obsidian Vault
      ↓
File Discovery
      ↓
Markdown and Kanban Parser
      ↓
Normalized Task Model
      ↓
Project and Task Index
      ↓
Dash Application
      ↓
Optional Markdown Updates
```

The Obsidian vault remains the primary store.

The dashboard reads the vault, builds a temporary index, and presents the result through a local browser interface.

---

# Proposed Technical Flow

```text
1-Projects/
      ↓
Discover project folders and Markdown files
      ↓
Read Markdown content and frontmatter
      ↓
Extract tasks, statuses, dates, tags, and links
      ↓
Normalize records into a common task model
      ↓
Validate tasks and detect parsing issues
      ↓
Build in-memory or cached indexes
      ↓
Render interactive views in Dash
```

For write operations:

```text
User action in dashboard
      ↓
Validate requested change
      ↓
Identify source Markdown file
      ↓
Create safe and minimal text modification
      ↓
Write file atomically
      ↓
Reparse affected file
      ↓
Refresh dashboard state
```

---

# Source of Truth

The authoritative source is:

```text
Markdown files in the vault
```

The following are not authoritative:

- Dash component state
- Browser session state
- Temporary Python objects
- Cached indexes
- SQLite tables
- Generated summaries
- Notification history

These may improve performance or usability, but they must remain reproducible from the Markdown files.

---

# File Discovery

The initial scanner should recursively process:

```text
1-Projects/
```

The scanner should identify:

- Project directories
- Markdown files
- Kanban files
- Project overview files
- Tasks embedded in meeting notes
- Tasks embedded in general project notes

Files and directories may need configurable exclusions.

Example:

```yaml
exclude:
  - ".obsidian"
  - "attachments"
  - "templates"
  - "generated"
```

The scanner should not make assumptions solely based on filenames where the structure can be identified explicitly.

---

# Project Identification

A project can initially be defined as a direct child directory of:

```text
1-Projects/
```

Example:

```text
1-Projects/
├── Website-Refresh/
├── MarkTask/
└── Product-Launch/
```

Each directory represents one active project.

A later implementation may support explicit project metadata:

```yaml
---
type: project
status: active
owner: Example User
created: 2026-09-28
---
```

Frontmatter is optional for the first implementation but may improve reliability later.

---

# Proposed Project Structure

A project should remain self-contained where practical.

Example:

```text
1-Projects/
└── MarkTask/
    ├── MarkTask.md
    ├── Kanban.md
    ├── Tasks.md
    ├── Decisions.md
    ├── Meetings/
    ├── Research/
    └── Implementation/
```

Not every project needs every file or directory.

The structure should remain lightweight and adaptable.

---

# Task Standardization

Automation requires consistent task syntax.

The initial task format should remain compatible with standard Markdown checkboxes.

Basic task:

```markdown
- [ ] Prepare project slides
```

Completed task:

```markdown
- [x] Prepare project slides
```

Task with due date:

```markdown
- [ ] Prepare project slides 📅 2026-10-02
```

Task with recurrence:

```markdown
- [ ] Review project status 📅 2026-10-02 🔁 every week
```

Task with project or context tags:

```markdown
- [ ] Review project status 📅 2026-10-02 🔁 every week #marktask
```

Compact example:

```markdown
- [ ] Prepare project slides 📅 2026-10-02 🔁 every month #project
```

The exact syntax must be documented and tested before more advanced features are implemented.

---

# Normalized Task Model

Regardless of how a task appears in a Markdown file, the parser should produce a normalized internal representation.

Conceptual example:

```python
{
    "id": "stable-task-id",
    "description": "Prepare project slides",
    "completed": False,
    "project": "Website-Refresh",
    "status": "In Progress",
    "due_date": "2026-10-02",
    "recurrence": "every month",
    "tags": ["project"],
    "source_file": "1-Projects/Website-Refresh/Kanban.md",
    "source_line": 42,
    "created_at": None,
    "completed_at": None
}
```

The internal model may contain additional technical fields, but the primary information must remain recoverable from the Markdown source.

---

# Task Identity

Stable task identity is a non-trivial design problem.

Line numbers are not stable because tasks move when files are edited.

Task text is not stable because descriptions change.

Possible approaches include:

## Generated Task Identifier

```markdown
- [ ] Prepare project slides ^task-a81f2c
```

Advantages:

- Stable across file movements
- Explicit
- Easy to reference

Disadvantages:

- Adds visible technical syntax
- Requires ID management

## Metadata Comment

```markdown
- [ ] Prepare project slides <!-- task-id: a81f2c -->
```

Advantages:

- Less visible in rendered Markdown
- Stable

Disadvantages:

- Slightly more complex parsing
- Comments may be altered by other tools

## Derived Identifier

The identifier could be calculated from:

- File path
- Task text
- Surrounding heading
- Creation timestamp

Advantages:

- No additional syntax

Disadvantages:

- Changes when tasks move or text changes
- More difficult to reconcile

The first version may avoid stable IDs where they are not yet necessary. Stable IDs should be introduced before advanced synchronization, recurrence history, or cross-file dependency tracking.

---

# Kanban Model

Existing Obsidian Kanban boards should remain usable.

A simplified board may look like:

```markdown
## Inbox

- [ ] Capture new requirement

## Backlog

- [ ] Define task schema

## Next

- [ ] Implement file scanner

## In Progress

- [ ] Create architecture document

## Waiting

- [ ] Review software availability

## Done

- [x] Select project name
```

The heading defines the task status.

The task remains a standard Markdown checkbox item.

This structure is readable:

- In Obsidian
- In VS Code
- In a terminal
- Through Python
- Without the Kanban plugin

---

# Recommended Kanban Columns

A default workflow could use:

```text
Inbox
Backlog
Next
In Progress
Waiting
Done
```

The meanings should be explicit.

## Inbox

Newly captured tasks that have not been reviewed.

## Backlog

Valid tasks that are not currently prioritized.

## Next

Tasks selected for near-term execution.

## In Progress

Tasks currently being worked on.

## Waiting

Tasks blocked by another person, system, decision, or dependency.

## Done

Completed tasks.

Projects may use adjusted workflows, but excessive variation makes global aggregation more difficult.

---

# Dashboard Objectives

## Global Today View

The Today view should aggregate all incomplete tasks due today across active projects.

The view should include:

- Task description
- Project
- Status
- Due date
- Source file
- Direct link to the source note
- Optional priority
- Optional tags

This should become the primary daily operational view.

---

## Overdue View

The Overdue view should identify incomplete tasks with due dates before the current date.

The view should support:

- Sorting by oldest due date
- Grouping by project
- Filtering by status
- Excluding explicitly deferred tasks
- Opening the source file
- Rescheduling where safe editing is supported

Overdue tasks should be treated as review items, not merely as failures.

The user may decide to:

- Complete the task
- Reschedule the task
- Remove the due date
- Move the task to the backlog
- Delete the task
- Mark the task as waiting
- Archive the related project

---

## Upcoming View

The Upcoming view should show tasks within configurable date ranges.

Examples:

```text
Next 7 days
Next 14 days
Next 30 days
```

The view should support grouping by:

- Due date
- Project
- Status
- Tag

---

## Waiting View

The Waiting view should aggregate tasks located in Waiting columns or explicitly marked as waiting.

This view is important because many knowledge-work tasks depend on:

- Responses
- Decisions
- Access
- Data
- Reviews
- Approvals
- Technical support

Optional future metadata may include:

```markdown
- [ ] Receive review feedback ⏳ 2026-10-05 #waiting
```

or:

```yaml
waiting_for: review feedback
follow_up: 2026-10-05
```

The first implementation should avoid excessive syntax and may derive waiting status from the Kanban column.

---

## Recurring View

The Recurring view should show:

- Recurring task definition
- Project
- Recurrence rule
- Current due date
- Next expected occurrence
- Last completion, if available
- Parsing or recurrence errors

Recurring tasks require careful design because the system must avoid:

- Duplicate occurrences
- Lost completion history
- Infinite task generation
- Incorrect interpretation of recurrence rules

---

## Project Portfolio View

The Project Portfolio view should provide one summary row or card per active project.

Possible metrics include:

- Open task count
- Overdue task count
- Tasks due this week
- Waiting task count
- In-progress task count
- Completed task count
- Most recent file activity
- Next due date

These metrics should provide signals rather than performance scores.

The purpose is to identify projects that require attention, not to evaluate personal performance.

---

## Project Detail View

Selecting a project should open a detailed project view containing:

- Project summary
- Project path
- Open tasks
- Kanban board
- Upcoming deadlines
- Waiting items
- Recurring tasks
- Related notes
- Recent activity
- Links to source files

The detail view should retain a direct connection to the underlying Markdown files.

---

## Global Kanban View

A global Kanban view could combine tasks across projects.

Example columns:

```text
Inbox
Next
In Progress
Waiting
Done
```

Each card should clearly display its project.

Potential card fields:

```text
Task description
Project
Due date
Tags
Source file
```

The global board should not remove tasks from their original project context.

---

## Search and Filtering

The dashboard should support filtering by:

- Project
- Status
- Due date
- Tag
- Task text
- Source file
- Completion state
- Recurrence
- Waiting state

Search results should link back to the source Markdown file wherever possible.

---

# Dashboard Layout

A possible initial layout is:

```text
┌───────────────────────────────────────────────────────────────┐
│ MarkTask                                                     │
├───────────────┬───────────────────────────────────────────────┤
│ Navigation    │ Summary Cards                                 │
│               │ Today | Overdue | Waiting | Projects          │
│ Dashboard     ├───────────────────────────────────────────────┤
│ Today         │ Filters                                       │
│ Upcoming      ├───────────────────────────────────────────────┤
│ Overdue       │ Main View                                     │
│ Waiting       │                                               │
│ Recurring     │ Task table, Kanban board, or project cards    │
│ Projects      │                                               │
│ Search        │                                               │
│ Settings      │                                               │
└───────────────┴───────────────────────────────────────────────┘
```

The interface should prioritize clarity over decorative complexity.

---

# Interaction Model

## Read Operations

Initial read operations should include:

- Scan project directories
- Parse Markdown files
- Extract tasks
- Detect Kanban columns
- Identify due dates
- Identify recurrence rules
- Extract tags
- Display source locations
- Create aggregate views

Read operations are lower risk and should be implemented first.

---

## Write Operations

Later write operations may include:

- Complete a task
- Reopen a task
- Change due date
- Move task between Kanban columns
- Create a task
- Edit task text
- Generate the next recurring task
- Add a tag
- Move a task to another project

Write operations require stricter controls because an incorrect update could damage a Markdown file.

---

# Safe Markdown Writing

Safe writing should follow the principles below.

## Minimal Modification

Change only the exact line or block required.

Do not rewrite the complete file unless necessary.

## Atomic Writes

A file update should:

1. Create the new content separately
2. Validate that the new content can be parsed
3. Replace the original file atomically
4. Preserve a recoverable previous version where appropriate

## Conflict Detection

Before writing, verify that the source file has not changed since it was read.

If the file has changed, reparse it before applying the update.

## Backup and Version Control

The vault should be backed up through an approved mechanism.

Where Git is available and approved, Git can provide:

- Change history
- Diffs
- Recovery
- Auditability of local modifications

Git should not be treated as a substitute for an appropriate backup strategy.

---

# Recurring Tasks

Recurring tasks are a central requirement.

Examples include:

- Weekly project review
- Monthly status update
- Quarterly preparation work
- Periodic documentation review
- Regular follow-ups
- Maintenance activities

Example syntax:

```markdown
- [ ] Review MarkTask project status 📅 2026-10-02 🔁 every week
```

Possible recurrence rules include:

```text
every day
every weekday
every week
every month
every quarter
every year
```

More advanced rules could later include:

```text
every first Monday
every last working day of the month
every 3 weeks
```

The initial implementation should support a small, explicit set of recurrence rules.

---

# Recurrence Strategy

Two broad recurrence strategies are possible.

## Generate on Completion

When a recurring task is completed, the next occurrence is created.

Advantages:

- Avoids large numbers of future tasks
- Mirrors common task-manager behavior
- Completion history remains explicit

Disadvantages:

- Requires write support
- Requires stable recurrence handling

## Generate in Advance

Future occurrences are generated up to a configured horizon.

Advantages:

- Upcoming workload is visible
- Does not require completion to create the next occurrence

Disadvantages:

- Can create duplicates
- Requires reconciliation
- Can clutter the vault

The preferred initial approach is:

> Generate the next occurrence when the current task is completed.

The implementation must ensure idempotency so that the same next occurrence cannot be generated multiple times.

---

# Reminders and Notifications

Notifications are the weakest part of a purely Markdown-based system.

Markdown can store:

- Due dates
- Reminder dates
- Priorities
- Recurrence rules

Markdown cannot independently display a Windows notification.

A running process or integration is required.

---

# Notification Philosophy

MarkTask should not become notification-driven.

The primary productivity model should be:

```text
Daily review
+
Weekly review
+
Focused execution
```

Notifications should be reserved for events where missing the task has a meaningful consequence.

Examples:

- Hard submission deadlines
- Project deadlines
- Time-sensitive commitments
- Time-sensitive follow-ups
- Scheduled operational activities

Routine tasks should normally appear in the Today or Upcoming view without generating interruptions.

---

# Notification Options

## Dashboard-Based Notifications

The Dash application can highlight urgent tasks while it is open.

Examples:

- Overdue indicator
- Due-today banner
- Upcoming deadline warning

Limitation:

- No notification when the dashboard is closed

## Local Windows Notifications

A Python process could generate Windows notifications.

Limitation:

- The process must run
- Required packages may not be available
- Device policies may restrict automatic execution

## Windows Task Scheduler

A scheduled script could scan the vault periodically and trigger notifications.

Limitation:

- Scheduled tasks may require permissions or approval
- Deployment becomes more complex
- The notification process is separate from Dash

## Outlook or Calendar Integration

Hard deadlines could be mirrored into Outlook or the calendar.

Limitation:

- Creates a second store
- Requires synchronization logic
- Can create duplicated maintenance

The initial MarkTask implementation should treat notifications as an optional extension.

---

# Recommended Reminder Strategy

Use three levels.

## Level 1: Dashboard Visibility

For normal tasks:

- Today
- Upcoming
- Overdue
- Waiting

## Level 2: Visual Urgency

For important tasks:

- Priority indicator
- Highlighted due date
- Dashboard warning

## Level 3: External Reminder

For hard deadlines only:

- Outlook reminder
- Calendar reminder
- Windows notification

This prevents excessive notifications while preserving protection for important commitments.

---

# Technology Stack

## Python

Python will provide:

- File scanning
- Markdown parsing
- Data normalization
- Recurrence logic
- Validation
- Dashboard callbacks
- Optional notifications

The implementation should use standard library functionality where practical.

---

## Dash

Dash will provide the local interactive web interface.

It is suitable for:

- Tables
- Filters
- Cards
- Navigation
- Charts
- Interactive controls
- Callback-based updates
- Local browser delivery

The dashboard should initially run only on:

```text
localhost
```

It should not require external hosting.

---

## Dash Bootstrap Components

Potential use:

```python
dash-bootstrap-components
```

This can support:

- Responsive layouts
- Navigation
- Cards
- Forms
- Tabs
- Modals
- Consistent visual styling

The project should avoid unnecessary visual complexity.

---

## Markdown Parsing

Potential libraries include:

```python
markdown-it-py
python-frontmatter
```

Standard Python functionality may also be used:

```python
pathlib
re
datetime
dataclasses
```

The parser should be designed around an explicit and tested task grammar rather than an uncontrolled collection of regular expressions.

---

## File Monitoring

Potential library:

```python
watchdog
```

This could allow the dashboard to detect changes in the vault.

However, file monitoring should not be required for the first version.

A manual refresh button or periodic rescan is acceptable initially.

---

## Data Processing

Potential library:

```python
pandas
```

Pandas may be useful for:

- Filtering
- Grouping
- Sorting
- Summary metrics
- Task tables

The core domain model should not depend exclusively on DataFrames. Explicit dataclasses or domain objects may provide clearer logic for tasks and projects.

---

## Cache Layer

The initial implementation can use:

```text
In-memory indexes
```

A later implementation may introduce:

```text
SQLite cache
```

The cache may improve:

- Startup performance
- Search
- Change tracking
- Recurrence history
- Task reconciliation

The cache must remain disposable and rebuildable from the Markdown files.

---

# Proposed Package Structure

```text
marktask/
├── README.md
├── pyproject.toml
├── src/
│   └── marktask/
│       ├── __init__.py
│       ├── app.py
│       ├── config.py
│       ├── domain/
│       │   ├── task.py
│       │   ├── project.py
│       │   └── recurrence.py
│       ├── parsing/
│       │   ├── scanner.py
│       │   ├── markdown.py
│       │   ├── kanban.py
│       │   └── frontmatter.py
│       ├── services/
│       │   ├── indexer.py
│       │   ├── task_service.py
│       │   ├── recurrence_service.py
│       │   └── file_writer.py
│       ├── repository/
│       │   ├── vault_repository.py
│       │   └── cache_repository.py
│       ├── dashboard/
│       │   ├── layout.py
│       │   ├── callbacks.py
│       │   ├── components.py
│       │   └── pages/
│       │       ├── home.py
│       │       ├── today.py
│       │       ├── projects.py
│       │       ├── kanban.py
│       │       └── recurring.py
│       └── notifications/
│           ├── base.py
│           └── windows.py
├── tests/
│   ├── fixtures/
│   ├── test_markdown_parser.py
│   ├── test_kanban_parser.py
│   ├── test_recurrence.py
│   └── test_file_writer.py
└── docs/
    ├── architecture.md
    ├── task-syntax.md
    └── decisions/
```

This structure is a proposal and may be simplified for the first implementation.

---

# Configuration

MarkTask should use an explicit configuration file.

Example:

```yaml
vault_path: "C:/Users/user/Documents/Obsidian"

projects_directory: "1-Projects"

archive_directory: "4-Archive"

kanban:
  default_columns:
    - Inbox
    - Backlog
    - Next
    - In Progress
    - Waiting
    - Done

tasks:
  completed_markers:
    - x
    - X

dashboard:
  host: "127.0.0.1"
  port: 8050
  auto_refresh_seconds: 60

notifications:
  enabled: false
```

Machine-specific configuration should not be hard-coded into the application.

---

# Portability Requirements

MarkTask should remain portable at several levels.

## Data Portability

All essential information must remain in Markdown.

## Editor Portability

The vault should be usable in:

- Obsidian
- VS Code
- Neovim
- Other Markdown editors

## Operating System Portability

Core parsing and dashboard logic should not unnecessarily depend on Windows-specific behavior.

Notifications may require platform-specific adapters.

## Application Portability

The application should be able to rebuild its state by scanning the vault.

## Plugin Portability

If a plugin-specific syntax is used, it should degrade gracefully into readable Markdown.

---

# Degraded Operation

MarkTask should support several operating modes.

## Full Mode

```text
Obsidian
+
Kanban plugin
+
Tasks plugin
+
Python
+
Dash
+
Optional notifications
```

## Obsidian-Only Mode

```text
Obsidian
+
Markdown
+
Kanban plugin
```

The dashboard is unavailable, but project work remains possible.

## VS Code Mode

```text
VS Code
+
Markdown files
```

Tasks, notes, and Kanban headings remain editable.

## Plain-Text Mode

```text
Any text editor
+
Markdown files
```

The system loses convenience but not the underlying information.

This degraded-operation model is a key resilience feature.

---

# Security and Privacy

MarkTask is intended to run locally.

The default implementation should:

- Bind only to localhost
- Avoid external network calls
- Avoid telemetry
- Avoid cloud synchronization unless separately configured
- Avoid transmitting vault content
- Store configuration locally
- Keep temporary indexes local

The dashboard should not expose the vault to the wider network by default.

Any future deployment beyond localhost requires separate security analysis.

---

# Data Classification

MarkTask is a technical mechanism, not an override of organizational data-handling policies.

The user remains responsible for ensuring that information stored in the vault is appropriate for the approved storage location.

Local-first does not automatically mean approved for all information categories.

The implementation should therefore:

- Avoid copying unnecessary data
- Avoid storing credentials or secrets
- Avoid embedding database passwords
- Keep configuration separate from content
- Support exclusions for restricted directories
- Avoid exporting vault content to external systems by default

---

# Reliability Requirements

The system should prefer correctness over convenience.

Key requirements include:

- A parser failure must not modify source files
- An unknown task syntax must remain untouched
- Write operations must be validated
- Recurrence generation must be idempotent
- Duplicate task creation must be prevented
- Errors must identify the affected source file
- A malformed file should not stop the complete scan
- Cache corruption must not affect source files
- The index must be rebuildable

---

# Observability

MarkTask should provide clear information about its own operation.

Useful diagnostics include:

- Number of scanned files
- Number of parsed tasks
- Number of parsing warnings
- Number of excluded files
- Last successful scan
- Files changed since the previous scan
- Recurrence errors
- Write failures
- Configuration errors

Logs should avoid unnecessarily reproducing complete task or note content.

---

# Testing Strategy

The parser and writer require strong automated testing.

## Parser Tests

Test cases should include:

- Basic tasks
- Completed tasks
- Due dates
- Recurring tasks
- Tags
- Indented tasks
- Kanban columns
- Mixed Markdown content
- Malformed metadata
- Unicode content
- Empty files
- Large files

## Recurrence Tests

Test cases should include:

- Daily recurrence
- Weekly recurrence
- Monthly recurrence
- Quarterly recurrence
- Yearly recurrence
- Month-end behavior
- Duplicate prevention
- Completion-triggered generation

## Writer Tests

Test cases should include:

- Completing a task
- Reopening a task
- Changing a due date
- Moving a task
- Preserving unrelated content
- Preserving line endings
- Conflict detection
- Atomic replacement
- Recovery after failed validation

## Integration Tests

Test cases should include:

- Scanning a sample vault
- Building the project index
- Rendering dashboard views
- Editing a task and reparsing the file
- Handling external file changes

---

# Implementation Principles

## Start Read-Only

The first usable version should not modify the vault.

It should:

- Scan projects
- Parse tasks
- Show Today
- Show Overdue
- Show Upcoming
- Show Waiting
- Show project summaries
- Link to source files

This creates immediate value with limited risk.

## Add Writes Incrementally

Recommended order:

1. Complete and reopen tasks
2. Change due dates
3. Create tasks
4. Move tasks between columns
5. Generate recurring tasks
6. Add drag-and-drop Kanban interactions

## Prefer Explicit Behavior

Avoid hidden automation.

When MarkTask modifies a file, the operation should be clear and predictable.

## Preserve Manual Control

All files should remain manually editable.

MarkTask must not require its own interface for routine maintenance.

---

# Implementation Phases

## Phase 1: Data Discovery

Objectives:

- Define folder conventions
- Define task syntax
- Define Kanban status conventions
- Scan active project files
- Report unsupported structures

Deliverable:

```text
CLI scan report
```

---

## Phase 2: Read-Only Task Index

Objectives:

- Parse tasks
- Normalize task records
- Group tasks by project
- Detect due dates
- Detect recurrence rules
- Detect Kanban status

Deliverable:

```text
Structured task index
```

---

## Phase 3: Basic Dash Dashboard

Objectives:

- Project overview
- Today view
- Upcoming view
- Overdue view
- Waiting view
- Search and filters
- Source-file links

Deliverable:

```text
Local read-only dashboard
```

---

## Phase 4: Safe Task Updates

Objectives:

- Complete tasks
- Reopen tasks
- Change due dates
- Validate write operations
- Introduce conflict detection

Deliverable:

```text
Controlled Markdown editing
```

---

## Phase 5: Recurring Tasks

Objectives:

- Parse supported recurrence rules
- Generate the next occurrence
- Prevent duplicates
- Preserve recurrence history where required
- Display recurrence errors

Deliverable:

```text
Reliable recurring-task engine
```

---

## Phase 6: Interactive Kanban

Objectives:

- Display project boards
- Move cards between columns
- Support global Kanban views
- Preserve source formatting
- Validate concurrent changes

Deliverable:

```text
Interactive Markdown-backed Kanban board
```

---

## Phase 7: Notifications

Objectives:

- Define reminder syntax
- Add notification evaluation
- Support selected Windows notifications or approved integrations
- Avoid duplicate reminders
- Keep notifications optional

Deliverable:

```text
Optional local reminder service
```

---

# Minimum Viable Product

The minimum viable product should include:

- Configuration of the vault path
- Discovery of projects under `1-Projects`
- Parsing of standard Markdown tasks
- Recognition of Kanban columns
- Recognition of due dates
- Recognition of supported recurrence syntax
- Today view
- Overdue view
- Upcoming view
- Waiting view
- Project overview
- Search and filtering
- Links to source files
- Manual refresh

The minimum viable product should be read-only.

A read-only dashboard provides substantial value while protecting the vault during early development.

---

# Non-Goals

MarkTask is not initially intended to:

- Replace Obsidian
- Replace Markdown
- Replace Outlook
- Replace Microsoft Planner for team collaboration
- Become a multi-user project management platform
- Support complex resource planning
- Track employee performance
- Require cloud infrastructure
- Require a mobile application
- Create a proprietary task database
- Synchronize with every external productivity system
- Automate every possible workflow

Scope control is important.

MarkTask should first become a reliable personal productivity interface.

---

# Limitations

## Notifications Require a Running Component

Markdown files cannot create notifications independently.

A Python process, scheduled task, Outlook integration, or similar mechanism is required.

## Obsidian Plugins May Become Unavailable

Community plugins may stop receiving updates or may become incompatible with future Obsidian versions.

Essential data should therefore remain readable without plugins.

## Dashboard Availability Depends on Python

The dashboard requires an available Python environment and the necessary packages.

The Markdown system remains usable if the dashboard cannot run.

## Package Installation May Be Restricted

Restricted environments may block package downloads or installation.

Dependencies should therefore be:

- Minimal
- Well established
- Explicitly documented
- Lockable to known versions

## Drag-and-Drop Is Not Trivial

A visual card movement must be translated into a safe modification of a Markdown file.

This requires:

- Stable task identification
- Conflict detection
- File validation
- Careful preservation of unrelated content

## Markdown Is Flexible but Ambiguous

Different Markdown styles may represent similar information in different ways.

Reliable automation requires conventions.

## Multi-Device Synchronization Is Outside the Initial Scope

The initial design assumes a locally accessible vault.

Synchronization between devices introduces additional concerns such as conflicts and approved storage locations.

## Local-First Does Not Eliminate Backup Requirements

Local files can still be:

- Deleted
- Corrupted
- Overwritten
- Lost through hardware failure

A separate approved backup strategy remains necessary.

---

# Risks

## Excessive Plugin Dependency

If essential information exists only in a plugin's internal data, portability is reduced.

Mitigation:

- Prefer standard Markdown
- Keep plugin count low
- Document plugin-specific syntax
- Test degraded operation

## Excessive Custom Syntax

Too much metadata can make notes difficult to read manually.

Mitigation:

- Use a minimal task grammar
- Add metadata only where it provides clear value
- Keep task lines human-readable

## Dashboard Becoming the Real Source of Truth

Convenient interfaces may gradually introduce data that exists only in the application database.

Mitigation:

- Require all essential data to be written back to Markdown
- Treat caches as disposable
- Test full index rebuilds

## File Corruption

Incorrect write logic may damage Markdown files.

Mitigation:

- Start read-only
- Use atomic writes
- Use Git or another approved history mechanism
- Validate changed files
- Test writers heavily

## Scope Expansion

The project could expand into a full project-management platform.

Mitigation:

- Maintain explicit non-goals
- Prioritize the personal workflow
- Require clear value for each feature
- Avoid team collaboration features in the initial architecture

## Maintenance Burden

A custom system requires maintenance.

Mitigation:

- Keep architecture simple
- Minimize dependencies
- Use automated tests
- Prefer standard formats
- Avoid unnecessary infrastructure

---

# Decision Framework

New MarkTask features should be evaluated using the following questions:

1. Does the feature improve execution or project visibility?
2. Can the essential data remain in Markdown?
3. Does the feature introduce vendor lock-in?
4. Does the feature remain useful without Obsidian?
5. Does the feature increase maintenance disproportionately?
6. Can the feature be implemented without risking source files?
7. Is the feature necessary for the personal workflow?
8. Can the feature degrade gracefully if unavailable?

A feature should not be added merely because it is technically possible.

---

# Success Criteria

MarkTask is successful if it provides a reliable answer to the following questions:

- What should I work on today?
- What is overdue?
- What is due soon?
- What am I waiting for?
- Which projects require attention?
- Which recurring activities are approaching?
- Where is the context for each task?
- Can I continue working if Obsidian becomes unavailable?
- Can I rebuild the dashboard entirely from the Markdown vault?
- Can I switch editors without migrating the underlying data?

The project is not successful merely because the dashboard looks polished.

Correctness, portability, and practical usefulness matter more than visual complexity.

---

# Long-Term Vision

MarkTask should become a personal operating system for knowledge work.

The final system should connect:

```text
Projects
+
Tasks
+
Notes
+
Decisions
+
Meetings
+
Research
+
Recurring responsibilities
+
Deadlines
```

without hiding the information inside a proprietary platform.

The Python Dash application is not the product.

Obsidian is not the product.

The Kanban plugin is not the product.

The product is the durable combination of:

- Knowledge
- Projects
- History
- Decisions
- Tasks
- Context

stored in an open and accessible format.

---

# Long-Term Possibilities

Potential future capabilities include:

- Project health summaries
- Inbox processing
- Weekly review workflows
- Calendar-based task views
- Dependency tracking
- Stale-task detection
- Project archival workflows
- Command-line interfaces
- VS Code integration
- Local search
- Local AI-assisted task classification
- Automated project summaries
- Git-based activity views
- Import tools for Todoist exports
- Export tools for Planner or other systems
- Optional approved integrations

These are possible extensions, not initial requirements.

---

# Relationship Between MarkTask and Obsidian

Obsidian provides a strong current interface because it supports:

- Markdown editing
- Backlinks
- Search
- Folder navigation
- Kanban rendering through plugins
- Task queries through plugins
- Local vaults

However, MarkTask must not be defined as an Obsidian-only system.

The relationship is:

```text
MarkTask = productivity architecture
Obsidian = one interface for MarkTask
```

If Obsidian becomes unavailable, the architecture remains valid.

---

# Relationship Between MarkTask and VS Code

VS Code is the primary fallback interface.

Because the source files are Markdown, VS Code can provide:

- File navigation
- Markdown editing
- Search
- Regular-expression search
- Git integration
- Terminal access
- Python development
- Extension-based Markdown previews

Some advanced Obsidian functionality may be unavailable, but the essential information remains accessible.

The fallback path is therefore:

```text
Obsidian unavailable
      ↓
Open vault folder in VS Code
      ↓
Continue working with Markdown files
```

---

# Relationship Between MarkTask and Microsoft Products

Microsoft products may still provide value where they have clear strengths.

Examples:

- Outlook for selected hard reminders
- Calendar for scheduled commitments
- Planner for collaborative team boards
- Microsoft To Do for approved Microsoft-native task workflows

MarkTask does not need to reject Microsoft products.

The distinction is:

- MarkTask owns the personal productivity architecture
- External products provide optional supporting capabilities

Essential project knowledge and task context should not depend entirely on an external product.

---

# Daily Workflow

A possible daily workflow is:

## Start of Day

1. Open the MarkTask dashboard
2. Review overdue items
3. Review today's tasks
4. Review waiting items requiring follow-up
5. Select realistic tasks for active execution

## During the Day

1. Capture new tasks in the relevant project or inbox
2. Move tasks between Kanban states
3. Add context to project notes
4. Complete or reschedule tasks
5. Use external reminders only for hard commitments

## End of Day

1. Review incomplete in-progress tasks
2. Move blocked tasks to Waiting
3. Reschedule tasks where necessary
4. Confirm that important context is captured
5. Clear or review the inbox

---

# Weekly Review

A weekly review should include:

- Review all active projects
- Review overdue tasks
- Review waiting tasks
- Review recurring activities
- Process project inboxes
- Confirm next actions
- Archive completed projects
- Identify projects without a clear next action
- Review upcoming deadlines
- Remove obsolete tasks

The dashboard should eventually support this workflow directly.

---

# Design Statement

MarkTask is not intended to maximize the number of features.

MarkTask is intended to maximize:

- Durability
- Clarity
- Control
- Portability
- Recoverability
- Context
- Execution quality

The system should remain understandable without specialized knowledge of its implementation.

A Markdown file should still make sense when opened directly.

---

# Final Architecture

The intended architecture can be summarized as:

```text
PARA
+
Markdown
+
Obsidian
+
Kanban
+
Tasks
+
Python
+
Dash
+
Optional notifications
```

The dependency hierarchy is:

```text
Knowledge and tasks
      ↓
Markdown
      ↓
PARA structure
      ↓
Obsidian and VS Code
      ↓
Python processing
      ↓
Dash dashboard
      ↓
Optional integrations
```

Each lower layer is more durable than the layers above it.

---

# Final Principle

> The files matter more than the tools.

Any individual component should be replaceable without losing:

- Knowledge
- Tasks
- History
- Decisions
- Project structure
- Context

MarkTask is therefore not merely a task manager.

MarkTask is a Markdown-based productivity architecture designed to remain useful even when the surrounding applications, plugins, vendors, and technical environments change.