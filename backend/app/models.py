"""Document shapes stored in MongoDB (for reference; validation lives in schemas.py).

users
  _id, email (unique, lowercase), full_name, hashed_password,
  role: "user" | "admin" | "superadmin", is_active, created_at, created_by, last_login_at,
  age, height_cm, weight_kg, sex, activity_level, preferred_language

food_logs
  _id, user_id (ObjectId -> users), created_at, raw_text, native_text, language,
  items: [FoodItem], total_calories, total_protein, total_carbs, total_fat, total_fibre

password_resets
  _id, email, otp_hash (sha256), created_at, expires_at (TTL), is_used, attempts

audit_log
  _id, at, actor_email, action, target_email, detail
"""
