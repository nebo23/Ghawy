# Phase 3 — endpoint authorization classification

All 241 endpoints. Produced by an AST scan that understands all four guard
idioms used in this repo, then **read individually**. The scan is the reading list;
the classification is the reading. Three successive scans disagreed with each other
and all three were wrong somewhere — see the methodology note in PHASE3-REPORT.md.

Guard column shows every idiom that applies, so a route guarded by a dependency
*and* an in-body permission call shows both.

| # | File | Method | Route | Guard (dep) | Guard (in-body / inline) | Client ids | Class |
|---|------|--------|-------|-------------|--------------------------|-----------|-------|
| 1 | admin.py | GET | `/users` | get_current_user | has_permission, require_permission | — | guarded |
| 2 | admin.py | POST | `/users/add` | get_current_user | require_permission | — | guarded |
| 3 | admin.py | PATCH | `/users/{user_id}/toggle-active` | get_current_user | require_permission | user_id | guarded |
| 4 | admin.py | PATCH | `/users/{user_id}/set-subscription` | get_current_user | require_permission | user_id | guarded |
| 5 | admin.py | PATCH | `/users/{user_id}/toggle-admin` | get_current_user | require_owner | user_id | guarded |
| 6 | admin.py | PATCH | `/users/{user_id}/toggle-owner` | get_current_user | inline role check | user_id | guarded |
| 7 | admin.py | GET | `/staff` | get_current_user | require_owner | — | guarded |
| 8 | admin.py | PUT | `/staff/{user_id}/permissions` | get_current_user | require_owner | user_id | guarded |
| 9 | admin.py | GET | `/staff/roles` | get_current_user | require_owner | — | guarded |
| 10 | admin.py | PUT | `/users/{user_id}/team-role` | get_current_user | require_owner | user_id | guarded |
| 11 | admin.py | DELETE | `/users/{user_id}` | get_current_user | require_owner | user_id | guarded |
| 12 | admin.py | POST | `/users/{user_id}/reset-password` | get_current_user | require_permission | user_id | guarded |
| 13 | admin.py | GET | `/notes/{user_id}` | get_current_user | require_permission | user_id | guarded |
| 14 | admin.py | POST | `/notes/{user_id}` | get_current_user | require_permission | user_id | guarded |
| 15 | admin.py | GET | `/payments` | get_current_user | has_permission, require_permission | — | guarded |
| 16 | admin.py | GET | `/payments/stats` | get_current_user | require_permission | — | guarded |
| 17 | admin.py | GET | `/payments/export-csv` | get_current_user | has_permission, require_permission | — | guarded |
| 18 | admin.py | POST | `/payments/{payment_id}/retry` | get_current_user | require_permission | payment_id | guarded |
| 19 | admin.py | POST | `/payments/{payment_id}/refund` | get_current_user | require_permission | payment_id | guarded |
| 20 | admin.py | GET | `/analytics/kpis` | get_current_user | require_permission | — | guarded |
| 21 | admin.py | GET | `/analytics/members-over-time` | get_current_user | require_permission | — | guarded |
| 22 | admin.py | GET | `/analytics/revenue-over-time` | get_current_user | require_permission | — | guarded |
| 23 | admin.py | GET | `/analytics/revenue-by-month` | get_current_user | require_permission | — | guarded |
| 24 | admin.py | GET | `/analytics/subscription-breakdown` | get_current_user | require_permission | — | guarded |
| 25 | admin.py | GET | `/analytics/payment-method-breakdown` | get_current_user | require_permission | — | guarded |
| 26 | admin.py | GET | `/students-progress` | get_current_user | require_permission | — | guarded |
| 27 | admin.py | GET | `/students-progress/{user_id}/courses/{course_id}/lessons` | get_current_user | require_permission | user_id, course_id | guarded |
| 28 | ai_updates.py | GET | `/posts` | get_current_active_member | — | — | guarded |
| 29 | ai_updates.py | GET | `/unread` | get_current_active_member | — | — | guarded |
| 30 | ai_updates.py | PUT | `/read` | get_current_active_member | — | — | guarded |
| 31 | ai_updates.py | GET | `/overview` | get_current_active_member | — | — | guarded |
| 32 | ai_updates.py | POST | `/posts` | get_current_admin_user | — | — | guarded |
| 33 | ai_updates.py | DELETE | `/posts/{post_id}` | get_current_admin_user | — | post_id | guarded |
| 34 | ai_updates.py | PATCH | `/posts/{post_id}/pin` | get_current_admin_user | — | post_id | guarded |
| 35 | ai_updates.py | PATCH | `/posts/{post_id}` | get_current_admin_user | — | post_id | guarded |
| 36 | ai_updates.py | POST | `/posts/{post_id}/react` | get_current_active_member | — | post_id | guarded |
| 37 | ai_updates.py | GET | `/posts/{post_id}/comments` | get_current_active_member | — | post_id | guarded |
| 38 | ai_updates.py | POST | `/posts/{post_id}/comments` | get_current_active_member | inline role check | post_id | guarded |
| 39 | ai_updates.py | DELETE | `/comments/{comment_id}` | get_current_active_member | inline role check | comment_id | guarded |
| 40 | ai_updates.py | POST | `/polls/{poll_id}/vote` | get_current_active_member | — | poll_id | guarded |
| 41 | ai_updates.py | GET | `/polls/{poll_id}/results` | get_current_active_member | — | poll_id | guarded |
| 42 | announcements.py | GET | `/audience/preview` | get_current_user | require_permission | — | guarded |
| 43 | announcements.py | GET | `/` | get_current_user | require_permission | — | guarded |
| 44 | announcements.py | GET | `/{announcement_id}` | get_current_user | require_permission | announcement_id | guarded |
| 45 | announcements.py | POST | `/` | get_current_user | require_permission | — | guarded |
| 46 | announcements.py | PUT | `/{announcement_id}` | get_current_user | require_permission | announcement_id | guarded |
| 47 | announcements.py | POST | `/{announcement_id}/duplicate` | get_current_user | require_permission | announcement_id | guarded |
| 48 | announcements.py | DELETE | `/{announcement_id}` | get_current_user | require_permission | announcement_id | guarded |
| 49 | announcements.py | POST | `/{announcement_id}/send` | get_current_user | require_permission | announcement_id | guarded |
| 50 | atlas.py | POST | `/send-otp` | — | — | — | public-by-design |
| 51 | atlas.py | POST | `/verify-otp` | — | — | — | public-by-design |
| 52 | birthday.py | GET | `/claim` | — | — | — | public-by-design |
| 53 | birthday.py | GET | `/claims` | get_current_user | _require_owner | — | guarded |
| 54 | birthday.py | POST | `/claims/{claim_id}/approve` | get_current_user | _require_owner | claim_id | guarded |
| 55 | birthday.py | POST | `/claims/{claim_id}/reject` | get_current_user | _require_owner | claim_id | guarded |
| 56 | chat.py | GET | `/start-here-config` | get_current_active_member | — | — | guarded |
| 57 | chat.py | PUT | `/start-here-config` | get_current_active_member | inline role check | — | guarded |
| 58 | chat.py | GET | `/messages` | get_current_active_member | ensure_channel_access | — | guarded |
| 59 | chat.py | POST | `/messages` | get_current_active_member | ensure_channel_access | — | guarded |
| 60 | chat.py | DELETE | `/messages/{message_id}` | get_current_active_member | inline role check | message_id | guarded |
| 61 | chat.py | PUT | `/messages/{message_id}` | get_current_active_member | inline role check | message_id | guarded |
| 62 | chat.py | POST | `/mark-read` | get_current_active_member | — | — | guarded |
| 63 | chat.py | GET | `/online-count` | — | — | — | public-by-design |
| 64 | chat.py | GET | `/admins` | get_current_active_member | — | — | guarded |
| 65 | chat.py | GET | `/channels` | get_current_active_member | — | — | guarded |
| 66 | chat.py | POST | `/channels` | get_current_active_member | inline role check | — | guarded |
| 67 | chat.py | POST | `/channels/{channel_id}/join` | get_current_active_member | ensure_channel_access | channel_id | guarded |
| 68 | chat.py | GET | `/channels/{channel_id}/messages` | get_current_active_member | ensure_channel_access | channel_id | guarded |
| 69 | chat.py | POST | `/channels/{channel_id}/messages` | get_current_active_member | ensure_channel_access | channel_id | guarded |
| 70 | chat.py | PUT | `/channels/{channel_id}/read` | get_current_active_member | — | channel_id | guarded |
| 71 | chat.py | PUT | `/dm/read` | get_current_active_member | — | — | guarded |
| 72 | chat.py | GET | `/community/unread` | get_current_active_member | — | — | guarded |
| 73 | chat.py | PUT | `/community/read` | get_current_active_member | — | — | guarded |
| 74 | chat.py | GET | `/channels/{channel_id}/members` | get_current_active_member | ensure_channel_access | channel_id | guarded |
| 75 | chat.py | POST | `/upload` | get_current_active_member | — | — | guarded |
| 76 | chat.py | POST | `/dm` | get_current_active_member | inline role check | — | guarded |
| 77 | chat.py | GET | `/dm/list` | get_current_active_member | — | — | guarded |
| 78 | chat.py | GET | `/members` | get_current_active_member | — | — | guarded |
| 79 | chat.py | POST | `/avatar` | get_current_active_member | — | — | guarded |
| 80 | coupons.py | POST | `/preview` | get_current_user | — | — | guarded |
| 81 | coupons.py | GET | `/admin` | get_current_user | _require_owner | — | guarded |
| 82 | coupons.py | POST | `/admin` | get_current_user | _require_owner | — | guarded |
| 83 | coupons.py | PATCH | `/admin/{coupon_id}` | get_current_user | _require_owner | coupon_id | guarded |
| 84 | courses.py | GET | `/` | — | — | — | public-by-design |
| 85 | courses.py | GET | `/progress/summary` | get_current_active_member | — | — | guarded |
| 86 | courses.py | GET | `/stats` | get_current_active_member | — | — | guarded |
| 87 | courses.py | GET | `/{course_id}` | get_current_user_optional | _can_watch | course_id | guarded |
| 88 | courses.py | PATCH | `/{course_id}/lessons/{lesson_id}/duration` | get_current_active_member | _can_watch | course_id, lesson_id | guarded |
| 89 | courses.py | POST | `/{course_id}/lessons/{lesson_id}/complete` | get_current_active_member | inline role check | course_id, lesson_id | guarded |
| 90 | courses.py | DELETE | `/{course_id}/lessons/{lesson_id}/complete` | get_current_active_member | — | course_id, lesson_id | guarded |
| 91 | courses.py | GET | `/{course_id}/top-students` | get_current_user | — | course_id | guarded |
| 92 | courses.py | GET | `/{course_id}/progress` | get_current_user | — | course_id | guarded |
| 93 | courses.py | GET | `/admin/all` | PERM_COURSES | — | — | guarded |
| 94 | courses.py | GET | `/admin/courses` | PERM_COURSES | — | — | guarded |
| 95 | courses.py | PATCH | `/admin/courses/reorder` | PERM_COURSES | — | — | guarded |
| 96 | courses.py | POST | `/admin/courses` | PERM_COURSES | — | — | guarded |
| 97 | courses.py | PATCH | `/admin/courses/{course_id}` | PERM_COURSES | — | course_id | guarded |
| 98 | courses.py | DELETE | `/admin/courses/{course_id}` | PERM_COURSES | — | course_id | guarded |
| 99 | courses.py | POST | `/admin/courses/{course_id}/upload-pdf` | PERM_COURSES | — | course_id | guarded |
| 100 | courses.py | POST | `/admin/courses/{course_id}/upload-thumbnail` | PERM_COURSES | — | course_id | guarded |
| 101 | courses.py | POST | `/admin/{course_id}/certificate` | PERM_COURSES | — | course_id | guarded |
| 102 | courses.py | DELETE | `/admin/{course_id}/certificate` | PERM_COURSES | — | course_id | guarded |
| 103 | courses.py | GET | `/admin/{course_id}/lessons` | PERM_COURSES | — | course_id | guarded |
| 104 | courses.py | POST | `/admin/{course_id}/lessons` | PERM_COURSES | — | course_id | guarded |
| 105 | courses.py | PATCH | `/admin/lessons/{lesson_id}` | PERM_COURSES | — | lesson_id | guarded |
| 106 | courses.py | POST | `/admin/lessons/{lesson_id}/pdfs` | PERM_COURSES | — | lesson_id | guarded |
| 107 | courses.py | DELETE | `/admin/lessons/{lesson_id}/pdfs` | PERM_COURSES | — | lesson_id | guarded |
| 108 | courses.py | DELETE | `/admin/lessons/{lesson_id}` | PERM_COURSES | — | lesson_id | guarded |
| 109 | courses.py | GET | `/admin/lessons/{lesson_id}/status` | PERM_COURSES | — | lesson_id | guarded |
| 110 | courses.py | PATCH | `/{course_id}/lessons/{lesson_id}` | PERM_COURSES | — | course_id, lesson_id | guarded |
| 111 | courses.py | POST | `/{course_id}/lessons` | PERM_COURSES | — | course_id | guarded |
| 112 | courses.py | GET | `/{course_id}/lessons` | get_current_user | _can_watch | course_id | guarded |
| 113 | courses.py | GET | `/{course_id}/lessons/{lesson_id}/vdo-otp` | get_current_user | inline role check | course_id, lesson_id | guarded |
| 114 | courses.py | GET | `/{course_id}/reviews` | — | — | course_id | public-by-design |
| 115 | courses.py | POST | `/{course_id}/reviews` | get_current_user | — | course_id | guarded |
| 116 | courses.py | DELETE | `/{course_id}/reviews/{review_id}` | PERM_COURSES | — | course_id, review_id | guarded |
| 117 | dashboard.py | GET | `/summary` | get_current_active_member | — | — | guarded |
| 118 | email_campaigns.py | POST | `/audience-quality` | get_current_user | require_permission | — | guarded |
| 119 | email_campaigns.py | GET | `/recipients` | get_current_user | require_permission | — | guarded |
| 120 | email_campaigns.py | GET | `/atlas-recipients` | get_current_user | require_permission | — | guarded |
| 121 | email_campaigns.py | POST | `/preview` | get_current_user | require_permission | — | guarded |
| 122 | email_campaigns.py | POST | `/send` | get_current_user | require_permission | — | guarded |
| 123 | email_campaigns.py | GET | `/status` | get_current_user | require_permission | campaign_id | guarded |
| 124 | email_campaigns.py | GET | `/campaigns` | get_current_user | require_permission | — | guarded |
| 125 | email_campaigns.py | GET | `/campaigns/{campaign_id}` | get_current_user | require_permission | campaign_id | guarded |
| 126 | email_campaigns.py | POST | `/campaigns` | get_current_user | require_permission | — | guarded |
| 127 | email_campaigns.py | PUT | `/campaigns/{campaign_id}` | get_current_user | require_permission | campaign_id | guarded |
| 128 | email_campaigns.py | POST | `/campaigns/{campaign_id}/active` | get_current_user | require_permission | campaign_id | guarded |
| 129 | exams.py | GET | `/courses/{course_id}/exams` | get_current_active_member | — | course_id | guarded |
| 130 | exams.py | GET | `/exams/{exam_id}` | get_current_active_member | — | exam_id | guarded |
| 131 | exams.py | POST | `/exams/{exam_id}/submit` | get_current_active_member | — | exam_id | guarded |
| 132 | exams.py | GET | `/admin/courses/{course_id}/exams` | PERM_COURSES | — | course_id | guarded |
| 133 | exams.py | GET | `/admin/exams/{exam_id}` | PERM_COURSES | — | exam_id | guarded |
| 134 | exams.py | POST | `/admin/courses/{course_id}/exams` | PERM_COURSES | — | course_id | guarded |
| 135 | exams.py | PATCH | `/admin/exams/{exam_id}` | PERM_COURSES | — | exam_id | guarded |
| 136 | exams.py | DELETE | `/admin/exams/{exam_id}` | PERM_COURSES | — | exam_id | guarded |
| 137 | feedbacks.py | POST | `/` | get_current_active_member | — | — | guarded |
| 138 | feedbacks.py | POST | `/upload-image` | PERM_FEEDBACKS | — | — | guarded |
| 139 | feedbacks.py | GET | `/admin` | PERM_FEEDBACKS | — | — | guarded |
| 140 | feedbacks.py | GET | `/` | get_current_active_member | — | — | guarded |
| 141 | feedbacks.py | DELETE | `/{feedback_id}` | PERM_FEEDBACKS | — | feedback_id | guarded |
| 142 | files.py | POST | `/session` | get_current_user | — | — | guarded |
| 143 | files.py | DELETE | `/session` | — | — | — | public-by-design |
| 144 | files.py | GET | `/{category}/{filename}` | file_requester | _authorize | — | guarded |
| 145 | google_auth.py | GET | `/auth/google/login` | — | — | — | public-by-design |
| 146 | google_auth.py | GET | `/auth/google/callback` | — | — | — | public-by-design |
| 147 | google_auth.py | POST | `/auth/exchange` | — | — | — | public-by-design |
| 148 | guests.py | GET | `/` | — | — | — | public-by-design |
| 149 | guests.py | GET | `/stats` | — | — | — | public-by-design |
| 150 | guests.py | GET | `/sessions/` | — | — | — | public-by-design |
| 151 | guests.py | GET | `/suggest` | get_current_active_member | require_permission | — | guarded |
| 152 | guests.py | POST | `/suggest` | get_current_active_member | — | — | guarded |
| 153 | guests.py | DELETE | `/suggest/{suggestion_id}` | get_current_active_member | require_permission | suggestion_id | guarded |
| 154 | guests.py | GET | `/{guest_id}` | — | — | guest_id | public-by-design |
| 155 | guests.py | POST | `/upload-avatar` | get_current_active_member | require_permission | — | guarded |
| 156 | guests.py | POST | `/` | get_current_active_member | require_permission | — | guarded |
| 157 | guests.py | PUT | `/{guest_id}` | get_current_active_member | require_permission | guest_id | guarded |
| 158 | guests.py | DELETE | `/{guest_id}` | get_current_active_member | require_permission | guest_id | guarded |
| 159 | guests.py | POST | `/sessions/` | get_current_active_member | require_permission | — | guarded |
| 160 | guests.py | PUT | `/sessions/{session_id}` | get_current_active_member | require_permission | session_id | guarded |
| 161 | guests.py | DELETE | `/sessions/{session_id}` | get_current_active_member | require_permission | session_id | guarded |
| 162 | help_center.py | GET | `/team` | get_current_active_member | — | — | guarded |
| 163 | live.py | POST | `/admin/live/sessions` | PERM_LIVE | — | — | guarded |
| 164 | live.py | PATCH | `/admin/live/sessions/{session_id}` | PERM_LIVE | — | session_id | guarded |
| 165 | live.py | DELETE | `/admin/live/sessions/{session_id}` | PERM_LIVE | — | session_id | guarded |
| 166 | live.py | POST | `/admin/live/sessions/{session_id}/notify` | PERM_LIVE | — | session_id | guarded |
| 167 | live.py | GET | `/admin/live/sessions` | PERM_LIVE | — | — | guarded |
| 168 | live.py | GET | `/admin/live/sessions/{session_id}/attendees` | PERM_LIVE | — | session_id | guarded |
| 169 | live.py | GET | `/live/sessions` | get_current_user | — | — | guarded |
| 170 | live.py | POST | `/live/sessions/{session_id}/register` | get_current_user | — | session_id | guarded |
| 171 | live.py | DELETE | `/live/sessions/{session_id}/register` | get_current_user | — | session_id | guarded |
| 172 | manual_payments.py | POST | `/submit` | get_current_user | — | — | guarded |
| 173 | manual_payments.py | GET | `/my-status` | get_current_user | — | — | guarded |
| 174 | manual_payments.py | GET | `/status/{email}` | get_current_user | has_permission | — | guarded |
| 175 | manual_payments.py | GET | `/stats` | get_current_user | require_owner | — | guarded |
| 176 | manual_payments.py | GET | `/` | get_current_user | require_owner | — | guarded |
| 177 | manual_payments.py | GET | `/{request_id}` | get_current_user | require_owner | request_id | guarded |
| 178 | manual_payments.py | POST | `/{request_id}/approve` | get_current_user | require_owner | request_id | guarded |
| 179 | manual_payments.py | POST | `/{request_id}/reject` | get_current_user | require_owner | request_id | guarded |
| 180 | manual_payments.py | POST | `/{request_id}/resend-invite` | get_current_user | require_owner | request_id | guarded |
| 181 | notifications.py | GET | `/` | get_current_user | — | — | guarded |
| 182 | notifications.py | PATCH | `/{notif_id}/read` | get_current_user | — | notif_id | guarded |
| 183 | notifications.py | PATCH | `/read-all` | get_current_user | — | — | guarded |
| 184 | payment.py | POST | `/kashier/create` | get_current_user | — | — | guarded |
| 185 | payment.py | GET | `/kashier/success` | — | — | — | public-by-design |
| 186 | payment.py | GET | `/kashier/fail` | — | — | — | public-by-design |
| 187 | posts.py | GET | `/{channel}` | get_current_active_member | — | — | guarded |
| 188 | posts.py | POST | `/{channel}` | get_current_active_member | — | — | guarded |
| 189 | posts.py | GET | `/{channel}/top-topics` | get_current_active_member | — | — | guarded |
| 190 | posts.py | GET | `/{channel}/pinned` | get_current_active_member | — | — | guarded |
| 191 | posts.py | GET | `/{channel}/{post_id:int}` | get_current_active_member | — | post_id | guarded |
| 192 | posts.py | PATCH | `/{channel}/{post_id:int}` | get_current_active_member | inline role check | post_id | guarded |
| 193 | posts.py | DELETE | `/{channel}/{post_id:int}` | get_current_active_member | inline role check | post_id | guarded |
| 194 | posts.py | PATCH | `/{channel}/{post_id:int}/pin` | get_current_active_member | inline role check | post_id | guarded |
| 195 | posts.py | POST | `/{post_id}/react` | get_current_active_member | — | post_id | guarded |
| 196 | posts.py | GET | `/{post_id}/comments` | get_current_active_member | — | post_id | guarded |
| 197 | posts.py | POST | `/{post_id}/comments` | get_current_active_member | inline role check | post_id | guarded |
| 198 | posts.py | PATCH | `/{post_id}/comments/{comment_id}` | get_current_active_member | inline role check | post_id, comment_id | guarded |
| 199 | posts.py | DELETE | `/{post_id}/comments/{comment_id}` | get_current_active_member | inline role check | post_id, comment_id | guarded |
| 200 | posts.py | POST | `/comments/{comment_id}/react` | get_current_active_member | — | comment_id | guarded |
| 201 | profile.py | POST | `/heartbeat` | get_current_active_member | — | — | guarded |
| 202 | profile.py | POST | `/offline` | get_current_active_member | — | — | guarded |
| 203 | profile.py | GET | `/subscription-info` | get_current_user | — | — | guarded |
| 204 | profile.py | GET | `/me` | get_current_active_member | — | — | guarded |
| 205 | profile.py | PUT | `/me` | get_current_active_member | — | — | guarded |
| 206 | profile.py | POST | `/avatar` | get_current_active_member | — | — | guarded |
| 207 | profile.py | GET | `/onboarding-status` | get_current_active_member | — | — | guarded |
| 208 | profile.py | POST | `/complete-onboarding` | get_current_active_member | — | — | guarded |
| 209 | profile.py | POST | `/upload-avatar` | get_current_active_member | — | — | guarded |
| 210 | profile.py | GET | `/{user_id}/public` | get_current_active_member | — | user_id | guarded |
| 211 | profile.py | GET | `/{user_id}` | get_current_active_member | has_permission | user_id | guarded |
| 212 | profile.py | POST | `/change-password` | get_current_active_member | — | — | guarded |
| 213 | profile.py | POST | `/send-phone-otp` | get_current_active_member | — | — | guarded |
| 214 | profile.py | POST | `/verify-phone-otp` | get_current_active_member | — | — | guarded |
| 215 | projects.py | POST | `/projects/submit` | get_current_active_member | — | course_id | guarded |
| 216 | projects.py | GET | `/projects/my-projects` | get_current_active_member | — | course_id | guarded |
| 217 | projects.py | GET | `/projects/{project_id}` | get_current_active_member | — | project_id | guarded |
| 218 | projects.py | GET | `/admin/projects` | PERM_PROJECTS | — | course_id | guarded |
| 219 | projects.py | GET | `/admin/projects/{project_id}` | PERM_PROJECTS | — | project_id | guarded |
| 220 | projects.py | GET | `/admin/projects/{project_id}/download` | PERM_PROJECTS | — | project_id | guarded |
| 221 | projects.py | POST | `/admin/projects/{project_id}/approve` | PERM_PROJECTS | — | project_id | guarded |
| 222 | projects.py | POST | `/admin/projects/{project_id}/request-changes` | PERM_PROJECTS | — | project_id | guarded |
| 223 | projects.py | POST | `/admin/projects/{project_id}/notes` | PERM_PROJECTS | — | project_id | guarded |
| 224 | projects.py | DELETE | `/admin/projects/{project_id}` | PERM_PROJECTS | — | project_id | guarded |
| 225 | reports.py | POST | `/` | get_current_active_member | — | — | guarded |
| 226 | reports.py | GET | `/my` | get_current_active_member | — | — | guarded |
| 227 | reports.py | GET | `/admin` | PERM_REPORTS | — | user_id | guarded |
| 228 | reports.py | DELETE | `/{report_id}` | PERM_REPORTS | — | report_id | guarded |
| 229 | stats.py | GET | `/public` | — | — | — | public-by-design |
| 230 | users.py | POST | `/register` | — | — | — | public-by-design |
| 231 | users.py | POST | `/login` | — | — | — | public-by-design |
| 232 | users.py | POST | `/token` | — | — | — | public-by-design |
| 233 | users.py | POST | `/verify-email` | — | — | — | public-by-design |
| 234 | users.py | POST | `/resend-verification-code` | — | — | — | public-by-design |
| 235 | users.py | POST | `/forgot-password` | — | — | — | public-by-design |
| 236 | users.py | POST | `/verify-reset-code` | — | — | — | public-by-design |
| 237 | users.py | POST | `/reset-password` | — | — | — | public-by-design |
| 238 | users.py | POST | `/logout-all` | get_current_user | — | — | guarded |
| 239 | users.py | GET | `/` | get_current_active_member | has_permission | — | guarded |
| 240 | users.py | DELETE | `/account` | get_current_user | — | — | guarded |
| 241 | webhooks.py | POST | `/kashier` | — | — | — | public-by-design |

## The 26 unauthenticated endpoints, one by one

Each was read in full. None is a vulnerability; every one is listed here with the
reason it needs no session.

| File | Method | Route | Why it needs no auth |
|---|---|---|---|
| atlas.py | POST | `/send-otp` | Roster membership + 60s server-side resend cooldown + nginx `otp` zone. Serves people who may not have an account yet. |
| atlas.py | POST | `/verify-otp` | The OTP proves control of the address; code burns after 5 wrong tries. |
| birthday.py | GET | `/claim` | Authenticated by a signed JWT in the email link (checks `purpose` and `year`). Idempotent per year; creates only a *pending* claim an owner must approve. |
| chat.py | GET | `/online-count` | Returns one integer from the in-memory WS manager, no DB query, nothing identifying. Polled by every page. |
| courses.py | GET | `/` | The published course catalogue the marketing site renders. `PublicCourseOut` deliberately withholds `pdf_url` and video ids. |
| courses.py | GET | `/{course_id}/reviews` | Public testimonials. Reviewer display name and avatar only. |
| files.py | DELETE | `/session` | DELETE clears the caller's own cookie and reads nothing. There is no other party to authorize. |
| google_auth.py | GET | `/auth/google/login` | OAuth entry point — it only redirects to Google. |
| google_auth.py | GET | `/auth/google/callback` | Authenticated by Google's signed token, and refuses a claim whose `email_verified` is false. |
| google_auth.py | POST | `/auth/exchange` | Authenticated by the HttpOnly hand-off cookie: single-use, 120-second life, `typ=oauth` so it is not a session. |
| guests.py | GET | `/` | Guest-of-honour marketing content. |
| guests.py | GET | `/stats` | Aggregate counts over the same marketing content. |
| guests.py | GET | `/sessions/` | Guest session schedule — same marketing content. |
| guests.py | GET | `/{guest_id}` | One guest, same marketing content. |
| payment.py | GET | `/kashier/success` | Kashier redirects the payer's browser here. Confirms a payment only on a valid redirect signature AND matching amount and currency AND a PENDING row. |
| payment.py | GET | `/kashier/fail` | A static redirect to `/pricing?error=failed`. Reads no input. |
| stats.py | GET | `/public` | Member count only, 5-minute cache, single-flight. |
| users.py | POST | `/register` | Signup. Turnstile + disposable/fake-email filter + nginx `register` zone (6r/m). |
| users.py | POST | `/login` | Login. nginx `auth` zone (30r/m) — verified firing at request 12. |
| users.py | POST | `/token` | OAuth2 password-form login, same protections. |
| users.py | POST | `/verify-email` | Consumes a 6-digit code that was emailed to the address. |
| users.py | POST | `/resend-verification-code` | nginx `otp` zone (6r/m). |
| users.py | POST | `/forgot-password` | Constant response regardless of whether the address exists (no enumeration) + nginx `otp` zone. |
| users.py | POST | `/verify-reset-code` | Consumes the emailed code; 5-attempt counter then burn. |
| users.py | POST | `/reset-password` | Consumes the reset token and bumps `token_version`, killing existing sessions. |
| webhooks.py | POST | `/kashier` | Authenticated by the `x-kashier-signature` HMAC rather than by a session — that is what a webhook is. |
