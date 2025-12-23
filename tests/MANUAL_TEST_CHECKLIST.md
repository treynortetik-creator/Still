# Manual Testing Checklist for MVP

## Pre-Deployment Testing

Run through this checklist before deploying to production or inviting beta users.

---

## Registration & Login

### Registration
- [ ] Register with valid email and password
- [ ] Verify email format is validated
- [ ] Verify password minimum length enforced (8+ characters)
- [ ] Try registering with same email (should fail with clear error)
- [ ] After registration, automatically logged in

### Login
- [ ] Login with correct credentials
- [ ] Try login with wrong password (should fail with clear error)
- [ ] Try login with non-existent email (should fail)
- [ ] After login, redirected to upload page

### Session Management
- [ ] Logout and verify redirected to login page
- [ ] After logout, can't access protected pages (library, upload, etc.)
- [ ] Session persists on page refresh (token stored)

---

## File Upload & Processing

### Upload Interface
- [ ] Upload page loads correctly
- [ ] Persona dropdown populated with 3 options
- [ ] Asset type checkboxes work (LinkedIn, Blog)
- [ ] Asset quantity selectors work
- [ ] Magic words textarea accepts input
- [ ] Raw text option works (paste text instead of file)

### File Upload Test
- [ ] Upload video file (MP4, ~5 minutes)
- [ ] Enter magic words: "SafelyYou, Q4, ROI, DON"
- [ ] Select persona: CEO of Long-Term Care
- [ ] Select assets: 3 LinkedIn posts, 1 blog post
- [ ] Click "Upload & Process"
- [ ] Redirected to status page with job ID

### Status Page
- [ ] Progress bar displays and updates
- [ ] Current step displayed (Transcribing → Atomizing → Drafting → etc.)
- [ ] Processing tips rotate every 10 seconds
- [ ] Partial transcript appears during transcription step
- [ ] Job completes within 15 minutes for 1-hour video
- [ ] Success state shows "View Results" button

### Error Handling on Upload
- [ ] Try uploading file >500MB → expect clear error message
- [ ] Try uploading .exe file → expect "unsupported format" error
- [ ] Try uploading empty file → expect "empty file" error
- [ ] Verify error messages include actionable guidance

---

## Results Page

### Output Display
- [ ] All generated outputs displayed
- [ ] Grouped by content type (LinkedIn, Blog)
- [ ] Variation numbers shown correctly
- [ ] Content is readable and formatted

### Quality Scores
- [ ] Each output shows quality score badge (X/100)
- [ ] Hover over score shows breakdown:
  - [ ] Hook Quality
  - [ ] Brand Alignment
  - [ ] Clarity
  - [ ] Engagement Potential
- [ ] Outputs sorted by score (highest first)
- [ ] Score colors match thresholds (green ≥85, blue ≥70, yellow ≥50, red <50)

### Content Actions
- [ ] Copy button works (copies content to clipboard)
- [ ] "View all versions" expands to show Step 1, Step 2 drafts
- [ ] Warnings displayed if present (yellow badge)

### Atoms Section
- [ ] "Extracted Atoms" tab visible
- [ ] Atoms displayed with type badges (data, insight, story, etc.)
- [ ] Filter buttons work (All, Data, Stories, Insights, etc.)
- [ ] Atom copy buttons work

### Processing Info
- [ ] Total cost displayed at bottom
- [ ] Link to library works

---

## Content Library

### Library Display
- [ ] Library page loads correctly
- [ ] All atoms from uploaded content present
- [ ] Atoms grouped by source content
- [ ] Atom types displayed with colored badges

### Filtering & Search
- [ ] Filter by atom type works
- [ ] Search field filters atoms by content
- [ ] Clear filters returns all atoms

### Atom Details
- [ ] Atom content displayed
- [ ] Source location shown
- [ ] Persona relevance scores visible
- [ ] Tags displayed

### Generate from Library
- [ ] Select 3+ atoms (checkboxes)
- [ ] "Generate from Selected" button appears
- [ ] Click generates new job
- [ ] New job processes without file upload
- [ ] Results show content based on selected atoms

---

## Settings / Brand Voice

### Settings Page
- [ ] Settings page accessible from nav
- [ ] "Brand Voice Testing" tab active by default
- [ ] "Personas" tab lists all personas

### Brand Voice Preview
- [ ] Enter sample text (50+ characters)
- [ ] Select a persona
- [ ] Click "Preview Transformation"
- [ ] Loading state shown
- [ ] Side-by-side comparison displayed:
  - [ ] Original text on left
  - [ ] Transformed text on right
- [ ] Changes summary shown (what was modified)
- [ ] Copy transformed text works

### Persona Details
- [ ] Each persona card shows:
  - [ ] Title
  - [ ] Company size
  - [ ] Pain points
  - [ ] Priorities
  - [ ] Language level
  - [ ] Tone and length preferences
- [ ] "Test this persona" links to preview with persona selected

---

## Admin Interface

### Admin Access
- [ ] Access /admin/dashboard
- [ ] Verify authentication required

### Dashboard
- [ ] Job counts displayed (total, completed, failed)
- [ ] Processing cost totals shown
- [ ] Recent jobs list visible
- [ ] Click on job shows details

### Prompt Management
- [ ] Navigate to /admin/prompts
- [ ] All prompt templates listed
- [ ] Click "Edit" opens editor
- [ ] Modify prompt text
- [ ] Save changes
- [ ] Verify confirmation message

### Prompt Verification
- [ ] After editing prompt, upload new content
- [ ] Verify prompt changes reflected in output style

---

## Error Scenarios

### Network Errors
- [ ] Simulate offline → graceful error message
- [ ] API timeout → retry message displayed
- [ ] Server 500 → "Something went wrong" with contact info

### Rate Limiting
- [ ] Upload 11 times quickly → rate limit message
- [ ] Message explains wait time and upgrade option

### Processing Failures
- [ ] If job fails, error section shows:
  - [ ] Error title (specific, not generic)
  - [ ] Error message (explains what happened)
  - [ ] Action guidance (what to do next)
  - [ ] "Try Again" link

---

## Cross-Browser Testing

### Desktop Browsers
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

### Mobile Responsiveness
- [ ] iPhone Safari
- [ ] Android Chrome
- [ ] All pages usable on mobile
- [ ] Forms are touch-friendly
- [ ] Text is readable without zooming

---

## Performance Testing

### Processing Speed
- [ ] 30-second video processes in <3 minutes
- [ ] 5-minute video processes in <5 minutes
- [ ] 1-hour video processes in <15 minutes

### Page Load Speed
- [ ] All pages load in <3 seconds
- [ ] Library with 100+ atoms loads smoothly
- [ ] Results page handles 20+ outputs

### Status Page Updates
- [ ] Progress updates every 3 seconds
- [ ] No visible lag or jank
- [ ] Tips rotate smoothly

---

## Data Integrity

### User Isolation
- [ ] User A cannot see User B's jobs
- [ ] User A cannot see User B's library
- [ ] User A cannot access User B's results

### Data Persistence
- [ ] Logout and login → data still present
- [ ] Refresh page → state preserved
- [ ] Close browser, reopen → session maintained (if token valid)

---

## Final Checks

### Security
- [ ] All API endpoints require auth (except health, register, login)
- [ ] JWT tokens expire appropriately
- [ ] No sensitive data in URLs
- [ ] No API keys visible in frontend

### Links & Navigation
- [ ] All nav links work
- [ ] Logo links to home
- [ ] "Upload" in nav goes to upload page
- [ ] "Library" in nav goes to library
- [ ] "Settings" in nav goes to settings

---

## Sign-Off

| Tester | Date | Result |
|--------|------|--------|
| | | ☐ Pass ☐ Fail |

**Notes:**

---

## All Green? Ready for Replit deployment! 🚀
