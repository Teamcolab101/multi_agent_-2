from utils.database import (
    init_db,
    authenticate_user
)

init_db()

user = authenticate_user(
    "employee1",
    "emp123"
)

print(user)