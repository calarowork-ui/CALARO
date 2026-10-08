import os

os.environ["MONGODB_DB"] = "calaro_test"
os.environ["BHASHINI_USER_ID"] = "test-user"
os.environ["BHASHINI_API_KEY"] = "test-key"
os.environ["BHASHINI_INFERENCE_API_KEY"] = ""
os.environ["BHASHINI_UDYAT_KEY"] = ""
os.environ["SUPERADMIN_EMAIL"] = "calaro@admin.calaro.com"
os.environ["SUPERADMIN_PASSWORD"] = "super-secret-1"
os.environ["REGISTER_PER_HOUR_PER_IP"] = "1000"
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:9"  # unreachable on purpose

from mongomock_motor import AsyncMongoMockClient  # noqa: E402

from app import database  # noqa: E402

database.set_client(AsyncMongoMockClient())
